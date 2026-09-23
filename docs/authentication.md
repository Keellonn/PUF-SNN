# Layer 3 Authentication


## Executive summary

A device calls the frozen reconstruction function once for one scheduled PUF
reading. Only `candidate_valid_format` permits a session attempt. The candidate
is four bytes, not an authenticated credential. A verifier independently holds
trusted enrollment material, issues fresh session material, derives its own
HKDF-SHA256 key, and verifies a transcript-bound HMAC possession proof. Only that
proof can activate a session. The sender also verifies a server confirmation.

Windows preserve Keegan's 120-sample motion semantics but authenticate a precise
binary representation: big-endian integers, length-prefixed identifiers, and
exact finite IEEE-754 binary32 motion components. Negative zero becomes positive
zero at the sender. The verifier authenticates the exact received canonical
bytes, enforces device/session binding and strict consecutive sequence numbers,
and emits an audit record before releasing an accepted immutable payload.

The pilot credential is only 32 bits, and the existing research credentials are
deterministically reproducible from public experiment seeds. HKDF adds no entropy.
This design tests protocol behavior; it does not establish production security.
