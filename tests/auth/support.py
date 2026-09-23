"""Synthetic public test peers and raw mutation helpers, never experiment code."""
from dataclasses import replace
import base64
import json

from puf_snn.auth.binary_window import F32, Sample, Window, LP, V, encode_window, window_tag
from puf_snn.auth.session import RegistryEntry, SessionConfig, Transcript, frame, unframe, derive_session_key, client_proof
from puf_snn.auth.verifier import Verifier

CREDENTIAL = b"\x00\x00\x00\x01"


def activate(v, device="sim-device", credential=CREDENTIAL):
    request = frame(b"P3RQ" + V(2, 0) + LP(device.encode()) + bytes(range(32)))
    r = unframe(v.begin_session(request))
    r.expect(b"P3CH")
    transcript = r.lp()
    context = Transcript.parse(transcript)
    key = derive_session_key(credential, transcript)
    proof = client_proof(key, transcript)
    response = v.confirm_session(frame(b"P3CF" + V(2, 0) + context.session_id + proof))
    assert response[4:8] == b"P3OK"
    return context.session_id, key


def setup(config=SessionConfig()):
    v = Verifier([RegistryEntry("sim-device", "enrollment-1", CREDENTIAL),
                  RegistryEntry("other-device", "enrollment-2", CREDENTIAL)], config)
    sid, key = activate(v)
    return v, sid, key


def window(sid, seq=0):
    z, one = F32(0), F32(0x3f800000)
    samples = tuple(Sample(i, 1_000_000_000 + i*16_666_667, (z, z, z), (z, z, z, one), True)
                    for i in range(120))
    return Window("sim-device", sid, seq, "synthetic-window", 1_000_000_000, 3_000_000_000,
                  120, 1_000_000, samples)


def packet(sid, key, seq=0, **changes):
    return wrap(encode_window(replace(window(sid, seq), **changes)), sid, key)


def wrap(data, sid, key, tag=None, key_id=None):
    return json.dumps({"protected": {"encoding": "puf-snn-binary32-be-v2",
                                     "bytes_b64": base64.b64encode(data).decode()},
                       "authentication": {"algorithm": "HMAC-SHA-256", "key_id": key_id or sid.hex(),
                                          "tag_hex": (tag if tag is not None else window_tag(key, data)).hex()}}).encode()


def mutate(data, offset, value):
    return data[:offset] + value + data[offset+len(value):]


def offsets(data):
    dlen = int.from_bytes(data[19:21], "big")
    sid = 21 + dlen
    seq = sid + 16
    wid = seq + 8
    start = wid + 2 + int.from_bytes(data[wid:wid+2], "big")
    return dict(sid=sid, seq=seq, start=start, end=start+8, count=start+19, ppm=start+21,
                payload=start+29, sample=start+32)
