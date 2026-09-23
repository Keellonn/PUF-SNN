"""Frozen RFC 5869 Appendix A.1--A.3 known answers, public test material."""
import unittest
from puf_snn.auth.session import hkdf_extract, hkdf_expand


class HKDFTests(unittest.TestCase):
    def test_rfc_a1(self):
        prk = hkdf_extract(bytes.fromhex('000102030405060708090a0b0c'), bytes.fromhex('0b' * 22))
        self.assertEqual(prk.hex(), '077709362c2e32df0ddc3f0dc47bba6390b6c73bb50f9c3122ec844ad7c2b3e5')
        self.assertEqual(hkdf_expand(prk, bytes.fromhex('f0f1f2f3f4f5f6f7f8f9'), 42).hex(),
                         '3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865')

    def test_rfc_a2(self):
        prk = hkdf_extract(bytes(range(0x60, 0xb0)), bytes(range(0x50)))
        self.assertEqual(prk.hex(), '06a6b88c5853361a06104c9ceb35b45cef760014904671014a193f40c15fc244')
        self.assertEqual(hkdf_expand(prk, bytes(range(0xb0, 0x100)), 82).hex(),
                         'b11e398dc80327a1c8e7f78c596a49344f012eda2d4efad8a050cc4c19afa97c59045a99cac7827271cb41c65e590e09da3275600c2f09b8367793a9aca3db71cc30c58179ec3e87c14c01d5c1f3434f1d87')

    def test_rfc_a3(self):
        prk = hkdf_extract(b'', bytes.fromhex('0b' * 22))
        self.assertEqual(prk.hex(), '19ef24a32c717b167f33a91d6f648bdf96596776afdb6377ac434c1c293ccb04')
        self.assertEqual(hkdf_expand(prk, b'', 42).hex(),
                         '8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8')
