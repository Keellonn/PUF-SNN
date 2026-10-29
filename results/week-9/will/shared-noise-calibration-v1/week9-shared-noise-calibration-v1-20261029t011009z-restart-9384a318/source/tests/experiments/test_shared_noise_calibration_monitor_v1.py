"""Week 9 monitoring concurrency only; native runs use isolated 16-attempt fixtures."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"src/python"))
from puf_snn.experiments import shared_noise_calibration_monitor_v1 as io
from puf_snn.experiments import shared_noise_calibration_resources_v1 as resources
from puf_snn.experiments import shared_noise_calibration_evidence_v1 as evidence
from puf_snn.experiments import shared_noise_calibration_v1 as study
from puf_snn.experiments import shared_noise_calibration_authorization_v2 as auth

NATIVE_MONITOR_FIXTURES = []
CONCURRENCY_RESULTS = []


def windows_error(code):
    error = OSError("deterministic replacement fault")
    error.winerror = code
    return error


class RetryTests(unittest.TestCase):
    def test_transient_replacement_retries_same_staged_data(self):
        ticks = [0.0]
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
            path=Path(temp)/"monitor.json"
            actual=io._replace_once
            observations=[]
            def replace(candidate,target):
                observations.append(candidate.read_bytes())
                if len(observations)<3: raise windows_error(32)
                actual(candidate,target)
            with patch.object(io,"_replace_once",side_effect=replace),patch.object(io.time,"monotonic",side_effect=lambda:ticks[0]),patch.object(io.time,"sleep",side_effect=lambda delay:ticks.__setitem__(0,ticks[0]+delay)):
                io.save_json(path,dict(value=7))
            self.assertEqual(len(observations),3)
            self.assertTrue(all(v==observations[0] for v in observations))
            self.assertEqual(io.read_json(path),dict(value=7))

    def test_persistent_replacement_has_attempt_cap_and_deadline(self):
        for code in sorted(io.RETRYABLE_WINERRORS):
            ticks=[0.0]
            with patch.object(io,"_replace_once",side_effect=windows_error(code)) as replace,patch.object(io.time,"monotonic",side_effect=lambda:ticks[0]),patch.object(io.time,"sleep",side_effect=lambda delay:ticks.__setitem__(0,ticks[0]+delay)):
                with self.assertRaises(OSError):io._replace_bounded(Path("candidate"),Path("target"))
                self.assertLessEqual(replace.call_count,6)
                self.assertLessEqual(ticks[0],.05)
                self.assertGreater(replace.call_count,1)

    def test_scheduler_overrun_does_not_attempt_after_deadline(self):
        ticks=[0.0]
        with patch.object(io,"_replace_once",side_effect=windows_error(32)) as replace,patch.object(io.time,"monotonic",side_effect=lambda:ticks[0]),patch.object(io.time,"sleep",side_effect=lambda delay:ticks.__setitem__(0,.2)):
            with self.assertRaises(OSError):io._replace_bounded(Path("candidate"),Path("target"))
            self.assertEqual(replace.call_count,1)

    def test_nonsharing_errors_and_interruptions_are_not_retried(self):
        for error in (windows_error(112),windows_error(1176),KeyboardInterrupt()):
            with patch.object(io,"_replace_once",side_effect=error) as replace,patch.object(io.time,"sleep") as sleep:
                with self.assertRaises(type(error)):io._replace_bounded(Path("candidate"),Path("target"))
                self.assertEqual(replace.call_count,1);sleep.assert_not_called()

    def test_privately_loaded_supervisor_only_is_adapted(self):
        p=resources.primitives()
        spec=importlib.util.spec_from_file_location("_unchanged_historical_monitor_test",ROOT/"tools/profile_three_arm_resources_v1.py")
        historical=importlib.util.module_from_spec(spec);sys.modules[spec.name]=historical;spec.loader.exec_module(historical)
        self.assertIs(p.save_json,io.save_json);self.assertIs(p.read_json,io.read_json)
        self.assertIsNot(historical.save_json,io.save_json)
        self.assertIsNot(historical.read_json,io.read_json)
        self.assertEqual(Path(p.__file__).resolve(),Path(historical.__file__).resolve())

    def test_status_is_read_only_and_never_authorizes(self):
        output=evidence.OUTPUT_ROOT/(study.VERSION+"-status-test-absent")
        with patch.object(auth,"reserve_approval",side_effect=AssertionError("status must not authorize")):
            result=resources.monitoring_status(output)
        self.assertTrue(result["diagnostic_only"])
        self.assertIsNone(result["monitor"])
        self.assertFalse(output.exists())

    def test_status_cli_does_not_dispatch_execution(self):
        output=evidence.OUTPUT_ROOT/(study.VERSION+"-status-cli-test-absent")
        result=subprocess.run([sys.executable,str(resources.CLI),"status","--output",str(output)],capture_output=True,text=True,check=True)
        self.assertIsNone(json.loads(result.stdout)["monitor"])
        self.assertFalse(output.exists())


@unittest.skipUnless(os.name=="nt","native Windows sharing semantics")
class WindowsSharingTests(unittest.TestCase):
    def test_lock_contention_is_bounded_and_exception_releases_mutex(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
            path=Path(temp)/"monitor.json";io.save_json(path,dict(sequence=0))
            def contender():
                with self.assertRaises(TimeoutError):io.read_json(path)
            with ThreadPoolExecutor(max_workers=1) as pool:
                with io._guard(path):pool.submit(contender).result(timeout=2)
            with self.assertRaises(RuntimeError):
                with io._guard(path):raise RuntimeError('fixture interruption')
            io.save_json(path,dict(sequence=1))
            self.assertEqual(io.read_json(path)['sequence'],1)

    def test_held_snapshot_preserves_old_bytes_without_a_live_file_handle(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
            path=Path(temp)/"monitor.json";io.save_json(path,dict(sequence=0))
            with io.snapshot_reader(path) as held:
                for sequence in range(1,21):io.save_json(path,dict(sequence=sequence))
                self.assertEqual(json.loads(held.read()),dict(sequence=0))
                self.assertEqual(io.read_json(path),dict(sequence=20))

    def test_concurrent_periodic_writes_and_repeated_shared_reads(self):
        for name in ("monitor.json","progress.json"):
            with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
                path=Path(temp)/name
                io.save_json(path,dict(sequence=0,payload=[0]*100))
                started=threading.Barrier(3);finished=threading.Event();counts=[0,0]
                def reader(index):
                    started.wait()
                    while not finished.is_set() or counts[index]<100:
                        value=resources.primitives().read_json(path)
                        self.assertEqual(value["payload"],[value["sequence"]]*100)
                        counts[index]+=1
                with ThreadPoolExecutor(max_workers=2) as pool:
                    futures=[pool.submit(reader,index) for index in range(2)]
                    started.wait()
                    try:
                        for sequence in range(1,201):
                            resources.primitives().save_json(path,dict(sequence=sequence,payload=[sequence]*100))
                    finally:finished.set()
                    for future in futures:future.result(timeout=10)
                self.assertEqual(io.read_json(path)["sequence"],200)
                CONCURRENCY_RESULTS.append(dict(file=name,writes=200,read_counts=counts,errors=0))

    def test_temporarily_incompatible_reader_recovers_within_bounded_policy(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
            path=Path(temp)/"monitor.json";io.save_json(path,dict(sequence=0))
            blocked=threading.Event();actual=io._replace_once;failures=[]
            def replace(*args):
                try:return actual(*args)
                except OSError as error:failures.append(error.winerror);blocked.set();raise
            with path.open("rb") as incompatible,ThreadPoolExecutor(max_workers=1) as pool,patch.object(io,"_replace_once",side_effect=replace):
                future=pool.submit(io.save_json,path,dict(sequence=1))
                self.assertTrue(blocked.wait(2))
                incompatible.close()
                future.result(timeout=2)
            self.assertTrue(failures);self.assertEqual(io.read_json(path)["sequence"],1)

    def test_persistent_incompatible_reader_fails_and_preserves_both_versions(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
            path=Path(temp)/"monitor.json";io.save_json(path,dict(sequence=0))
            with path.open("rb"):
                began=time.monotonic()
                with self.assertRaises(OSError):io.save_json(path,dict(sequence=1))
                elapsed=time.monotonic()-began
            self.assertLess(elapsed,.5)  # Includes OS scheduling; policy itself is 50 ms.
            self.assertEqual(io.read_json(path)["sequence"],0)
            self.assertEqual(io.read_json(path.with_suffix(".json.new"))["sequence"],1)

    def test_read_parse_failure_and_size_limit_release_handles_and_mutex(self):
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp") as temp:
            path=Path(temp)/"monitor.json"
            for content in (b"{",b" "*(io.MAX_SNAPSHOT_BYTES+1)):
                path.write_bytes(content)
                with self.assertRaises(ValueError):io.read_json(path)
                # Original os.replace must succeed now: no reader handle leaked.
                replacement=path.with_suffix(".candidate");replacement.write_text('{}')
                os.replace(replacement,path)


def inspection_process(monitor,stop,result):
    """Separate process: hold one version and repeatedly inspect published versions."""
    deadline=time.monotonic()+45
    while not monitor.exists():
        if time.monotonic()>=deadline:raise TimeoutError("no monitored fixture")
        time.sleep(.005)
    reads=0;samples=set()
    with io.snapshot_reader(monitor) as held:
        first=held.read()
        while not stop.exists():
            snapshot=io.read_json(monitor)
            samples.add(snapshot['samples']);reads+=1
            if time.monotonic()>=deadline:raise TimeoutError("inspection stop missing")
            time.sleep(.002)
        held.seek(0)
        if held.read()!=first:raise AssertionError("held snapshot changed")
    io.save_json(result,dict(reads=reads,distinct_samples=len(samples),held_snapshot_unchanged=True,errors=0))


@unittest.skipUnless(os.name=="nt","native Windows supervised monitoring fixtures")
class NativeMonitoringTests(unittest.TestCase):
    def test_real_supervision_and_cross_process_status_inspection_complete_fixture(self):
        from experiments.test_shared_noise_calibration_authorization_v2 import fixture_config,fixture_approval
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="w9-monitor-success-") as temp:
            root=Path(temp);cfg=fixture_config();context,output,approval=fixture_approval(cfg,root,name="concurrent-status")
            monitor=context.sidecar_root/output.name/"worker/monitor.json"
            stop=root/"inspection-stop";inspection=root/"inspection-result.json"
            process=resources.primitives().launch_python([str(Path(__file__).resolve()),"_inspect",str(monitor),str(stop),str(inspection)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=ROOT)
            try:result=resources.execute(cfg,output,approval,fixture_root=root)
            finally:
                stop.touch()
                try:stdout,stderr=process.communicate(timeout=10)
                except subprocess.TimeoutExpired:process.kill();process.communicate();raise
            self.assertEqual(process.returncode,0,stderr.decode(errors='replace'))
            inspected=io.read_json(inspection)
            self.assertGreater(inspected['reads'],10);self.assertGreater(inspected['distinct_samples'],5)
            monitored=io.read_json(monitor.parent.parent/"monitor-result.json")
            self.assertTrue(monitored['success'] and monitored['supervision_verified']);self.assertEqual(monitored['violations'],[])
            marker=evidence.read_json(output/evidence.MARKER)
            self.assertEqual(marker['validation_passes_completed'],2)
            audit=evidence.audit_evidence(output);self.assertEqual(audit['status'],'PASS')
            self.assertEqual(result['status'],'completed-fixture-only')
            self.assertEqual(monitored['worker']['receipt']['arm_attempts'],16)
            with patch.object(resources,"_execute_reserved") as launch,self.assertRaises(ValueError):resources.execute(cfg,output,approval,fixture_root=root)
            launch.assert_not_called()
            NATIVE_MONITOR_FIXTURES.append(dict(kind='successful-cross-process-inspection',fixture_only=True,attempts=16,readings=32,decodes=16,monitor_samples=monitored['samples'],wall_seconds=monitored['launch_to_exit_wall_seconds'],sampled_peaks=monitored['sampled_peaks'],max_observed_sample_gap_seconds=monitored['max_observed_sample_gap_seconds'],violations=monitored['violations'],supervision_verified=monitored['supervision_verified'],inspection=inspected,two_pass_work=marker['finalization_validation_work'],audit=audit,consumed_authorization_reuse_refused=True))

    def test_persistent_monitor_failure_terminates_worker_retains_incomplete_and_consumes_fixture_authorization(self):
        from experiments.test_shared_noise_calibration_authorization_v2 import fixture_config,fixture_approval
        with tempfile.TemporaryDirectory(dir=ROOT/"tmp",prefix="w9-monitor-failure-") as temp:
            root=Path(temp);cfg=fixture_config();context,output,approval=fixture_approval(cfg,root,name="persistent-status-lock")
            p=resources.primitives();actual=io._replace_once;launch=p.launch_python
            held=[];processes=[];errors=[]
            def capture_launch(*args,**kwargs):
                process=launch(*args,**kwargs);processes.append(process);return process
            def replace(candidate,target):
                ledger=output/"attempts.jsonl"
                if target.name=="monitor.json" and target.exists() and ledger.exists() and ledger.stat().st_size>0:
                    if not held:held.append(target.open('rb'))
                try:return actual(candidate,target)
                except OSError as error:errors.append(error.winerror);raise
            try:
                with patch.object(io,"_replace_once",side_effect=replace),patch.object(p,"launch_python",side_effect=capture_launch):
                    with self.assertRaises(OSError):resources.execute(cfg,output,approval,fixture_root=root)
            finally:
                for stream in held:stream.close()
            self.assertTrue(errors);self.assertLessEqual(len(errors),io.REPLACE_MAX_ATTEMPTS)
            self.assertTrue(processes);self.assertTrue(all(process.poll() is not None for process in processes))
            self.assertTrue((output/'INCOMPLETE.json').exists());self.assertFalse((output/evidence.MARKER).exists())
            ledger=output/'attempts.jsonl';before=ledger.read_bytes();count=len(before.splitlines())
            self.assertGreater(count,0)
            self.assertIsNotNone(auth.load_consumption(context,approval['authorization_id']))
            diagnostic=io.read_json(context.sidecar_root/output.name/'worker/controller-error.json')
            with patch.object(resources,"_execute_reserved") as launch,self.assertRaises(ValueError):resources.execute(cfg,output,approval,fixture_root=root)
            launch.assert_not_called();self.assertEqual(ledger.read_bytes(),before)
            NATIVE_MONITOR_FIXTURES.append(dict(kind='persistent-incompatible-reader',fixture_only=True,persisted_attempts=count,replacement_winerrors=errors,worker_terminated=True,incomplete_preserved=True,completion_marker=False,authorization_consumed=True,reuse_refused_without_launch=True,diagnostic=diagnostic))


if __name__=="__main__":
    if len(sys.argv)==5 and sys.argv[1]=='_inspect':inspection_process(*(Path(p) for p in sys.argv[2:]))
    else:unittest.main()
