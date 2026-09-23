# Wire 2.0 public fixtures

**TEST ONLY / SYNTHETIC PUBLIC FIXTURE / NOT RUNTIME SECRET MATERIAL**

`vectors.json` contains frozen literal bytes, SHA-256 and HMAC outputs. W0 and
H0 match the normative document. Other window vectors replace W0's first x
position, replace all quaternions, or set tracking count 114/113. The 113 case is
structurally parseable but invalid sender quality; its tag is test-only.

Fixture creation used independent standard-library arithmetic with the literal
101-byte W0 header, explicit offsets and `struct.pack('>HQ', ...)`, without
importing the implementation under test. Tests never regenerate expectations.
The separate C# writer checks every valid full byte array and both digests via
`tests/auth/check_binary_v2_dotnet.ps1`; Unity EditMode tests read this same file.
The Python tests independently build every window and compare every byte.

The scalar HMAC covers only the concatenated scalar words. Such input is never
a valid authenticated window. Negative zero has the positive-zero output/tag;
raw negative zero is forbidden when parsing. All nonfinite inputs are invalid.
