"""Wire 2.0 codec. No session lookup, replay decisions, or inference release.

Motion enters as F32 bit words or explicitly checked exactly widened floats.
Parsing checks representation only; sender construction also checks quality.
"""
from dataclasses import dataclass
from fractions import Fraction
import base64
import hashlib
import hmac
import json
import re
import struct


class ProtocolError(ValueError):
    def __init__(self, reason="malformed_message"):
        self.reason = reason
        super().__init__(reason)


def uint(value, width):
    if type(value) is not int or not 0 <= value < 1 << (8 * width):
        raise ProtocolError()
    return value.to_bytes(width, "big")


def U8(x): return uint(x, 1)
def U16(x): return uint(x, 2)
def U32(x): return uint(x, 4)
def U64(x): return uint(x, 8)
def V(a, b): return U16(a) + U16(b)


def raw(value, length=None):
    if type(value) is not bytes or (length is not None and len(value) != length):
        raise ProtocolError()
    return value


def LP(value):
    return U16(len(raw(value))) + value


def identifier(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is None:
        raise ProtocolError()
    return value.encode("ascii")


@dataclass(frozen=True)
class F32:
    bits: int

    def __post_init__(self):
        U32(self.bits)
        if self.bits & 0x7f800000 == 0x7f800000:
            raise ProtocolError("invalid_payload_schema")

    def encode(self):
        return U32(0 if self.bits == 0x80000000 else self.bits)

    @classmethod
    def parse(cls, value):
        word = int.from_bytes(raw(value, 4), "big")
        if word == 0x80000000:
            raise ProtocolError("invalid_payload_schema")
        return cls(word)

    @classmethod
    def from_exact_float(cls, value):
        if type(value) is not float:
            raise ProtocolError("invalid_payload_schema")
        try:
            encoded = struct.pack(">f", value)
        except (OverflowError, struct.error):
            raise ProtocolError("invalid_payload_schema") from None
        if struct.unpack(">f", encoded)[0] != value:
            raise ProtocolError("invalid_payload_schema")
        return cls(int.from_bytes(encoded, "big"))

    def rational(self):
        word = self.bits
        exponent = (word >> 23) & 255
        mantissa = word & 0x7fffff
        if exponent:
            mantissa |= 1 << 23
        power = exponent - 150 if exponent else -149
        value = Fraction(mantissa * (1 << max(power, 0)), 1 << max(-power, 0))
        return -value if word >> 31 else value


class Reader:
    def __init__(self, data):
        self.data = raw(data)
        self.offset = 0

    def take(self, size):
        end = self.offset + size
        if end > len(self.data):
            raise ProtocolError()
        result = self.data[self.offset:end]
        self.offset = end
        return result

    def integer(self, size): return int.from_bytes(self.take(size), "big")
    def lp(self): return self.take(self.integer(2))

    def expect(self, expected, reason="malformed_message"):
        if self.take(len(expected)) != expected:
            raise ProtocolError(reason)

    def id(self):
        try:
            value = self.lp().decode("ascii")
        except UnicodeError:
            raise ProtocolError() from None
        identifier(value)
        return value

    def done(self):
        if self.offset != len(self.data):
            raise ProtocolError()


@dataclass(frozen=True)
class Sample:
    sample_index: int
    capture_time_ns: int
    position_m: tuple[F32, F32, F32]
    orientation_xyzw: tuple[F32, F32, F32, F32]
    tracking_valid: bool


@dataclass(frozen=True)
class Window:
    device_id: str
    session_id: bytes
    sequence_number: int
    window_id: str
    capture_start_ns: int
    capture_end_ns: int
    tracking_valid_count: int
    tracking_valid_fraction_ppm: int
    samples: tuple[Sample, ...]


def timestamp(value, sample=False, end=False):
    if type(value) is not int or not int(end) <= value < 1 << 63:
        raise ProtocolError("invalid_payload_schema" if sample else "malformed_message")
    return U64(value)


def tracking_ppm(count):
    quotient, remainder = divmod(count * 1_000_000, 120)
    return quotient + int(remainder > 60 or (remainder == 60 and quotient % 2 == 1))


def validate_quality(window):
    def require(condition):
        if not condition:
            raise ProtocolError("data_quality_failure")
    require(abs(window.capture_end_ns - window.capture_start_ns - 2_000_000_000) <= 120)
    count = sum(sample.tracking_valid for sample in window.samples)
    require(114 <= count <= 120 and count == window.tracking_valid_count)
    require(tracking_ppm(count) == window.tracking_valid_fraction_ppm)
    previous_time = None
    previous_q = None
    for sample in window.samples:
        time = sample.capture_time_ns
        require(window.capture_start_ns <= time < window.capture_end_ns)
        require(previous_time is None or 0 < time - previous_time <= 50_000_000)
        q = tuple(value.rational() for value in sample.orientation_xyzw)
        require(all(abs(value) <= Fraction(1000001, 1000000) for value in q))
        require(Fraction(9999, 10000)**2 <= sum(value**2 for value in q) <= Fraction(10001, 10000)**2)
        require(previous_q is None or sum(a*b for a, b in zip(q, previous_q)) >= 0)
        previous_time, previous_q = time, q


def encode_window(window):
    """Build A from immutable typed input; refuse invalid sender quality."""
    if type(window) is not Window or type(window.samples) is not tuple or len(window.samples) != 120:
        raise ProtocolError("invalid_payload_schema")
    try:
        sequence = U64(window.sequence_number)
    except ProtocolError:
        raise ProtocolError("sequence_out_of_range") from None
    header = (b"P3AW" + V(2, 0) + V(2, 0) + V(1, 0) + b"\x01\x01\x20"
              + LP(identifier(window.device_id)) + raw(window.session_id, 16) + sequence
              + LP(identifier(window.window_id)) + timestamp(window.capture_start_ns)
              + timestamp(window.capture_end_ns, end=True) + b"\x01" + U16(120)
              + U16(window.tracking_valid_count) + U32(window.tracking_valid_fraction_ppm) + U32(4683))
    payload = bytearray(b"\x01\x00\x3c")
    for index, sample in enumerate(window.samples):
        if (type(sample) is not Sample or type(sample.sample_index) is not int
                or sample.sample_index != index or type(sample.tracking_valid) is not bool
                or type(sample.position_m) is not tuple or len(sample.position_m) != 3
                or type(sample.orientation_xyzw) is not tuple or len(sample.orientation_xyzw) != 4):
            raise ProtocolError("invalid_payload_schema")
        payload += U16(index) + timestamp(sample.capture_time_ns, sample=True)
        for value in sample.position_m + sample.orientation_xyzw:
            if type(value) is not F32:
                raise ProtocolError("invalid_payload_schema")
            payload += value.encode()
        payload += U8(int(sample.tracking_valid))
    validate_quality(window)
    return header + bytes(payload)


def parse_window(data):
    """Parse representation, without claiming authentication or testing quality."""
    raw(data)
    if not 4761 <= len(data) <= 5015:
        raise ProtocolError()
    r = Reader(data)
    r.expect(b"P3AW")
    r.expect(V(2, 0) + V(2, 0), "unsupported_protocol_version")
    r.expect(V(1, 0) + b"\x01", "invalid_payload_schema")
    r.expect(b"\x01\x20")
    device, session, sequence, window_id = r.id(), r.take(16), r.integer(8), r.id()
    start, end = r.integer(8), r.integer(8)
    timestamp(start)
    timestamp(end, end=True)
    r.expect(b"\x01\x00\x78", "invalid_payload_schema")
    count, ppm = r.integer(2), r.integer(4)
    r.expect(U32(4683))
    r.expect(b"\x01\x00\x3c", "invalid_payload_schema")
    samples = []
    for index in range(120):
        r.expect(U16(index), "invalid_payload_schema")
        time = r.integer(8)
        timestamp(time, sample=True)
        values = tuple(F32.parse(r.take(4)) for _ in range(7))
        tracking = r.integer(1)
        if tracking not in (0, 1):
            raise ProtocolError("invalid_payload_schema")
        samples.append(Sample(index, time, values[:3], values[3:], bool(tracking)))
    r.done()
    return Window(device, session, sequence, window_id, start, end, count, ppm, tuple(samples))


def window_tag(key, data):
    return hmac.new(raw(key, 32), raw(data), hashlib.sha256).digest()


def encode_envelope(data, key):
    window = parse_window(data)
    validate_quality(window)
    return json.dumps({"protected": {"encoding": "puf-snn-binary32-be-v2",
                                     "bytes_b64": base64.b64encode(data).decode("ascii")},
                       "authentication": {"algorithm": "HMAC-SHA-256", "key_id": window.session_id.hex(),
                                          "tag_hex": window_tag(key, data).hex()}},
                      separators=(",", ":")).encode("utf-8")


@dataclass(frozen=True)
class Envelope:
    authenticated_bytes: bytes
    window: Window
    key_id: str
    tag: bytes

    def check_key_id(self):
        # Stateful verifier must call AFTER authenticating and binding the owner.
        if self.key_id != self.window.session_id.hex():
            raise ProtocolError("invalid_key_id")


def parse_envelope(data):
    raw(data)
    if len(data) > 16384 or data.startswith(b"\xef\xbb\xbf"):
        raise ProtocolError()
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError()
            result[key] = value
        return result
    def fields(obj, names):
        if type(obj) is not dict or set(obj) != set(names):
            raise ProtocolError()
    try:
        obj = json.loads(data.decode("utf-8", errors="strict"), object_pairs_hook=pairs)
        fields(obj, ("protected", "authentication"))
        p, a = obj["protected"], obj["authentication"]
        fields(p, ("encoding", "bytes_b64"))
        fields(a, ("algorithm", "key_id", "tag_hex"))
        if any(type(value) is not str for value in (*p.values(), *a.values())):
            raise ProtocolError()
        if p["encoding"] != "puf-snn-binary32-be-v2" or a["algorithm"] != "HMAC-SHA-256":
            raise ProtocolError()
        if not re.fullmatch("[0-9a-f]{32}", a["key_id"]) or not re.fullmatch("[0-9a-f]{64}", a["tag_hex"]):
            raise ProtocolError()
        binary = base64.b64decode(p["bytes_b64"], validate=True)
        if base64.b64encode(binary).decode("ascii") != p["bytes_b64"]:
            raise ProtocolError()
    except (ValueError, UnicodeError, RecursionError):
        raise ProtocolError() from None
    return Envelope(binary, parse_window(binary), a["key_id"], bytes.fromhex(a["tag_hex"]))
