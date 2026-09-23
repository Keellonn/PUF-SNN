"""Synthetic public fixtures; no runtime provisioning material."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import struct
import unittest

from puf_snn.auth.binary_window import (
    F32, Sample, Window, U8, U16, U32, U64, V, LP, ProtocolError, identifier,
    encode_window, parse_window, encode_envelope, parse_envelope, window_tag,
    tracking_ppm, validate_quality,
)

FIXTURE = json.loads((Path(__file__).parent / 'fixtures/binary-v2/vectors.json').read_text())
KEY = bytes.fromhex(FIXTURE['key_hex'])


def make_window(vector=None):
    vector = vector or FIXTURE['windows'][0]
    zero = F32(0)
    q = (zero, F32(0x3f3504f3), zero, F32(0x3f3504f3)) if vector['quaternion'] else (zero, zero, zero, F32(0x3f800000))
    count = vector['tracking_count']
    samples = tuple(Sample(i, 1000000000 + i*16666667,
                           (F32(int(vector['position_word'], 16)), F32(0xbe800000), zero) if i == 0 else (zero,)*3,
                           q, i < count) for i in range(120))
    return Window('quest-02', bytes(range(16)), 0, 'binary-golden-000', 1000000000,
                  3000000000, count, tracking_ppm(count), samples)


class BinaryTests(unittest.TestCase):
    def test_scalar_literals(self):
        for vector in FIXTURE['scalars']:
            with self.subTest(vector=vector['id']):
                if not vector['valid']:
                    for word in vector['words']:
                        with self.assertRaises(ProtocolError): F32(int(word,16))
                        with self.assertRaises(ProtocolError): F32.parse(bytes.fromhex(word))
                    continue
                actual = b''.join(F32(int(w,16)).encode() for w in vector['words'])
                self.assertEqual(actual, bytes.fromhex(vector['expected_hex']))
                self.assertEqual(hashlib.sha256(actual).hexdigest(), vector['sha256'])
                self.assertEqual(window_tag(KEY, actual).hex(), vector['hmac'])
                for word in vector['words']:
                    if word == '80000000':
                        with self.assertRaises(ProtocolError): F32.parse(bytes.fromhex(word))
                    else:
                        self.assertEqual(F32.parse(bytes.fromhex(word)).bits, int(word,16))
                    widened = struct.unpack('>f', bytes.fromhex(word))[0]
                    self.assertEqual(F32.from_exact_float(widened).encode(), F32(int(word,16)).encode())

    def test_complete_literal_vectors(self):
        for vector in FIXTURE['windows']:
            with self.subTest(vector=vector['id']):
                window = make_window(vector)
                if not vector['valid']:
                    with self.assertRaisesRegex(ProtocolError, 'data_quality_failure'): encode_window(window)
                    parsed = parse_window(bytes.fromhex(vector['expected_hex']))
                    with self.assertRaisesRegex(ProtocolError, 'data_quality_failure'): validate_quality(parsed)
                    continue
                actual = encode_window(window)
                self.assertEqual(actual, bytes.fromhex(vector['expected_hex']))
                self.assertEqual(len(actual), vector['length'])
                self.assertEqual(hashlib.sha256(actual).hexdigest(), vector['sha256'])
                self.assertEqual(window_tag(KEY, actual).hex(), vector['hmac'])
                self.assertEqual(encode_window(parse_window(actual)), actual)

    def test_float_adapter_rejects_rounding_and_nonfinite(self):
        for value in (0.1, 0.12345678, 1e300, float('nan'), float('inf'), -float('inf'), True, 1, '0'):
            with self.subTest(value=value), self.assertRaises(ProtocolError): F32.from_exact_float(value)

    def test_integer_bounds_and_identifiers(self):
        for func, width in ((U8,1),(U16,2),(U32,4),(U64,8)):
            self.assertEqual(func((1 << (width*8))-1), b'\xff'*width)
            self.assertEqual(func(0), bytes(width))
            for bad in (-1, 1 << (width*8), True, False, 1.0, '1'):
                with self.assertRaises(ProtocolError): func(bad)
        self.assertEqual(V(2,0), bytes.fromhex('00020000'))
        self.assertEqual(LP(b'abc'), bytes.fromhex('0003616263'))
        with self.assertRaises(ProtocolError): LP(bytes(65536))
        for bad in ('', '-a', 'a b', 'a\x00', 'é', 'a'*129, True):
            with self.assertRaises(ProtocolError): identifier(bad)
        w = replace(make_window(), device_id='a'*128, window_id='b'*128, sequence_number=2**64-1)
        self.assertEqual(len(encode_window(w)), 5015)
        self.assertEqual(parse_window(encode_window(w)), w)

    def test_envelope_transport(self):
        a = encode_window(make_window())
        packet = encode_envelope(a, KEY)
        parsed = parse_envelope(packet)
        self.assertEqual(parsed.authenticated_bytes, a)
        self.assertEqual(parsed.tag, window_tag(KEY, a))
        parsed.check_key_id()
        obj = json.loads(packet)
        self.assertEqual(parse_envelope(json.dumps(obj, indent=3, sort_keys=True).encode()).authenticated_bytes, a)
        bad_packets = [b'\xef\xbb\xbf'+packet, packet+b'x', b' '*16385, b'\xff', packet.replace(b'"protected":', b'"protected":{},"protected":',1)]
        for bad in bad_packets:
            with self.assertRaises(ProtocolError): parse_envelope(bad)
        for path, value in [(('protected','encoding'),'legacy'), (('protected','bytes_b64'), obj['protected']['bytes_b64']+'='),
                            (('authentication','algorithm'),'HMAC-SHA256'), (('authentication','tag_hex'),'A'*64),
                            (('authentication','key_id'),'0'*31), (('protected','extra'),'x'),
                            (('protected','bytes_b64'),'\ud800')]:
            modified = json.loads(packet)
            modified[path[0]][path[1]] = value
            with self.subTest(path=path), self.assertRaises(ProtocolError): parse_envelope(json.dumps(modified).encode())
        obj['authentication']['key_id'] = 'f'*32
        parsed = parse_envelope(json.dumps(obj).encode())
        with self.assertRaisesRegex(ProtocolError,'invalid_key_id'): parsed.check_key_id()

    def test_structural_rejection_offsets(self):
        a = encode_window(make_window())
        # Each constant, length, index, bool, noncanonical scalar and timestamp.
        changes = [(0,b'X'),(4,b'\x01'),(8,b'\x01'),(12,b'\x01'),(16,b'\x02'),(17,b'\x02'),
                   (18,b'\x10'),(19,b'\xff'),(21,b'-'),(53,b'\xff'),(72,b'\x80'),(89,b'\xff'),
                   (90,b'\x79'),(97,b'\xff'),(101,b'\x02'),(103,b'\x3b'),(105,b'\x01'),
                   (106,b'\x80'),(114,bytes.fromhex('80000000')),(114,bytes.fromhex('7fc00000')),(142,b'\x02')]
        for offset, value in changes:
            bad = a[:offset]+value+a[offset+len(value):]
            with self.subTest(offset=offset), self.assertRaises(ProtocolError): parse_window(bad)
        for bad in (a[:-1], a+b'\x00', a[:100], b''):
            with self.assertRaises(ProtocolError): parse_window(bad)

    def test_quality_is_separate_from_parser(self):
        w = make_window()
        for delta in (-120,120): encode_window(replace(w,capture_end_ns=w.capture_end_ns+delta))
        for delta in (-121,121):
            with self.assertRaisesRegex(ProtocolError,'data_quality_failure'): encode_window(replace(w,capture_end_ns=w.capture_end_ns+delta))
        for changed in (replace(w,tracking_valid_count=119),replace(w,tracking_valid_fraction_ppm=999999),
                        replace(w,samples=(replace(w.samples[0],orientation_xyzw=(F32(0),)*4),)+w.samples[1:]),
                        replace(w,samples=(w.samples[0],replace(w.samples[1],capture_time_ns=w.samples[0].capture_time_ns))+w.samples[2:])):
            with self.assertRaisesRegex(ProtocolError,'data_quality_failure'): encode_window(changed)
        data = bytearray(encode_window(w));data[91:93]=bytes.fromhex('0077')
        parsed = parse_window(bytes(data))
        with self.assertRaisesRegex(ProtocolError,'data_quality_failure'): validate_quality(parsed)
