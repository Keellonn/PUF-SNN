"""Coordinated Week 9 sidecar snapshots; never scientific evidence publication.

Named mutexes exclude short snapshot reads from atomic rename on Windows.
Readers return memory snapshots after closing the file/releasing the mutex.
Uncooperative readers can still deny rename: finite retry then fails closed.
"""
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
from functools import lru_cache
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import threading
import time

LOCK_WAIT_MILLISECONDS = 50
REPLACE_MAX_ATTEMPTS = 6  # Initial call plus at most five retries.
REPLACE_DEADLINE_SECONDS = .05  # From the first eligible replacement failure.
REPLACE_RETRY_SECONDS = .01
RETRYABLE_WINERRORS = frozenset((5, 32, 33))
MAX_SNAPSHOT_BYTES = 1024 * 1024
_portable_lock = threading.RLock()


@lru_cache(maxsize=1)
def _kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.ReleaseMutex.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


@contextmanager
def _guard(path):
    """Cross-process exclusion; at most a 50 ms lock wait, never infinite."""
    if os.name != "nt":
        if not _portable_lock.acquire(timeout=LOCK_WAIT_MILLISECONDS/1000):
            raise TimeoutError("Week 9 sidecar snapshot lock unavailable")
        try:
            yield
        finally:
            _portable_lock.release()
        return
    identity = os.path.normcase(str(Path(path).resolve())).encode("utf-8")
    kernel = _kernel()
    handle = kernel.CreateMutexW(None, False,
        "Local\\puf-snn-w9-sidecar-" + sha256(identity).hexdigest())
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        outcome = kernel.WaitForSingleObject(handle, LOCK_WAIT_MILLISECONDS)
        if outcome == 258:
            raise TimeoutError("Week 9 sidecar snapshot lock unavailable")
        if outcome not in (0, 128):  # Abandoned mutex grants ownership too.
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = True
        yield
    finally:
        try:
            if acquired and not kernel.ReleaseMutex(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(handle)


@contextmanager
def snapshot_reader(path):
    """Return immutable bytes in memory, with no live sidecar handle held."""
    with _guard(path):
        with Path(path).open("rb") as stream:
            snapshot = stream.read(MAX_SNAPSHOT_BYTES + 1)
    if len(snapshot) > MAX_SNAPSHOT_BYTES:
        raise ValueError("sidecar snapshot exceeds 1 MiB")
    with io.BytesIO(snapshot) as stream:
        yield stream


def read_json(path):
    with snapshot_reader(path) as stream:
        snapshot = stream.read()
    return json.loads(snapshot.decode("utf-8"))


def _replace_once(temporary, path):
    os.replace(temporary, path)


def _replace_bounded(temporary, path):
    deadline = None
    for attempt in range(REPLACE_MAX_ATTEMPTS):
        try:
            _replace_once(temporary, path)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in RETRYABLE_WINERRORS:
                raise
            if deadline is None:
                deadline = time.monotonic() + REPLACE_DEADLINE_SECONDS
            remaining = deadline - time.monotonic()
            if attempt + 1 == REPLACE_MAX_ATTEMPTS or remaining <= 0:
                raise
            time.sleep(min(REPLACE_RETRY_SECONDS, remaining))
            if time.monotonic() >= deadline:
                raise


def save_json(path, obj):
    """Atomic sidecar publication; errors propagate into containment cleanup.

    Lock wait <=50 ms; replacement retry <=50 ms and <=6 calls. No heartbeat
    is fabricated during either wait. OS calls themselves are not preemptible.
    Persistent errors retain diagnostics/candidate where possible and escape.
    """
    path = Path(path)
    payload = json.dumps(obj, sort_keys=True, indent=2, allow_nan=False)
    with _guard(path):
        temporary = path.with_suffix(path.suffix + ".new")
        temporary.write_text(payload, encoding="utf-8")
        _replace_bounded(temporary, path)
