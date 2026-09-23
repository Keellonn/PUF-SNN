"""Strict provisional research configuration; wire constants are not knobs."""
from dataclasses import asdict, dataclass
import json
from pathlib import Path

from .session import Limits, SessionConfig


@dataclass(frozen=True)
class AuthConfig:
    config_version: str = "puf-snn-auth-config-v1"
    protocol_profile: str = "puf-snn-l3-v1-wire2"
    handshake_timeout_ms: int = 10000
    session_ttl_ms: int = 300000
    max_windows: int = 10000
    max_pending_sessions: int = 128
    max_sessions_per_process: int = 10000
    warmup_iterations: int = 20

    def __post_init__(self):
        if (self.config_version != "puf-snn-auth-config-v1"
                or self.protocol_profile != "puf-snn-l3-v1-wire2"):
            raise ValueError("invalid authentication profile")
        self.session_config()
        if type(self.warmup_iterations) is not int or not 0 <= self.warmup_iterations <= 10000:
            raise ValueError("invalid warmup_iterations")

    def session_config(self):
        return SessionConfig(Limits(self.handshake_timeout_ms, self.session_ttl_ms, self.max_windows),
                             self.max_pending_sessions, self.max_sessions_per_process)

    @classmethod
    def from_dict(cls, obj):
        if type(obj) is not dict or set(obj) != set(cls.__dataclass_fields__):
            raise ValueError("authentication configuration requires exact keys")
        return cls(**obj)

    @classmethod
    def load(cls, path):
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate configuration key")
                result[key] = value
            return result
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=pairs))

    def to_dict(self):
        return asdict(self)
