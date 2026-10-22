"""Content-cache regressions using tiny temporary schemas; no study execution."""
from copy import deepcopy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from jsonschema import Draft202012Validator

from puf_snn.experiments import majority3_auth_v1 as week7
from puf_snn.experiments import three_arm_auth_v1 as week8


class SchemaCacheTests(unittest.TestCase):
    def setUp(self):
        self.checkout = week8.ROOT
        self.root = Path(self.enterContext(TemporaryDirectory(dir=self.checkout / "tmp")))
        (self.root / "schemas").mkdir()
        self.enterContext(patch.object(week7, "ROOT", self.root))
        self.enterContext(patch.object(week8, "ROOT", self.root))
        week7._checked_schema_validator.cache_clear()
        self.addCleanup(week7._checked_schema_validator.cache_clear)

    def path(self, module, kind="attempt"):
        if module is week8:
            name = f"three-arm-auth-{kind}-v1.schema.json"
        else:
            revision = 2 if kind in ("attempt", "summary") else 1
            name = f"majority3-auth-{kind}-v{revision}.schema.json"
        return self.root / "schemas" / name

    def message(self, module, kind="attempt"):
        return f"invalid {'three-arm ' if module is week8 else ''}{kind} schema"

    def uncached(self, module, kind, obj):
        # The pre-correction implementation, including exhaustive iter_errors.
        schema = week7.read_json_bytes(self.path(module, kind).read_bytes())
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(obj))
        week7.require(not errors, self.message(module, kind))

    def outcome(self, operation):
        try:
            return operation()
        except Exception as error:
            return type(error), str(error)

    def test_identical_bytes_share_one_checked_validator_but_validate_every_instance(self):
        data = b'{"type":"object","required":["accepted"],"properties":{"accepted":{"const":true}}}'
        for module in (week7, week8):
            self.path(module).write_bytes(data)
        instances = []

        def construct(schema):
            real = Draft202012Validator(schema)
            wrapped = SimpleNamespace(iter_errors=Mock(wraps=real.iter_errors))
            instances.append(wrapped)
            return wrapped

        constructor = Mock(side_effect=construct)
        constructor.check_schema = Mock(wraps=Draft202012Validator.check_schema)
        with patch.object(week7, "Draft202012Validator", constructor), \
             patch.object(week8, "Draft202012Validator", constructor), \
             patch.object(week7, "read_json_bytes", wraps=week7.read_json_bytes) as parse:
            for _ in range(2):
                for module in (week7, week8):
                    obj = {"accepted": True}
                    module.validate_schema("attempt", obj)
                    # A previously valid instance is mutated; no result caching.
                    obj["accepted"] = "private sentinel"
                    with self.assertRaises(ValueError) as caught:
                        module.validate_schema("attempt", obj)
                    self.assertEqual(str(caught.exception), self.message(module))
            self.assertEqual(parse.call_count, 1)
        self.assertEqual(constructor.check_schema.call_count, 1)
        self.assertEqual(constructor.call_count, 1)
        self.assertEqual(instances[0].iter_errors.call_count, 8)
        info = week7._checked_schema_validator.cache_info()
        self.assertEqual((info.hits, info.misses, info.currsize), (7, 1, 1))

    def test_same_size_same_mtime_edits_and_atomic_replacement_use_new_content(self):
        for module in (week7, week8):
            with self.subTest(module=module.__name__):
                path = self.path(module)
                original = b'{"type":"number"}'
                changed = b'{"type":"string"}'
                self.assertEqual(len(original), len(changed))
                path.write_bytes(original)
                module.validate_schema("attempt", 7)
                stamp = path.stat()
                path.write_bytes(changed)
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                module.validate_schema("attempt", "new")
                with self.assertRaises(ValueError):
                    module.validate_schema("attempt", 7)
                replacement = path.with_suffix(".replacement")
                replacement.write_bytes(b'{"const":false}')
                replacement.replace(path)
                module.validate_schema("attempt", False)
                with self.assertRaises(ValueError):
                    module.validate_schema("attempt", "new")
                # Restoring exact verified bytes may safely reuse the old entry.
                path.write_bytes(original)
                module.validate_schema("attempt", 7)

    def test_whitespace_change_is_a_miss_and_equal_content_at_other_path_is_a_hit(self):
        self.path(week8).write_bytes(b'{"type":"integer"}')
        week8.validate_schema("attempt", 1)
        self.path(week8, "summary").write_bytes(self.path(week8).read_bytes())
        week8.validate_schema("summary", 2)
        self.path(week8).write_bytes(b'{ "type":"integer" }')
        week8.validate_schema("attempt", 3)
        info = week7._checked_schema_validator.cache_info()
        self.assertEqual((info.hits, info.misses, info.currsize), (1, 2, 2))

    def test_missing_and_malformed_files_never_fall_back_to_a_warm_validator(self):
        malformed = (b'{', b'{"type":"unknown"}', b'{"type":"number","type":"string"}',
                     b'{"const":NaN}', b'\xff')
        for module in (week7, week8):
            for data in malformed:
                with self.subTest(module=module.__name__, data=data):
                    week7._checked_schema_validator.cache_clear()
                    path = self.path(module)
                    path.write_bytes(b'{"type":"object"}')
                    module.validate_schema("attempt", {})
                    path.write_bytes(data)
                    expected = self.outcome(lambda: self.uncached(module, "attempt", {}))
                    for _ in range(2):
                        actual = self.outcome(lambda: module.validate_schema("attempt", {}))
                        self.assertEqual(actual, expected)
                    self.assertIsNotNone(expected)
                    self.assertEqual(week7._checked_schema_validator.cache_info().currsize, 1)
                    path.unlink()
                    expected = self.outcome(lambda: self.uncached(module, "attempt", {}))
                    actual = self.outcome(lambda: module.validate_schema("attempt", {}))
                    self.assertEqual(actual, expected)
                    self.assertIs(expected[0], FileNotFoundError)
                    path.write_bytes(b'{"type":"object"}')
                    module.validate_schema("attempt", {})

    def test_real_schema_errors_and_canonical_instance_bytes_match_uncached_behavior(self):
        for module in (week7, week8):
            for kind in ("config", "plan", "attempt", "summary"):
                with self.subTest(module=module.__name__, kind=kind):
                    path = self.path(module, kind)
                    path.write_bytes((self.checkout / "schemas" / path.name).read_bytes())
                    obj = {"private sentinel": [True, 1, None]}
                    before = week7.canonical(obj)
                    expected = self.outcome(lambda: self.uncached(module, kind, obj))
                    self.assertEqual(expected, (ValueError, self.message(module, kind)))
                    for _ in range(2):
                        self.assertEqual(self.outcome(lambda: module.validate_schema(kind, obj)), expected)
                        self.assertEqual(week7.canonical(obj), before)

    def test_cold_and_warm_semantics_match_for_boolean_and_nested_schemas(self):
        schemas = (True, False, {"type": "integer"},
                   {"type": "array", "items": {"type": "number"}, "minItems": 1},
                   {"oneOf": [{"const": 1}, {"type": "boolean"}]},
                   {"$defs": {"n": {"type": "integer"}}, "$ref": "#/$defs/n"})
        for module in (week7, week8):
            for schema in schemas:
                self.path(module).write_bytes(week7.canonical(schema))
                for obj in (None, True, 1, "a", [], [1], ["a"], {}):
                    with self.subTest(module=module.__name__, schema=schema, obj=obj):
                        original = deepcopy(obj)
                        expected = self.outcome(lambda: self.uncached(module, "attempt", obj))
                        for _ in range(2):
                            self.assertEqual(self.outcome(lambda: module.validate_schema("attempt", obj)), expected)
                        self.assertEqual(obj, original)

    def test_validator_class_is_part_of_identity(self):
        data = b'{"type":"integer"}'
        first, second = Mock(wraps=Draft202012Validator), Mock(wraps=Draft202012Validator)
        a = week7._checked_schema_validator(data, first)
        self.assertIs(week7._checked_schema_validator(data, first), a)
        self.assertIsNot(week7._checked_schema_validator(data, second), a)
        self.assertEqual((first.call_count, second.call_count), (1, 1))

    def test_lru_bound_eviction_and_explicit_clear_recheck_definitions(self):
        cache = week7._checked_schema_validator
        limit = cache.cache_info().maxsize
        self.assertEqual(limit, 16)
        first = b'{"const":0}'
        a = cache(first, Draft202012Validator)
        for i in range(1, limit + 1):
            cache(week7.canonical({"const": i}), Draft202012Validator)
        self.assertEqual(cache.cache_info().currsize, limit)
        self.assertIsNot(cache(first, Draft202012Validator), a)
        cache.cache_clear()
        self.assertEqual(cache.cache_info().currsize, 0)
        with patch.object(Draft202012Validator, "check_schema",
                          wraps=Draft202012Validator.check_schema) as check:
            cache(first, Draft202012Validator)
        check.assert_called_once()


if __name__ == "__main__":
    unittest.main()
