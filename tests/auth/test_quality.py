"""Valid tags deliberately reach post-auth quality checks; no attack experiment."""
import unittest

from puf_snn.auth.binary_window import encode_window, U16, U32, U64, tracking_ppm
try:
    from .support import setup, window, wrap, offsets, mutate
except ImportError:
    from support import setup, window, wrap, offsets, mutate


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.v,self.sid,self.key=setup()
        self.a=encode_window(window(self.sid));self.o=offsets(self.a)

    def verify(self, a, accepted=False, schema=False):
        r=self.v.verify_window(wrap(a,self.sid,self.key))
        self.assertEqual(r.reason,'accepted' if accepted else 'invalid_payload_schema' if schema else 'data_quality_failure')
        self.assertEqual(self.v.audit_records[-1]['authentication_result'],'not_checked' if schema else 'pass')
        if not accepted: self.assertEqual(self.v.session_status(self.sid).accepted_count,0)

    def test_tracking_120(self): self.verify(self.a,True)

    def tracking(self,count):
        a=mutate(self.a,self.o['count'],U16(count))
        a=mutate(a,self.o['ppm'],U32(tracking_ppm(count)))
        for i in range(count,120): a=mutate(a,self.o['sample']+39*i+38,b'\x00')
        return a

    def test_tracking_114(self): self.verify(self.tracking(114),True)
    def test_tracking_113(self): self.verify(self.tracking(113))
    def test_tracking_summary_mismatch(self): self.verify(mutate(self.a,self.o['count'],U16(119)))
    def test_tracking_summary_width_only_before_hmac(self): self.verify(mutate(self.a,self.o['count'],U16(65535)))
    def test_ppm_mismatch(self): self.verify(mutate(self.a,self.o['ppm'],U32(999999)))
    def test_timestamp_outside(self): self.verify(mutate(self.a,self.o['sample']+2,U64(999999999)))
    def test_timestamp_equal_end(self): self.verify(mutate(self.a,self.o['sample']+119*39+2,U64(3000000000)))
    def test_timestamp_nonmonotonic(self): self.verify(mutate(self.a,self.o['sample']+39+2,U64(1000000000)))
    def test_excessive_gap(self): self.verify(mutate(self.a,self.o['sample']+39+2,U64(1050000001)))
    def test_end_before_start(self): self.verify(mutate(self.a,self.o['end'],U64(900000000)))
    def test_duration_plus_120(self): self.verify(mutate(self.a,self.o['end'],U64(3000000120)),True)
    def test_duration_minus_120(self): self.verify(mutate(self.a,self.o['end'],U64(2999999880)),True)
    def test_duration_plus_121(self): self.verify(mutate(self.a,self.o['end'],U64(3000000121)))
    def test_duration_minus_121(self): self.verify(mutate(self.a,self.o['end'],U64(2999999879)))

    def q(self, words, sample=0):
        return mutate(self.a,self.o['sample']+sample*39+22,b''.join(U32(w) for w in words))

    def test_quaternion_component_inside(self): self.verify(self.q((0,0,0,0x3f800008)),True)
    def test_quaternion_component_outside(self): self.verify(self.q((0,0,0,0x3f800009)))
    def test_quaternion_norm_lower_inside(self): self.verify(self.q((0,0,0,0x3f7ff973)),True)
    def test_quaternion_norm_lower_outside(self): self.verify(self.q((0,0,0,0x3f7ff972)))
    # Adjacent words bracketing sqrt((10001/10000)^2 - 1), independently
    # calculated with struct + Fraction; w=1 so components remain in bounds.
    def test_quaternion_norm_upper_inside(self): self.verify(self.q((0x3c67b5e6,0,0,0x3f800000)),True)
    def test_quaternion_norm_upper_outside(self): self.verify(self.q((0x3c67b5e7,0,0,0x3f800000)))
    def test_quaternion_sign_continuity(self): self.verify(self.q((0,0,0,0xbf800000),1))
    def test_structural_negative_zero(self): self.verify(self.q((0x80000000,0,0,0x3f800000)),schema=True)
    def test_sample_index_representation(self): self.verify(mutate(self.a,self.o['sample'],U16(1)),schema=True)
