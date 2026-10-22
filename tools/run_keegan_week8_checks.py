"""Save scoped root-discovery test receipts without requiring step-by-step commits.

This is a developer test run, not a historical experiment replay or benchmark.
Raw output stays locally ignored; summary and exact current source pins can be
reviewed separately. No test assertions, policies or historical results change.
"""

import argparse
import hashlib
import importlib
import io
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src/python"), str(ROOT / "tests")]
from puf_snn.quality_validation import source_hashes


def ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from ids(test)
        else:
            yield test.id()


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed_ids = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed_ids.append(test.id())


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    scope = (ROOT / "results/week-8/keegan").resolve()
    if output == scope or not output.is_relative_to(scope) or output.exists():
        raise ValueError("choose a new output below results/week-8/keegan; preserve old runs")
    output.mkdir(parents=True, exist_ok=False)
    (output / ".gitignore").write_text("*.private.log\n", encoding="utf-8", newline="\n")
    (output / ".gitattributes").write_text("* text eol=lf\n", encoding="utf-8", newline="\n")
    write_json(output / "INCOMPLETE", dict(note="Test execution has not finished. Retain partial evidence."))
    pinned = source_hashes(ROOT)
    write_json(output / "source-hashes.json", pinned)
    pip = subprocess.run([sys.executable, "-B", "-m", "pip", "check"], capture_output=True, text=True)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test*.py")
    selected = list(ids(suite))
    with (output / "test-output.private.log").open("x", encoding="utf-8", newline="\n") as log:
        log.write(pip.stdout + pip.stderr + "\n")
        result = unittest.TextTestRunner(stream=log, verbosity=2, resultclass=RecordedResult).run(suite)
    outside = [name for name, module in sys.modules.items() if (name == "puf_snn" or name.startswith("puf_snn."))
               and getattr(module, "__file__", None)
               and not Path(module.__file__).resolve().is_relative_to(ROOT / "src/python")]
    unchanged = source_hashes(ROOT) == pinned
    status = "PASS" if result.wasSuccessful() and not outside and unchanged and pip.returncode == 0 else "FAIL"
    summary = dict(status=status, scope="unittest root discovery; not every repository subdirectory",
        python=platform.python_version(), dependency_check_exit_code=pip.returncode,
        tests_selected=len(selected), tests_run=result.testsRun, tests_passed=len(result.passed_ids),
        unique_test_ids=len(set(selected)), skipped_ids=[test.id() for test, _ in result.skipped],
        failures=[test.id() for test, _ in result.failures], errors=[test.id() for test, _ in result.errors],
        expected_failures=[test.id() for test, _ in result.expectedFailures],
        unexpected_successes=[test.id() for test in result.unexpectedSuccesses],
        selected_test_ids=selected, source_unchanged=unchanged, project_imports_from_current_source=not outside,
        runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        excluded_nonpackage_test_directories=[path.name for path in sorted((ROOT / "tests").iterdir())
            if path.is_dir() and path.name != "__pycache__" and not (path / "__init__.py").is_file()],
        note="Fixture fitting/inference can occur inside unit tests; saved models are not retrained and test duration is not pipeline latency.")
    write_json(output / "summary.json", summary)
    print(json.dumps({key: summary[key] for key in ("status", "tests_run", "tests_passed", "skipped_ids", "failures", "errors")}), flush=True)
    if status == "PASS":
        write_json(output / "COMPLETE", dict(summary_sha256=hashlib.sha256((output / "summary.json").read_bytes()).hexdigest()))
        (output / "INCOMPLETE").unlink()
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
