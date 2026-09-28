"""Reproducible sensor changes applied before legitimate authentication."""

from .stream import apply_stream_attack, canonical_motion_record, iter_attack_cases, validate_attack_config

__all__ = ["apply_stream_attack", "canonical_motion_record", "iter_attack_cases", "validate_attack_config"]
