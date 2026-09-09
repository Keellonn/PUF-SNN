from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "python"))

from scripts.run_puf_baseline import make_rng
from puf_snn.puf.device import Device, create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import ReadConditions

class DeviceTests(unittest.TestCase):
    def test_state_is_immutable(self) -> None:
        device = Device("device-0", (0.1, -0.2))
        with self.assertRaises(FrozenInstanceError):
            device.device_id = "other"
        with self.assertRaises(TypeError):
            device.manufacturing_variation[0] = 5.0

    def test_invalid_state_is_rejected(self) -> None:
        for device_id, offsets, aging in (
            ("", (0.0, 0.0), None),
            ("d", [0.0, 0.0], None),
            ("d", (0.0,), None),
            ("d", (float("nan"), 0.0), None),
            ("d", (0.0, 0.0), (0.0,)),
        ):
            with self.subTest(device_id=device_id, offsets=offsets, aging=aging):
                with self.assertRaises(ValueError):
                    Device(device_id, offsets, aging)

    def test_optional_aging_state(self) -> None:
        self.assertIsNone(Device("d", (1.0, -1.0)).aging_state)
        self.assertEqual(Device("d", (1.0, -1.0), (0.0, 0.0)).aging_state,
                         (0.0, 0.0))

    def test_manufacturing_persists_across_noisy_measurements(self) -> None:
        manufacturing_rng = make_rng(1234, 0, "manufacturing")
        device = create_device("d", 128, 1.0, rng=manufacturing_rng)
        original_offsets = device.manufacturing_variation
        original_state = manufacturing_rng.getstate()
        read_rng = make_rng(1234, 0, "measurement")
        pairs = generate_pairs(128, "adjacent")
        for _ in range(20):
            generate_response(device, pairs, 100.0, ReadConditions(0, 1),
                              rng=read_rng)
            self.assertIs(device.manufacturing_variation, original_offsets)
        self.assertEqual(manufacturing_rng.getstate(), original_state)

    def test_devices_are_distinct_and_reproducible(self) -> None:
        def manufacture() -> list[Device]:
            return [create_device(f"d-{index}", 128, 1.0,
                                  rng=make_rng(1234, index, "manufacturing"))
                    for index in range(3)]

        devices = manufacture()
        self.assertEqual(devices, manufacture())
        self.assertEqual(len({d.manufacturing_variation for d in devices}), 3)
        self.assertTrue(all(len(d.manufacturing_variation) == 128
                            for d in devices))

    def test_zero_manufacturing_spread_uses_no_draws(self) -> None:
        rng = make_rng(1234, 0, "manufacturing")
        before = rng.getstate()
        device = create_device("d", 4, 0.0, rng=rng)
        self.assertEqual(device.manufacturing_variation, (0.0,) * 4)
        self.assertEqual(rng.getstate(), before)

    def test_invalid_manufacturing_inputs(self) -> None:
        for identifier, count, spread in (
            (" ", 4, 1), (None, 4, 1), ("d", 1, 1),
            ("d", True, 1), ("d", 4.0, 1), ("d", 4, -1),
            ("d", 4, float("nan")), ("d", 4, float("inf")),
            ("d", 4, True),
        ):
            rng = make_rng(1234, 0, "manufacturing")
            before = rng.getstate()
            with self.subTest(identifier=identifier, count=count,
                              spread=spread):
                with self.assertRaises(ValueError):
                    create_device(identifier, count, spread, rng=rng)
                self.assertEqual(rng.getstate(), before)
        with self.assertRaisesRegex(ValueError, "rng"):
            create_device("d", 4, 1, rng=None)
