"""Opt-in bounded resource controller; no formal execution action.

Only stdlib is needed by controller/tests. Harness imports are lazy.
See docs/week8-three-arm-resource-profiler-v1.md before authorizing workers.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from dataclasses import asdict, dataclass
import functools
import gc
import hashlib
import io
import json
import math
from multiprocessing.connection import Client, Listener
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_ROOT = ROOT / 'results/week-8/will/three-arm-auth-v1/nonformal'
SIDECAR_ROOT = ROOT / 'tmp/week8-three-arm-resource-profile-v1'
PREFIX = 'week8-three-arm-auth-v1-nonformal-resource-v1-'
APPROVAL = 'PROFILE-150-RESOURCE-V1'
AUTHORIZATION = 'RUN-150-NONFORMAL'
VERSION = 'three-arm-resource-profiler-v1'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def save_json(path, obj):
    """Atomic sidecar replacement; never used for experiment evidence."""
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.new')
    temporary.write_text(json.dumps(obj, sort_keys=True, indent=2, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def unlinked(path):
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink() and not getattr(ancestor, 'is_junction', lambda: False)(),
                'linked path forbidden')
        require(ancestor.name.rstrip(' .') == ancestor.name and ':' not in ancestor.name,
                'path alias forbidden')
        require(not any((ancestor / marker).is_file() for marker in
                        ('manifest.json', 'source-manifest.json', 'INCOMPLETE.json')),
                'nested sealed/partial evidence path forbidden')
    return path


def layout(session, pairs, runs_per_pair, audits):
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,23}', session or '') is not None,
            'session must be a new lowercase token, 1..24 characters')
    require(type(pairs) is int and 1 <= pairs <= 3, 'one to three process pairs required')
    require(type(runs_per_pair) is int and runs_per_pair in (1, 2), 'one or two bundles per process required')
    require(pairs * runs_per_pair <= 6, 'six bundle cap')
    require(type(audits) is int and 0 <= audits <= min(3, pairs), 'three audit cap')
    require(not audits or runs_per_pair == 2, 'audits may target only second bundles')
    sidecar = unlinked(SIDECAR_ROOT / session)
    require(not sidecar.exists(), 'sidecar session collision; no resume or retry')
    bundles = [[unlinked(EVIDENCE_ROOT / f'{PREFIX}{session}-p{p}-{label}')
                for label in ('cold', 'warm')[:runs_per_pair]] for p in range(1, pairs + 1)]
    for path in sum(bundles, []):
        require(not path.exists(), 'evidence output collision')
        require(path.parent.resolve() == EVIDENCE_ROOT.resolve(), 'historical/nested output forbidden')
        require(not sidecar.is_relative_to(path) and not path.is_relative_to(sidecar),
                'sidecars and evidence must be separate')
    return sidecar, bundles


@dataclass(frozen=True)
class Budgets:
    # All limits must be selected explicitly; proposed budgets are not approvals.
    bundle_seconds: float
    session_seconds: float
    memory_bytes: int
    min_free_ram_bytes: int
    min_free_disk_bytes: int
    bundle_growth_bytes: int
    total_growth_bytes: int
    sample_seconds: float = 0.05
    stop_grace_seconds: float = 2.0

    def __post_init__(self):
        require(all(type(v) in (int, float) and math.isfinite(v) and v > 0
                    for v in asdict(self).values()), 'all budgets must be supplied, finite and positive')
        require(0.01 <= self.sample_seconds <= 1, 'sample interval must be 0.01..1 seconds')
        require(self.stop_grace_seconds <= 10, 'stop grace must be at most ten seconds')

    def violations(self, sample, *, phase_seconds, session_seconds, bundle_bytes, total_bytes):
        failures = []
        for value, limit, name in ((phase_seconds, self.bundle_seconds, 'bundle/audit deadline'),
                (session_seconds, self.session_seconds, 'session deadline'),
                (bundle_bytes, self.bundle_growth_bytes, 'bundle growth'),
                (total_bytes, self.total_growth_bytes, 'aggregate growth')):
            if value >= limit:
                failures.append(name)
        memory = [sample.get(k) for k in ('rss_bytes', 'private_bytes', 'os_peak_rss_bytes')]
        if not any(v is not None for v in memory):
            failures.append('required process memory metric unavailable')
        elif max(v for v in memory if v is not None) >= self.memory_bytes:
            failures.append('process memory')
        for key, minimum in (('free_ram_bytes', self.min_free_ram_bytes),
                             ('free_disk_bytes', self.min_free_disk_bytes)):
            if sample.get(key) is None:
                failures.append('required ' + key + ' unavailable')
            elif sample[key] <= minimum:
                failures.append(key)
        return failures


def harness():
    # Preflight imports must not create source-tree bytecode side effects.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(ROOT / 'src/python'))
    from puf_snn.experiments import three_arm_auth_v1 as study
    from puf_snn.experiments import three_arm_auth_evidence_v1 as evidence
    return study, evidence


def check_config(study, config, reviewed=None, *, require_review=False):
    obj = config.to_dict()
    require(obj['mode'] == 'nonformal', 'only existing nonformal configuration allowed')
    require(obj['allocation'] == dict(populations=1, devices_per_population=1,
            attempts_per_device_condition=10), 'allocation must be exactly 1 x 1 x 10')
    require(obj['execution_limits'] == dict(formal_execution_enabled=False,
            nonformal_max_matched_trials=50, nonformal_max_arm_attempts=150, retries=0),
            'incorrect attempt limit')
    require(obj['timing_methodology']['profile'] == 'cold-process-no-harness-warmup-v1'
            and obj['authentication']['warmup_iterations'] == 0, 'timing profile changed')
    plan = study.compile_plan(config)
    study.validate_plan(config, plan)
    require(plan['counts']['arm_attempts'] == 150 and plan['counts']['matched_trials'] == 50,
            'plan must contain exactly 150 arms / 50 matched trials')
    if require_review or reviewed is not None:
        require(reviewed == plan['plan_sha256'], 'invalid or missing reviewed plan hash')
    return plan


def check_approval(request):
    require(request.get('approval') == APPROVAL, 'explicit resource profiling approval required')
    require(request.get('authorization') == AUTHORIZATION, 'existing nonformal authorization required')
    require(not request.get('audits') or request.get('audit_approval') == 'AUDIT-RESOURCE-V1',
            'explicit standalone audit authorization required')


def selected_budgets(args):
    names = tuple(Budgets.__dataclass_fields__)
    required = names[:7]
    if args.action == 'execute' or any(getattr(args, name) is not None for name in required):
        return Budgets(**{name: getattr(args, name) for name in names})
    return None


def preflight(args, *, loader=harness):
    sidecar, bundles = layout(args.session, args.pairs, args.runs_per_pair, args.audits)
    if args.action == 'execute':
        check_approval(vars(args))
    budgets = selected_budgets(args)
    study, evidence = loader()
    config = study.StudyConfig.load(args.config)
    plan = check_config(study, config, args.reviewed_plan_sha256,
                        require_review=args.action != 'preflight')
    for path in sum(bundles, []):
        evidence.checked_output_path(path, 'nonformal')
    hashes = evidence.source_hashes()  # read only: no replay, enrollment, or EvidenceRun
    return dict(version=VERSION, config=str(Path(args.config).resolve()), config_byte_sha256=digest(args.config),
                config_sha256=config.digest, plan_sha256=plan['plan_sha256'], source_hashes=hashes,
                profiler_sha256=digest(__file__), formal_execution_enabled=False,
                sidecar=str(sidecar), bundles=[[str(p) for p in pair] for pair in bundles],
                planned_bundles=args.pairs * args.runs_per_pair, planned_audits=args.audits,
                budgets=asdict(budgets) if budgets else None, experiment_executed=False)


class StopRequested(BaseException):
    """Escape ordinary runtime Exception handlers, retaining incomplete evidence."""


class Measurements:
    def __init__(self, clock=time.perf_counter_ns):
        self.clock = clock
        self.stack = []
        self.phase = 'startup'
        self.totals = defaultdict(lambda: dict(calls=0, failures=0, inclusive_ns=0,
                                              exclusive_ns=0, logical_input_bytes=0))
        self.by_phase = defaultdict(lambda: defaultdict(lambda: dict(calls=0, failures=0,
            inclusive_ns=0, exclusive_ns=0, logical_input_bytes=0)))
        self.passes = []

    def begin(self, name, logical_bytes=0):
        item = [name, self.clock(), 0, logical_bytes, self.phase]
        self.stack.append(item)
        return item

    def end(self, item, failed=False):
        require(self.stack and self.stack[-1] is item, 'instrumentation nesting mismatch')
        elapsed = self.clock() - item[1]
        self.stack.pop()
        if self.stack:
            self.stack[-1][2] += elapsed
        for total in (self.totals[item[0]], self.by_phase[item[4]][item[0]]):
            total['calls'] += 1
            total['failures'] += int(failed)
            total['inclusive_ns'] += elapsed
            total['exclusive_ns'] += elapsed - item[2]
            total['logical_input_bytes'] += item[3]
        if item[0].startswith('file_hash'):
            # Attribute every digest input to each enclosing source scan. The outer
            # Week 8 total INCLUDES the inherited scan; do not sum both totals.
            for parent in self.stack:
                if parent[0].startswith('source_hashes'):
                    parent[3] += item[3]
        if item[0] in ('reconcile', 'finalize', 'audit', 'setup', 'population_setup', 'summary', 'bundle', 'imports'):
            self.passes.append(dict(name=item[0], phase=item[4], inclusive_ns=elapsed, failed=failed))

    @contextmanager
    def span(self, name):
        item = self.begin(name)
        failed = True
        try:
            yield
            failed = False
        finally:
            self.end(item, failed)

    def wrapper(self, original, name, byte_counter=None, boundary=None):
        @functools.wraps(original)
        def measured(*args, **kwargs):
            if boundary:
                boundary()
            size = 0
            if byte_counter:
                try:
                    size = byte_counter(*args, **kwargs)
                except OSError:
                    pass  # Preserve the delegated exception, including identity.
            item = self.begin(name, size)
            failed = True
            try:
                result = original(*args, **kwargs)
                failed = False
                return result
            finally:
                self.end(item, failed)
        return measured


@contextmanager
def patched(measurements, bindings, boundary=None):
    """Call each original exactly once; unwind even on BaseException."""
    saved = []
    try:
        for owner, attr, name, byte_counter, stop_boundary in bindings:
            original = getattr(owner, attr)
            setattr(owner, attr, measurements.wrapper(original, name, byte_counter,
                                                       boundary if stop_boundary else None))
            saved.append((owner, attr, original))
        yield
    finally:
        for owner, attr, original in reversed(saved):
            setattr(owner, attr, original)


@contextmanager
def io_schema_profile(measurements, validator):
    """Observe built-in write/flush/fsync and validator construction without proxies.

    Only the calling thread is profiled. Hook overhead affects observed timings.
    """
    require(sys.getprofile() is None, 'an existing profiler hook is unsupported')
    codes = {validator.__init__.__code__: 'validator_construction',
             validator.check_schema.__func__.__code__: 'schema_self_check'}
    active = []

    def profile(frame, event, arg):
        if event == 'call':
            name = codes.get(frame.f_code)
            if name:
                active.append((frame, measurements.begin(name)))
        elif event == 'return':
            if active and active[-1][0] is frame:
                measurements.end(active.pop()[1])
        elif event == 'c_call':
            name = getattr(arg, '__name__', '')
            owner = getattr(arg, '__self__', None)
            if arg is os.fsync or (name in ('write', 'flush') and isinstance(owner, io.IOBase)):
                active.append((arg, measurements.begin('fsync' if arg is os.fsync else name)))
        elif event in ('c_return', 'c_exception'):
            if active and active[-1][0] == arg:
                measurements.end(active.pop()[1], event == 'c_exception')

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(None)


def instrument_bindings(study, evidence):
    bindings = []
    for module, label in ((evidence, 'week8'), (evidence.previous, 'week7')):
        bindings += [(module, 'source_hashes', 'source_hashes_' + label, None, False),
                     (module, 'file_digest', 'file_hash_' + label,
                      lambda path: Path(path).stat().st_size, False)]
    for module, label in ((study, 'week8'), (study.previous, 'week7')):
        bindings += [(module, 'validate_schema', 'schema_' + label, None, False),
                     (module, 'canonical', 'canonical_' + label, None, False)]
    bindings += [(evidence.previous, 'canonical', 'canonical_evidence_week7', None, False)]
    bindings += [(evidence, name, label, None, stop) for name, label, stop in (
        ('execute_attempt', 'execute_attempt', True), ('reconcile', 'reconcile', True),
        ('summarize', 'summary', True), ('audit_evidence', 'audit', True),
        ('write_json', 'write_json', False))]
    bindings += [(evidence.EvidenceRun, name, label, None, stop) for name, label, stop in (
        ('__init__', 'setup', True), ('execute', 'execute_including_finalization', True),
        ('append', 'append', True), ('finalize', 'finalize', True))]
    bindings += [(study, 'prepare_population', 'population_setup', None, True)]
    return bindings


def tree_size(path):
    total = count = 0
    if Path(path).exists():
        for item in Path(path).rglob('*'):
            try:
                if item.is_file():
                    total += item.stat().st_size
                    count += 1
            except FileNotFoundError:
                pass  # Atomic sidecar/cache replacement or INCOMPLETE removal.
    return dict(logical_bytes=total, files=count)


class WindowsMetrics:
    """OS lifetime counters plus samples; logical I/O is not device throughput."""
    def __init__(self, pid):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.psapi = ctypes.WinDLL('psapi', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenProcess.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.OpenProcess(0x0400 | 0x0010, False, pid)

    def sample(self):
        result = dict(rss_bytes=None, private_bytes=None, os_peak_rss_bytes=None,
                      cpu_seconds=None, logical_io=None, free_ram_bytes=None)
        class Memory(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
                (k, ctypes.c_size_t) for k in ('peak', 'working', 'quota_peak_paged', 'quota_paged',
                'quota_peak_nonpaged', 'quota_nonpaged', 'pagefile', 'peak_pagefile', 'private')]
        memory = Memory()
        memory.cb = ctypes.sizeof(memory)
        self.psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        if self.handle and self.psapi.GetProcessMemoryInfo(self.handle, ctypes.byref(memory), memory.cb):
            result.update(rss_bytes=memory.working, private_bytes=memory.private,
                          os_peak_rss_bytes=memory.peak)
        class Times(ctypes.Structure):
            _fields_ = [('low', wintypes.DWORD), ('high', wintypes.DWORD)]
        times = [Times() for _ in range(4)]
        self.kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
        if self.handle and self.kernel.GetProcessTimes(self.handle, *(ctypes.byref(t) for t in times)):
            result['cpu_seconds'] = sum((t.high << 32) + t.low for t in times[2:]) / 1e7
        class IO(ctypes.Structure):
            _fields_ = [(k, ctypes.c_ulonglong) for k in ('read_ops', 'write_ops', 'other_ops',
                        'read_bytes', 'write_bytes', 'other_bytes')]
        counters = IO()
        self.kernel.GetProcessIoCounters.argtypes = [wintypes.HANDLE, ctypes.c_void_p]
        if self.handle and self.kernel.GetProcessIoCounters(self.handle, ctypes.byref(counters)):
            result['logical_io'] = {k: getattr(counters, k) for k, _ in IO._fields_}
        class Status(ctypes.Structure):
            _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD)] + [
                (k, ctypes.c_ulonglong) for k in ('total_ram', 'free_ram', 'total_page', 'free_page',
                    'total_virtual', 'free_virtual', 'free_extended')]
        status = Status()
        status.length = ctypes.sizeof(status)
        self.kernel.GlobalMemoryStatusEx.argtypes = [ctypes.c_void_p]
        if self.kernel.GlobalMemoryStatusEx(ctypes.byref(status)):
            result['free_ram_bytes'] = status.free_ram
            result['total_ram_bytes'] = status.total_ram
        return result

    def close(self):
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class JobBasicLimits(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', wintypes.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                ('active', wintypes.DWORD), ('affinity', ctypes.c_size_t),
                ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class JobLimits(ctypes.Structure):
    _fields_ = [('basic', JobBasicLimits), ('io', ctypes.c_ulonglong * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]


class ProcessTree:
    """Windows kill-on-close job; POSIX dedicated process group for stub tests."""
    def __init__(self, process):
        self.process = process
        self.job = None
        self.name = 'Local\\puf-snn-resource-' + uuid.uuid4().hex
        if os.name == 'nt':
            kernel = self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel.CreateJobObjectW.restype = wintypes.HANDLE
            kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
            kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            self.job = kernel.CreateJobObjectW(None, self.name)
            settings = JobLimits()
            settings.basic.flags = 0x2000
            if not (self.job and kernel.SetInformationJobObject(self.job, 9, ctypes.byref(settings),
                    ctypes.sizeof(settings)) and kernel.AssignProcessToJobObject(self.job, int(process._handle))):
                self.close()
                raise OSError('cannot contain process tree; worker remains gated')

    def close(self):
        if os.name == 'nt' and self.job:
            self.kernel.CloseHandle(self.job)
            self.job = None
        elif os.name != 'nt':
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def terminate(process, tree):
    if tree:
        tree.close()
    if process.poll() is None:
        process.kill()
    process.wait()
    if process.stdin and not process.stdin.closed:
        process.stdin.close()


def error_detail(stage, exc):
    return dict(stage=stage, type=type(exc).__name__, message=str(exc)[:2000])


def diagnostic(path, detail):
    """Best effort only; an I/O failure must not replace the original exception."""
    try:
        save_json(path, dict(success=False, error=detail))
    except (OSError, ValueError):
        pass


def request_digest(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, allow_nan=False).encode()).hexdigest()


def pipe_send(connection, message):
    connection.send_bytes(json.dumps(message, allow_nan=False).encode())


def pipe_receive(connection):
    return json.loads(connection.recv_bytes(65536))


def pipe_peer_pid(connection, *, server):
    require(os.name == 'nt', 'verified supervision requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    function = getattr(kernel, 'GetNamedPipeClientProcessId' if server else 'GetNamedPipeServerProcessId')
    function.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.ULONG)]
    function.restype = wintypes.BOOL
    pid = wintypes.ULONG()
    if not function(connection.fileno(), ctypes.byref(pid)):
        raise ctypes.WinError(ctypes.get_last_error())
    return pid.value


def verified_job(name, *, terminate_job=False):
    """Query the specific controller job, never just membership in ANY job.

    Do not retain a worker job handle: that would defeat controller kill-on-close.
    """
    require(os.name == 'nt', 'verified containment requires Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.OpenJobObjectW.restype = wintypes.HANDLE
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    kernel.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                               wintypes.DWORD, ctypes.c_void_p]
    kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenJobObjectW(0x0004 | (0x0008 if terminate_job else 0), False, name)
    require(bool(handle), 'controller job unavailable')
    try:
        member, limits = wintypes.BOOL(), JobLimits()
        require(kernel.IsProcessInJob(kernel.GetCurrentProcess(), handle, ctypes.byref(member))
                and member.value, 'worker is not in controller job')
        require(kernel.QueryInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits), None)
                and limits.basic.flags & 0x2000, 'controller job lacks kill-on-close')
        if terminate_job:
            require(kernel.TerminateJobObject(handle, 70), 'cannot terminate unsupervised job')
    finally:
        kernel.CloseHandle(handle)


def approved_worker(request, sidecar):
    """Bind all controller fields, budgets, and the exact slot before importing the study."""
    require(type(request.get('budgets')) is dict, 'complete worker budgets required')
    try:
        budgets = Budgets(**request['budgets'])
    except TypeError as exc:
        raise ValueError('complete worker budgets required') from exc
    approved = read_json(sidecar.parent / 'request.json')
    session_request = approved['request']
    require(session_request['action'] == 'execute'
            and session_request['sidecar'] == str(sidecar.parent)
            and approved['budgets'] == request['budgets'] == session_request['budgets'],
            'worker differs from approved session/budgets')
    require(all(request.get(k) == v for k, v in session_request.items()),
            'worker differs from approved controller request')
    require(all(request.get(k) == v for k, v in asdict(budgets).items()),
            'worker budget fields disagree')
    require(type(request.get('controller_pid')) is int and request['controller_pid'] == os.getppid(),
            'worker controller is not its live parent')
    require(request['kind'] in ('pair', 'audit')
            and (request['kind'] != 'audit' or request['pair'] <= request['audits']),
            'worker slot not approved')
    require(request['directories'] == session_request['bundles'][request['pair']-1],
            'worker slot targets differ from approved session')
    require(type(request.get('worker_launch_monotonic')) in (int, float)
            and math.isfinite(request['worker_launch_monotonic'])
            and request['session_started_monotonic'] <= request['worker_launch_monotonic'] <= time.monotonic(),
            'invalid worker launch epoch')
    return budgets


class ControllerSupervision:
    """Peer-verified duplex pipe. Only monitor-loop samples emit heartbeats."""
    def __init__(self, request, process, tree):
        require(os.name == 'nt' and tree.job, 'supervision requires contained Windows worker')
        self.process = process
        self.request_hash = request_digest(request)
        self.job_name = tree.name
        self.connection = None
        self.error = self.finished = None
        self.ready, self.verified, self.closing = threading.Event(), threading.Event(), threading.Event()
        self.listener = Listener(request['supervision']['pipe'], family='AF_PIPE')
        self.thread = threading.Thread(target=self._receive, daemon=True, name='profiler-controller-pipe')
        self.thread.start()

    def _receive(self):
        try:
            self.connection = self.listener.accept()
            if self.closing.is_set():
                return
            require(pipe_peer_pid(self.connection, server=True) == self.process.pid, 'wrong worker pipe peer')
            require(pipe_receive(self.connection) == dict(event='hello', request_sha256=self.request_hash),
                    'worker request handshake mismatch')
            self.ready.set()
            require(pipe_receive(self.connection) == dict(event='contained', request_sha256=self.request_hash),
                    'worker containment acknowledgement missing')
            self.verified.set()
            finished = pipe_receive(self.connection)
            require(finished.get('event') == 'finished' and finished.get('request_sha256') == self.request_hash,
                    'worker completion handshake mismatch')
            self.finished = finished
        except BaseException as exc:
            if not self.closing.is_set():
                self.error = exc

    def pulse(self):
        if self.error:
            raise self.error
        if self.ready.is_set() and self.finished is None:
            try:
                pipe_send(self.connection, dict(event='sampled', request_sha256=self.request_hash,
                                               job_name=self.job_name, sampled_monotonic=time.monotonic()))
            except (BrokenPipeError, EOFError):
                self.thread.join(timeout=.1)
                if self.finished is None:
                    raise

    def completed(self, result_path):
        self.thread.join(timeout=1)
        return bool(not self.error and self.verified.is_set() and self.finished
                    and self.finished.get('result_sha256') == digest(result_path))

    def close(self):
        self.closing.set()
        if self.connection is None and self.thread.is_alive():
            # Listener.close does not cancel PipeListener.accept's outstanding
            # overlapped connection. Wake our own accept before closing handles.
            try:
                Client(self.listener.address, family='AF_PIPE').close()
            except OSError:
                pass
        if self.connection:
            self.connection.close()
        self.listener.close()
        self.thread.join(timeout=1)
        if self.connection:
            self.connection.close()


class WorkerSupervision:
    """OS peer identity + exact job membership + sampled-monitor lease.

    Local nonmalicious-user guardrail, not protection from a hostile parent/admin.
    """
    def __init__(self, request):
        self.request = request
        self.budgets = Budgets(**request['budgets'])
        self.timeout = max(2.0, 5*self.budgets.sample_seconds)
        self.connection = self.thread = None
        self.closing, self.lost = threading.Event(), threading.Event()
        self.last_sample = 0.0
        self.request_hash = request_digest(request)

    def _sample(self, message):
        require(message.get('event') == 'sampled' and message.get('request_sha256') == self.request_hash
                and message.get('job_name') == self.request['supervision']['job_name'],
                'invalid controller supervision heartbeat')
        stamp = message.get('sampled_monotonic')
        require(type(stamp) in (int, float) and math.isfinite(stamp)
                and self.last_sample <= stamp <= time.monotonic()
                and time.monotonic()-stamp < self.timeout, 'stale controller supervision heartbeat')
        self.last_sample = stamp

    def __enter__(self):
        require(os.name == 'nt', 'verified supervision requires Windows')
        require(self.request['controller_pid'] == os.getppid(), 'controller parent changed')
        endpoint = self.request.get('supervision')
        require(type(endpoint) is dict and type(endpoint.get('pipe')) is str
                and endpoint['pipe'].startswith('\\\\.\\pipe\\puf-snn-resource-')
                and type(endpoint.get('job_name')) is str
                and endpoint['job_name'].startswith('Local\\puf-snn-resource-'),
                'verified controller supervision endpoint required')
        try:
            self.connection = Client(self.request['supervision']['pipe'], family='AF_PIPE')
            require(pipe_peer_pid(self.connection, server=False) == self.request['controller_pid'],
                    'wrong controller pipe peer')
            pipe_send(self.connection, dict(event='hello', request_sha256=self.request_hash))
            require(self.connection.poll(self.timeout), 'active resource supervisor unavailable')
            self._sample(pipe_receive(self.connection))
            verified_job(self.request['supervision']['job_name'])
            pipe_send(self.connection, dict(event='contained', request_sha256=self.request_hash))
            self.thread = threading.Thread(target=self._watch, daemon=True, name='profiler-worker-watchdog')
            self.thread.start()
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def _watch(self):
        try:
            while not self.closing.is_set():
                if self.connection.poll(.05):
                    self._sample(pipe_receive(self.connection))
                self.check()
        except BaseException as exc:
            if not self.closing.is_set():
                self.lost.set()
                # Diagnostic I/O must not indefinitely postpone emergency termination.
                recorder = threading.Thread(target=diagnostic, args=(
                    Path(self.request['worker_sidecar']) / 'supervision-error.json',
                    error_detail('supervision-lost', exc)), daemon=True)
                recorder.start()
                recorder.join(timeout=.05)
                try:
                    verified_job(self.request['supervision']['job_name'], terminate_job=True)
                finally:
                    os._exit(70)  # Also stop a long operation without waiting for its next boundary.

    def check(self):
        if self.lost.is_set() or time.monotonic()-self.last_sample >= self.timeout:
            raise StopRequested('active resource supervision lost')

    def finish(self, result_path):
        self.check()
        pipe_send(self.connection, dict(event='finished', request_sha256=self.request_hash,
                                       result_sha256=digest(result_path)))

    def __exit__(self, *exc):
        self.closing.set()
        if self.thread:
            self.thread.join(timeout=1)
        if self.connection:
            self.connection.close()


def peak_update(peaks, sample):
    for key, value in sample.items():
        if isinstance(value, (int, float)) and key in peaks:
            peaks[key] = value if peaks[key] is None else max(peaks[key], value)


def launch_python(arguments, *, env=None, **kwargs):
    """Launch the interpreter itself, retaining the current virtual environment.

    python.org Windows venv executables are redirectors: their Popen PID is NOT
    the Python worker PID. Launch the base interpreter using the same environment
    setting as CPython's redirector, so parent/pipe identity, metrics and job
    attachment all refer to the actual worker. Never relax those identity checks.
    """
    child_env = dict(os.environ if env is None else env)
    executable = sys.executable
    if os.name == 'nt' and sys.prefix != sys.base_prefix:
        executable = getattr(sys, '_base_executable', None)
        require(sys.implementation.name == 'cpython' and type(executable) is str
                and executable and Path(executable).is_absolute()
                and Path(executable) != Path(sys.executable),
                'direct Windows virtual-environment interpreter unavailable')
        child_env['__PYVENV_LAUNCHER__'] = sys.executable
    return subprocess.Popen([executable, *arguments], env=child_env, **kwargs)


def monitor_worker(request, sidecar, budgets, session_start, all_bundles,
                   *, popen=launch_python, metrics_factory=WindowsMetrics,
                   supervision_factory=ControllerSupervision):
    """No harness import/execution until the controller releases the stdin gate."""
    sidecar = Path(sidecar)
    progress, stop = sidecar / 'progress.json', sidecar / 'STOP'
    start = time.monotonic()
    request = dict(request, worker_launch_monotonic=start, budgets=asdict(budgets))
    peaks = dict(rss_bytes=None, private_bytes=None, os_peak_rss_bytes=None, cpu_seconds=None)
    phase_peaks, violations, errors = {}, [], []
    process = tree = metrics = supervision = None
    samples, max_gap, previous_time = 0, 0.0, start
    last_sample = None
    def observe():
        sample = metrics.sample()
        sample['free_disk_bytes'] = shutil.disk_usage(sidecar).free
        sizes = {str(p): tree_size(p) for p in all_bundles}
        phase = read_json(progress) if progress.exists() else dict(name='startup', started=start)
        total = sum(v['logical_bytes'] for v in sizes.values()) + tree_size(sidecar.parent)['logical_bytes']
        failures = budgets.violations(sample, phase_seconds=time.monotonic()-phase['started'],
            session_seconds=time.monotonic()-session_start,
            bundle_bytes=max([0] + [v['logical_bytes'] for v in sizes.values()]), total_bytes=total)
        return sample, sizes, phase, total, failures
    try:
        with (sidecar / 'stdout.txt').open('xb') as stdout, (sidecar / 'stderr.txt').open('xb') as stderr:
            process = popen([str(Path(__file__).resolve()), '_worker'],
                stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, cwd=ROOT,
                start_new_session=os.name != 'nt', env=dict(os.environ,
                    PYTHONDONTWRITEBYTECODE='1', NUMBA_CACHE_DIR=str(sidecar / 'compiler-cache')))
            tree = ProcessTree(process)
            request['supervision'] = dict(pipe='\\\\.\\pipe\\puf-snn-resource-' + uuid.uuid4().hex,
                                          job_name=tree.name)
            require(os.name == 'nt' or metrics_factory is not WindowsMetrics, 'execution monitoring requires Windows')
            metrics = metrics_factory(process.pid)
            # Check hard resources before releasing the gated worker.
            _, _, _, _, violations = observe()
            if not violations:
                supervision = supervision_factory(request, process, tree)
                process.stdin.write(json.dumps(request).encode('utf-8'))
                process.stdin.close()
            stopped_at = None
            while process.poll() is None:
                now = time.monotonic()
                max_gap, previous_time = max(max_gap, now-previous_time), now
                sample, sizes, phase, total, failures = observe()
                if supervision and not failures and not violations:
                    try:
                        supervision.pulse()
                    except Exception as exc:
                        errors.append(error_detail('supervision', exc))
                        failures.append('active resource supervision lost')
                if failures or violations:
                    violations = list(dict.fromkeys(violations + failures))
                    if stopped_at is None:
                        stop.write_text('\n'.join(violations), encoding='utf-8')
                        stopped_at = now
                        if process.stdin and not process.stdin.closed:
                            process.stdin.close()
                    if now-stopped_at >= budgets.stop_grace_seconds:
                        terminate(process, tree)
                peak_update(peaks, sample)
                phase_peak = phase_peaks.setdefault(phase['name'], dict(rss_bytes=None, private_bytes=None))
                peak_update(phase_peak, sample)
                last_sample = dict(metrics=sample, outputs=sizes, aggregate_growth_bytes=total,
                                   phase=phase['name'], elapsed_seconds=now-start)
                samples += 1
                save_json(sidecar / 'monitor.json', dict(samples=samples, sampled_peaks=peaks,
                    phase_sampled_peaks=phase_peaks, last_sample=last_sample, violations=violations))
                time.sleep(budgets.sample_seconds)
            exited = time.monotonic()
            # Held process handle can expose final lifetime counters after exit.
            final, sizes, phase, total, failures = observe()
            peak_update(peaks, final)
            violations = list(dict.fromkeys(violations + failures))
            result_path = sidecar / 'worker-result.json'
            worker_result = read_json(result_path) if result_path.exists() else None
            verified_completion = bool(supervision and result_path.exists() and supervision.completed(result_path))
            success = process.returncode == 0 and not violations and verified_completion and bool(
                worker_result and worker_result['success'])
            if not success:
                errors.append(dict(stage='worker-completion', type='WorkerFailure', exit_code=process.returncode,
                    violations=violations, verified_completion=verified_completion,
                    worker_result_present=worker_result is not None))
            return dict(success=success, exit_code=process.returncode, launch_to_exit_wall_seconds=exited-start,
                sampled_peaks=peaks, phase_sampled_peaks=phase_peaks, final_os_counters=final,
                samples=samples, requested_sampling_seconds=budgets.sample_seconds, max_observed_sample_gap_seconds=max_gap,
                violations=violations, errors=errors, supervision_verified=verified_completion,
                final_outputs=sizes, worker=worker_result, last_sample=last_sample)
    except BaseException as exc:
        diagnostic(sidecar / 'controller-error.json', error_detail('monitor-worker', exc))
        raise
    finally:
        try:
            if process:
                terminate(process, tree)
        finally:
            try:
                if supervision:
                    supervision.close()
            finally:
                if metrics:
                    metrics.close()


def run_bundle(evidence, config, directory, request):
    """Delegate the unmodified lifecycle; never synthesize a successful receipt."""
    with evidence.EvidenceRun(directory, config, authorization=request['authorization'],
            reviewed_plan_sha256=request['reviewed_plan_sha256']) as run:
        result = run.execute()
    require(result['status'] == 'PASS' and result['arm_attempts'] == 150
            and result['validation_passes_completed'] == 2, 'invalid finalization receipt')
    directory = Path(directory)
    require(not (directory / 'INCOMPLETE.json').exists()
            and (directory / 'NONFORMAL_VALIDATED.json').is_file(), 'incomplete evidence after finalization')
    return result


def worker(request, *, loader=harness):
    check_approval(request)
    require(request['profiler_sha256'] == digest(__file__), 'profiler changed')
    session = request['session']
    require(re.fullmatch(r'[a-z0-9][a-z0-9-]{0,23}', session or '') is not None, 'invalid session')
    require(all(type(request[k]) is int for k in ('pair', 'pairs', 'runs_per_pair', 'audits'))
            and 1 <= request['pair'] <= request['pairs'] <= 3
            and request['runs_per_pair'] in (1, 2) and request['pairs']*request['runs_per_pair'] <= 6
            and 0 <= request['audits'] <= min(3, request['pairs'])
            and (not request['audits'] or request['runs_per_pair'] == 2), 'aggregate cap violated')
    sidecar = unlinked(Path(request['worker_sidecar']))
    require(sidecar.parent == (SIDECAR_ROOT / session).absolute()
            and sidecar.name == f'{request["kind"]}-{request["pair"]}', 'invalid worker sidecar')
    expected = [str((EVIDENCE_ROOT / f'{PREFIX}{session}-p{request["pair"]}-{s}').absolute())
                for s in ('cold', 'warm')[:request['runs_per_pair']]]
    require(request['directories'] == expected, 'invalid worker evidence targets')
    # For audits, inspect ancestors without rejecting the target's own sealed files.
    unlinked(EVIDENCE_ROOT)
    for directory in expected:
        candidate = Path(directory)
        require(not candidate.is_symlink() and not getattr(candidate, 'is_junction', lambda: False)(),
                'linked evidence forbidden')
    approved_worker(request, sidecar)
    with WorkerSupervision(request) as supervision:
        return supervised_worker(request, sidecar, expected, supervision, loader)


def supervised_worker(request, sidecar, expected, supervision, loader):
    supervision.check()
    # A controller slot may execute once, including audit slots. Failed work is
    # never retried and an internal worker invocation cannot replay the same slot.
    with (sidecar / 'worker-claimed.json').open('x', encoding='utf-8') as claim:
        json.dump(dict(kind=request['kind'], pair=request['pair']), claim)
    measurements, receipts, success = Measurements(), [], False
    def boundary():
        supervision.check()
        if (sidecar / 'STOP').exists():
            raise StopRequested('controller resource boundary')
        require(digest(request['config']) == request['config_byte_sha256'], 'configuration drift')
    def phase(name, directory):
        # First bundle/audit budget includes worker launch and imports; reuse gets
        # its own deadline. The controller supplies the shared monotonic epoch.
        started = time.monotonic() if name == 'process-reused' else request['worker_launch_monotonic']
        save_json(sidecar / 'progress.json', dict(name=name, evidence=str(directory), started=started))
        measurements.phase = name
        boundary()
    try:
        boundary()
        with measurements.span('imports'):
            study, evidence = loader()
        with io_schema_profile(measurements, study.Draft202012Validator), patched(
                measurements, instrument_bindings(study, evidence), boundary):
            config = study.StudyConfig.load(request['config'])
            check_config(study, config, request['reviewed_plan_sha256'], require_review=True)
            require(digest(request['config']) == request['config_byte_sha256']
                    and config.digest == request['config_sha256'], 'configuration drift')
            require(evidence.source_hashes() == request['source_hashes'], 'source drift')
            if request['kind'] == 'audit':
                require(request['audit_approval'] == 'AUDIT-RESOURCE-V1' and request['runs_per_pair'] == 2
                        and request['pair'] <= request['audits'], 'audit approval/second bundle required')
                phase('standalone-audit', expected[-1])
                receipt = evidence.audit_evidence(expected[-1])
                require(receipt['status'] == 'PASS' and receipt['arm_attempts'] == 150
                        and receipt['validation_scope'] == 'standalone-audit'
                        and receipt['validation_passes_completed'] == 1, 'invalid standalone audit receipt')
                receipts.append(receipt)
            else:
                require(request['kind'] == 'pair', 'unknown worker kind')
                for index, directory in enumerate(expected):
                    phase('process-cold' if index == 0 else 'process-reused', directory)
                    evidence.checked_output_path(directory, 'nonformal')
                    require(evidence.source_hashes() == request['source_hashes'], 'source drift between bundles')
                    require(digest(request['config']) == request['config_byte_sha256'], 'configuration drift between bundles')
                    with measurements.span('bundle'):
                        receipts.append(run_bundle(evidence, config, directory, request))
                    # run_bundle releases the active run; runtime creates fresh endpoints per arm.
                    gc.collect()
            boundary()
        success = True
    finally:
        save_json(sidecar / 'worker-result.json', dict(success=success, receipts=receipts,
            measurements=dict(measurements.totals),
            measurements_by_phase={name: dict(totals) for name, totals in measurements.by_phase.items()},
            separate_passes=measurements.passes,
            cpu_seconds_worker=time.process_time(), environment=dict(executable=sys.executable,
                python=sys.version, platform=platform.platform(), cpu=platform.processor(), cores=os.cpu_count(),
                perf_counter=vars(time.get_clock_info('perf_counter'))),
            cache=dict(settings={k: v for k, v in os.environ.items() if k.startswith(('NUMBA_', 'OMP_', 'MKL_', 'OPENBLAS_'))},
                second_bundle_same_process=request['kind'] == 'pair' and request['runs_per_pair'] == 2,
                cache_hits=None, empty_disk_cache_guaranteed=False)))
        supervision.finish(sidecar / 'worker-result.json')


def publish_acceptance(sidecar, summary, budgets, session_start, all_bundles):
    """Stage first; all checks include staging bytes. Atomic acceptance is LAST.

    Only summary.json is authoritative. A .new file is never an accepted receipt.
    """
    candidate = dict(summary, success=True, state='accepted',
                     session_wall_seconds=time.monotonic()-session_start)
    target = sidecar / 'summary.json'
    temporary = target.with_suffix('.json.new')
    temporary.write_text(json.dumps(candidate, sort_keys=True, indent=2, allow_nan=False), encoding='utf-8')
    growth = sum(tree_size(p)['logical_bytes'] for p in all_bundles) + tree_size(sidecar)['logical_bytes']
    if growth >= budgets.total_growth_bytes:
        summary['violations'].append('aggregate growth at session completion')
    if shutil.disk_usage(sidecar).free <= budgets.min_free_disk_bytes:
        summary['violations'].append('free_disk_bytes at completion')
    if time.monotonic()-session_start >= budgets.session_seconds:
        summary['violations'].append('session deadline at completion')
    if summary['violations'] or summary['errors']:
        return False
    temporary.replace(target)
    return True  # No subsequent filesystem operation or acceptance check.


def execute(args, checked, budgets):
    check_approval(vars(args))
    sidecar = unlinked(checked['sidecar'])
    sidecar.mkdir(parents=True, exist_ok=False)
    session_start = time.monotonic()
    request = dict(vars(args), **{k: v for k, v in checked.items() if k not in vars(args)})
    request['config'] = checked['config']
    request.update(controller_pid=os.getpid(), session_started_monotonic=session_start, budgets=asdict(budgets))
    results = []
    outcome = dict(success=False, sidecar=str(sidecar), completed_workers=0)
    summary = dict(success=False, state='pending', workers=results, session_wall_seconds=0,
                   budgets=asdict(budgets), limitations=LIMITATIONS, violations=[], errors=[])
    save_json(sidecar / 'summary.json', summary)
    all_bundles = [Path(p) for pair in checked['bundles'] for p in pair]
    stage = 'session-request'
    try:
        save_json(sidecar / 'request.json', dict(request=request, budgets=asdict(budgets)))
        jobs = [('pair', p) for p in range(1, args.pairs + 1)] + [('audit', p) for p in range(1, args.audits + 1)]
        for kind, pair in jobs:
            stage = f'worker-{kind}-{pair}'
            require(time.monotonic()-session_start < budgets.session_seconds, 'session deadline before launch')
            child = sidecar / f'{kind}-{pair}'
            child.mkdir(exist_ok=False)
            (child / 'compiler-cache').mkdir(exist_ok=False)
            task = dict(request, kind=kind, pair=pair, directories=checked['bundles'][pair-1], worker_sidecar=str(child))
            result = monitor_worker(task, child, budgets, session_start, all_bundles)
            save_json(child / 'summary.json', result)
            results.append(result)
            if not result['success']:
                summary['errors'].extend(result.get('errors') or [dict(stage=stage, type='WorkerFailure')])
                summary['violations'].extend(result.get('violations', []))
                break
        else:
            stage = 'final-acceptance'
            summary['session_wall_seconds'] = time.monotonic()-session_start
            save_json(sidecar / 'summary.json', summary)
            if publish_acceptance(sidecar, summary, budgets, session_start, all_bundles):
                return dict(outcome, success=True, completed_workers=len(results))
            summary['errors'].append(dict(stage=stage, type='FinalAcceptanceViolation',
                                          violations=list(summary['violations'])))
        summary.update(state='unsuccessful', session_wall_seconds=time.monotonic()-session_start)
        save_json(sidecar / 'summary.json', summary)
    except BaseException as exc:
        detail = error_detail(stage, exc)
        summary['errors'].append(detail)
        summary.update(success=False, state='unsuccessful', session_wall_seconds=time.monotonic()-session_start)
        diagnostic(sidecar / 'controller-error.json', detail)
        try:
            save_json(sidecar / 'summary.json', summary)
        except (OSError, ValueError):
            pass  # Previously committed pending/unsuccessful receipt remains authoritative.
        raise
    outcome['completed_workers'] = len(results)
    return outcome


LIMITATIONS = [
    'Sampling misses transient peaks; OS peak working set is worker-lifetime, shared across reused phases.',
    'Logical process I/O and file-hash input bytes are not physical disk throughput.',
    'Only the serial calling thread has function/C-call profiling; hook overhead affects all observed timings.',
    'Inclusive timings overlap. Exclusive timings subtract observed direct children only.',
    'Built-in write/flush counts include Python-visible calls; implicit close/OS/cache flushes are not observed.',
    'Manifest construction/verification are included in finalize/audit and file-hash spans, not isolated root spans.',
    'Children are contained/cleaned up; separate child CPU/RAM/I/O, physical allocation and cache hits are unavailable.',
    'New compiler cache directory per worker does not guarantee other caches are empty or machine coldness.',
    'First/subsequent BCH decode and detailed JIT phases need broader instrumentation; evidence retains stage spans.',
    'Storage type/filesystem, power policy, background load and interruptions require researcher host notes.',
    'Hard termination can leave no worker metrics or incomplete evidence; no resume/retry/reseal/deletion.',
    'Launch-to-exit wall includes controller observation latency; sampled maxima are not guaranteed peaks.',
]


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('preflight', 'dry-run', 'execute', '_worker'))
    p.add_argument('--config', default=str(ROOT / 'configs/three_arm_auth_nonformal_pilot_v1.json'))
    p.add_argument('--session')
    p.add_argument('--pairs', type=int, default=1)
    p.add_argument('--runs-per-pair', type=int, default=1)
    p.add_argument('--audits', type=int, default=0)
    p.add_argument('--approval')
    p.add_argument('--authorization')
    p.add_argument('--audit-approval')
    p.add_argument('--reviewed-plan-sha256')
    for option in ('bundle-seconds', 'session-seconds', 'memory-bytes', 'min-free-ram-bytes',
                   'min-free-disk-bytes', 'bundle-growth-bytes', 'total-growth-bytes'):
        p.add_argument('--' + option, type=float if option.endswith('seconds') else int)
    p.add_argument('--sample-seconds', type=float, default=0.05)
    p.add_argument('--stop-grace-seconds', type=float, default=2)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.action == '_worker':
        worker(json.load(sys.stdin))
        return 0
    checked = preflight(args)
    if args.action != 'execute':
        print(json.dumps(checked, indent=2))
        return 0
    result = execute(args, checked, Budgets(**checked['budgets']))
    print(json.dumps(result, indent=2))
    return 0 if result['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
