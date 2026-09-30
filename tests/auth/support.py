"""Synthetic public test peers and raw mutation helpers, never experiment code."""
from dataclasses import replace
import base64
import json

from puf_snn.auth.binary_window import F32, Sample, Window, LP, V, encode_window, window_tag
from puf_snn.auth.session import RegistryEntry, SessionConfig, Transcript, frame, unframe, derive_session_key, client_proof
from puf_snn.auth.verifier import Verifier
from puf_snn.auth.session import Sender, provision_device
from puf_snn.auth.credential_verifier import (
    CredentialAdmissionService, CredentialVerifierRecord, CredentialVerifierStore,
    InMemoryCredentialVerifierKeyProvider,
)

CREDENTIAL = b"\x00\x00\x00\x01"


def admission_for_entries(entries):
    """Trusted synthetic enrollment, never a verification bypass."""
    provider = InMemoryCredentialVerifierKeyProvider("synthetic-test-key", bytes(range(32)))
    records = [CredentialVerifierRecord.enroll(
        device_id=e.device_id, enrollment_id=e.enrollment_id, reconstruction_id=e.reconstruction_id,
        verifier_key_id="synthetic-test-key", credential4=e.credential4, key_provider=provider,
    ) for e in entries]
    return CredentialAdmissionService(CredentialVerifierStore(records), provider)


def make_verifier(entries, config=SessionConfig()):
    return Verifier(entries, config, admission_service=admission_for_entries(entries))


def admitted_request(v, device="sim-device", credential=CREDENTIAL):
    from puf_snn.reconstruction import enroll, ReconstructionResult
    entry = v._registry[device]  # Trusted fixture binding, not verification truth.
    helper = enroll((0,)*64, credential, enrollment_id=entry.enrollment_id)
    s = Sender(provision_device(device, entry.enrollment_id, helper), v.config.limits,
               admission_service=v._admission_service)
    bits = tuple((b >> shift) & 1 for b in credential for shift in range(7, -1, -1)) + (0,)*4
    result = ReconstructionResult('candidate_valid_format', 'decoded', 0, bits, credential, True, None)
    request = s.begin_attempt(result, 'synthetic-fixture-attempt')
    assert type(request) is bytes
    return s, request


def activate(v, device="sim-device", credential=CREDENTIAL):
    sender, request = admitted_request(v, device, credential)
    confirmation = sender.answer_challenge(v.begin_session(request, admission=sender.admission))
    response = v.confirm_session(confirmation)
    assert sender.finish_session(response) is sender
    return sender._context.session_id, sender._key


def setup(config=SessionConfig()):
    v = make_verifier([RegistryEntry("sim-device", "enrollment-1", CREDENTIAL),
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
