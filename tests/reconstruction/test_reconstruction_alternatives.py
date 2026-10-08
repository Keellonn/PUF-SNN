"""Deterministic independent algebra and candidate-boundary tests; synthetic only."""
from dataclasses import replace
from itertools import product
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/python'))
from puf_snn import reconstruction_alternatives as a
from puf_snn.reconstruction import BCHCodec, DEFAULT_CONFIG


def bits(value,width):
    return tuple(map(int,f'{value:0{width}b}'))


def poly_remainder(value,divisor):
    while value.bit_length()>=divisor.bit_length():
        value ^= divisor << (value.bit_length()-divisor.bit_length())
    return value


def independent_generator():
    # Integer GF(64) arithmetic; no galois or production encoder calls.
    def multiply(x,y):
        value=0
        while y:
            if y&1: value ^= x
            y >>= 1
            x <<= 1
            if x&64: x ^= 0x43
        return value
    powers=[1]
    for _ in range(63): powers.append(multiply(powers[-1],2))
    assert len(set(powers[:63]))==63 and powers[-1]==1
    roots=set()
    for i in range(1,13):
        j=i
        while j not in roots:
            roots.add(j)
            j=j*2%63
    coefficients=[1]
    for exponent in sorted(roots):
        result=[0]*(len(coefficients)+1)
        for j,c in enumerate(coefficients):
            result[j] ^= multiply(c,powers[exponent])
            result[j+1] ^= c
        coefficients=result
    assert set(coefficients)<= {0,1}
    return sum(c<<j for j,c in enumerate(coefficients))


class AlternativesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codec=a.ExperimentalBCHCodec()
        cls.codec.initialize()

    def test_all_majority_truth_tables(self):
        for m in (3,5):
            for pattern in product((0,1),repeat=m):
                reads=tuple((v,)*64 for v in pattern)
                self.assertEqual(a.majority_vote(reads),(int(sum(pattern)>m//2),)*64)
                self.assertEqual(reads,tuple((v,)*64 for v in pattern))

    def test_vote_input_validation(self):
        for reads in ((),((0,)*64,),((0,)*64,)*2,((0,)*64,)*4,[(0,)*64]*3,
                      ((0,)*63,)*3,((False,)+(0,)*63,)*3,((2,)*64,)*3):
            with self.subTest(reads=len(reads)), self.assertRaises(ValueError): a.majority_vote(reads)

    def test_independent_generator_and_basis(self):
        g=independent_generator()
        self.assertEqual(g,0x37CD0EB67)
        self.assertEqual(g.bit_length()-1,33)
        self.assertEqual(poly_remainder((1<<63)|1,g),0)
        for j in range(30):
            shifted=(1<<j)<<33
            expected=shifted ^ poly_remainder(shifted,g)
            self.assertEqual(self.codec.encode(bits(1<<j,30)),bits(expected,63))

    def test_exact_algebra(self):
        b=a._backend()
        self.assertEqual((b.n,b.k,b.d,b.t,int(b.generator_poly)),(63,30,13,6,0x37CD0EB67))
        self.assertEqual((int(b.extension_field.irreducible_poly),int(b.alpha),b.c),(0x43,2,1))
        self.assertTrue(b.is_systematic and b.is_narrow_sense and b.is_primitive)

    def test_known_six_error_fixture(self):
        message=(1,)+(0,)*28+(1,)
        word=tuple(map(int,'100000000000000000000000000001011000010101110001001111011010100'))
        self.assertEqual(self.codec.encode(message),word)
        received=tuple(v^int(j in (0,10,20,30,40,62)) for j,v in enumerate(word))
        result=self.codec.decode(received)
        self.assertEqual(result.corrected_codeword,word)
        self.assertEqual(result.reported_correction_count,6)

    def test_every_single_position_and_fixed_boundaries(self):
        word=self.codec.encode(bits(0x12345678,30))
        for positions in [(j,) for j in range(63)]+[tuple(range(n)) for n in range(7)]:
            result=self.codec.decode(tuple(v^int(j in positions) for j,v in enumerate(word)))
            self.assertEqual(result.corrected_codeword,word)
            self.assertEqual(result.reported_correction_count,len(positions))

    def test_beyond_radius_declared_failure(self):
        result=self.codec.decode((1,)*7+(0,)*56)
        self.assertEqual(result.status,'uncorrectable')
        self.assertIsNone(result.candidate_message)

    def test_beyond_radius_wrong_candidate(self):
        # Actual enrollment word is zero. Received is six away from a different codeword.
        wrong=self.codec.encode(bits(1,30))
        received=tuple(v^int(j<6) for j,v in enumerate(wrong))
        self.assertGreater(sum(received),6)
        result=self.codec.decode(received)
        self.assertEqual(result.corrected_codeword,wrong)
        self.assertEqual(result.reported_correction_count,6)
        helper=a.enroll((0,)*64,bytes(4),enrollment_id='synthetic')
        candidate=a.reconstruct(received+(0,),helper)
        self.assertEqual(candidate.candidate_credential,b'\x00\x00\x00\x01')
        self.assertEqual(candidate.outcome,'candidate_valid_format')
        self.assertIsNone(candidate.padding_valid)

    def test_credential_representation(self):
        for value in [0,2**30-1,0x12345678]+[1<<j for j in range(30)]:
            data=value.to_bytes(4,'big')
            self.assertEqual(a.credential_to_message(data),bits(value,30))
            self.assertEqual(a.message_to_credential(bits(value,30)),data)
        for data in (bytes(3),bytes(5),bytearray(4),b'\x40\0\0\0',b'\xff'*4):
            with self.assertRaises(ValueError): a.credential_to_message(data)

    def test_enrollment_and_omitted_position(self):
        reference=(1,0)*32
        credential=b'\x12\x34\x56\x78'
        helper=a.enroll(reference,credential,enrollment_id='synthetic')
        word=self.codec.encode(a.credential_to_message(credential))
        self.assertEqual(helper.helper_bits,tuple(x^y for x,y in zip(reference,word)))
        for response in (reference,reference[:63]+(1-reference[63],)):
            self.assertEqual(a.reconstruct(response,helper).candidate_credential,credential)

    def test_changed_parameters_and_foreign_helpers_refused(self):
        with self.assertRaises(ValueError): replace(a.CONFIG,k=36)
        with self.assertRaises(ValueError): a.ExperimentalHelper((0,)*63,'x',DEFAULT_CONFIG)
        with self.assertRaises(ValueError): a.reconstruct((0,)*64,object())
        with self.assertRaises(ValueError): a.enroll((0,)*63,bytes(4),enrollment_id='x')
        with self.assertRaises(ValueError): self.codec.encode((False,)*30)
        with self.assertRaises(ValueError): self.codec.decode((0,)*62)

    def test_backend_declared_failure_payload_discarded(self):
        with patch.object(a,'_backend') as backend:
            backend.return_value.decode.return_value=(np.ones(63,dtype=int),-1)
            result=self.codec.decode((0,)*63)
            self.assertIsNone(result.candidate_message)
            self.assertIsNone(result.corrected_codeword)

    def test_backend_count_shape_and_consistency_checks(self):
        for word,count in [(np.zeros(63,dtype=int),True),(np.zeros(63,dtype=int),7),
                           (np.zeros(62,dtype=int),0),(np.full(63,2),0),
                           (np.zeros(63,dtype=int),1),(np.array([1]+[0]*62),1)]:
            with self.subTest(count=count,shape=word.shape),patch.object(a,'_backend') as backend:
                backend.return_value.decode.return_value=(word,count)
                with self.assertRaises(RuntimeError): self.codec.decode((0,)*63)

    def test_encoder_consistency_and_exceptions(self):
        with patch.object(a,'_backend') as backend:
            backend.return_value.encode.return_value=np.zeros(63,dtype=int)
            with self.assertRaises(RuntimeError): self.codec.encode((1,)*30)
            backend.return_value.decode.side_effect=RuntimeError('synthetic')
            with self.assertRaises(RuntimeError): self.codec.decode((0,)*63)

    def test_production_identity_unchanged(self):
        self.assertEqual((BCHCodec.k,BCHCodec.t,DEFAULT_CONFIG.padding),(36,5,(0,0,0,0)))


if __name__=='__main__': unittest.main()