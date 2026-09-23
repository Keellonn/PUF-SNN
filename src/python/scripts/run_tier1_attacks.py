"""Tier 1 external mutations around the immutable wire-2 authentication baseline.

Synthetic mechanism experiment, not PUF reliability or production security.
No runtime monkeypatching, private auth-state access, re-tagging or retry.
"""
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import argparse
import base64
import csv
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/python'))

from jsonschema import Draft202012Validator
from puf_snn.auth.audit import AuditJSONL, Provenance, summarize_ns
from puf_snn.auth.binary_window import F32, Sample, Window, parse_envelope, validate_quality
from puf_snn.auth.config import AuthConfig
from puf_snn.auth.sender import Sender
from puf_snn.auth.session import Failure, RegistryEntry, provision_device
from puf_snn.auth.verifier import Verifier

PRIMARY = ('same_session_replay', 'prior_session_replay', 'cross_device_substitution',
           'payload_modification', 'metadata_modification')
CONTROL = 'legitimate_control'
SUPPORT = 'cross_session_substitution'
BASELINE = 'docs/layer3-baseline-v1-manifest.json'
CONFIG = 'configs/tier1_attack_experiment_v1.json'
SCHEMA = 'schemas/tier1-attempt-v1.schema.json'
EXPERIMENT_SOURCES = ('src/python/scripts/run_tier1_attacks.py', 'run_tier1.ps1',
                      SCHEMA, 'tests/tier1/test_tier1.py',
                      'docs/tier1-attack-experiment-plan.md')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    return digest(Path(path).read_bytes())


def utc():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def strict_json(data):
    def pairs(items):
        obj = {}
        for key, value in items:
            if key in obj:
                raise ValueError('duplicate JSON key')
            obj[key] = value
        return obj
    return json.loads(data, object_pairs_hook=pairs)


@dataclass(frozen=True)
class Config:
    config_version: str
    baseline_version: str
    protocol_profile: str
    attack_set_version: str
    trials_per_primary_attack: int
    legitimate_control_trials: int
    supporting_cross_session_trials: int
    experiment_seed: int
    warmup_count: int
    expected_attack_names: list
    prior_session_variant: str
    primary_metadata_field: str
    result_schema_version: str
    timing_methodology: str
    confidence_interval_method: str

    @classmethod
    def load(cls, path):
        return cls.from_dict(strict_json(Path(path).read_text(encoding='utf-8')))

    @classmethod
    def from_dict(cls, obj):
        if type(obj) is not dict or set(obj) != set(cls.__dataclass_fields__):
            raise ValueError('Tier 1 configuration requires exact keys')
        constants = dict(config_version='puf-snn-tier1-config-v1',
                         baseline_version='Layer 3 Authentication Baseline v1',
                         protocol_profile='puf-snn-l3-v1-wire2',
                         attack_set_version='puf-snn-tier1-attacks-v1',
                         prior_session_variant='authenticated_replacement',
                         primary_metadata_field='sequence_number',
                         result_schema_version='puf-snn-tier1-attempt-v1',
                         timing_methodology='layer3-v1-perf-counter-ns-linear-p95',
                         confidence_interval_method='wilson-two-sided-95-z-1.959963984540054')
        if any(obj[k] != v for k, v in constants.items()):
            raise ValueError('unsupported Tier 1 version/method')
        if type(obj['expected_attack_names']) is not list or obj['expected_attack_names'] != list(PRIMARY):
            raise ValueError('exact ordered primary attack set required')
        for name in ('trials_per_primary_attack', 'legitimate_control_trials', 'supporting_cross_session_trials'):
            if type(obj[name]) is not int or not 1 <= obj[name] <= 10000:
                raise ValueError('trial counts must be positive bounded integers')
        if type(obj['experiment_seed']) is not int or not 0 <= obj['experiment_seed'] < 2**64:
            raise ValueError('invalid seed')
        if type(obj['warmup_count']) is not int or obj['warmup_count'] != 20:
            raise ValueError('frozen Layer 3 timing requires 20 isolated warmups')
        return cls(**deepcopy(obj))


class BaselineMismatch(RuntimeError):
    def __init__(self, report):
        self.report = report
        super().__init__('frozen baseline hash mismatch')


def check_baseline(root=ROOT):
    root = Path(root)
    manifest = strict_json((root / BASELINE).read_text(encoding='utf-8'))
    files = manifest['file_sha256']
    if manifest['baseline'] != 'Layer 3 Authentication Baseline v1' or manifest['wire_protocol'] != '2.0' or not files:
        raise ValueError('unrecognized baseline manifest')
    observed = {name: file_hash(root / name) if (root / name).is_file() else None for name in files}
    mismatches = [dict(file=name, expected=want, observed=observed[name])
                  for name, want in files.items() if observed[name] != want]
    report = dict(manifest_sha256=file_hash(root / BASELINE), checked=len(files),
                  file_sha256=observed, mismatches=mismatches)
    if mismatches:
        raise BaselineMismatch(report)
    return report


def plan_trials(config):
    counts = {CONTROL: config.legitimate_control_trials,
              **{name: config.trials_per_primary_attack for name in PRIMARY},
              SUPPORT: config.supporting_cross_session_trials}
    plan = []
    for repetition in range(max(counts.values())):
        for kind, count in counts.items():
            if repetition >= count:
                continue
            index = len(plan)
            b = hashlib.sha256(f'tier1-plan-v1:{config.experiment_seed}:{index}'.encode('ascii')).digest()
            plan.append(dict(trial_id=f'trial-{index:05d}', trial_index=index, repetition=repetition,
                             attack_type=kind, sample_index=int.from_bytes(b[:2], 'big') % 120,
                             component=b[2] % 3, mantissa_bit=b[3] % 23,
                             motion_seed=int.from_bytes(b[4:12], 'big')))
    return plan


def expected(kind):
    if kind == CONTROL:
        return 'accept', 'accepted', 'pass', 'pass'
    if kind == 'same_session_replay':
        return 'reject', 'duplicate_sequence', 'pass', 'duplicate'
    if kind == 'prior_session_replay':
        return 'reject', 'inactive_session', 'not_checked', 'not_checked'
    if kind in (*PRIMARY[2:], SUPPORT):
        return 'reject', 'invalid_tag', 'fail', 'not_checked'
    raise ValueError('unknown planned attack')


def synthetic_material(seed, index, label):
    # Privileged provisioning only. Each device/trial has a separate domain.
    from puf_snn.reconstruction import ReconstructionResult, enroll
    stream = hashlib.sha256(f'tier1-enrollment-v1:{seed}:{index}:{label}'.encode('ascii')).digest()
    credential = stream[:4]
    reference = tuple((b >> shift) & 1 for b in stream[4:12] for shift in range(7, -1, -1))
    device, enrollment = f'sim-tier1-{label}', f'tier1-enrollment-{label}'
    helper = enroll(reference, credential, enrollment_id=enrollment)
    bits = tuple((b >> shift) & 1 for b in credential for shift in range(7, -1, -1)) + (0,) * 4
    candidate = ReconstructionResult('candidate_valid_format', 'decoded', 0, bits, credential, True, None)
    return provision_device(device, enrollment, helper), RegistryEntry(device, enrollment, credential), candidate


def synthetic_window(seed, name):
    zero, one = F32(0), F32(0x3f800000)
    samples = []
    for i in range(120):
        b = hashlib.sha256(f'tier1-motion-v1:{seed}:{i}'.encode('ascii')).digest()
        position = tuple(F32(0x3e000000 | (int.from_bytes(b[j:j+4], 'big') & 0x007fffff))
                         for j in (0, 4, 8))
        samples.append(Sample(i, 1_000_000_000 + i * 16_666_667, position, (zero, zero, zero, one), True))
    return Window('synthetic', bytes(16), 0, name, 1_000_000_000, 3_000_000_000,
                  120, 1_000_000, tuple(samples))


def establish(verifier, material, auth_config, local):
    binding, _, candidate = material
    sender = Sender(binding, auth_config.session_config().limits)
    request = sender.begin_attempt(candidate, local.source_record_id, local_provenance=local)
    if isinstance(request, Failure):
        raise RuntimeError('synthetic sender admission failed')
    confirmation = sender.answer_challenge(verifier.begin_session(request, local))
    if isinstance(confirmation, Failure):
        raise RuntimeError('synthetic challenge failed')
    if sender.finish_session(verifier.confirm_session(confirmation)) is not sender:
        raise RuntimeError('synthetic mutual confirmation failed')
    return sender


def mutate_envelope(envelope_bytes, spec, target_device=None, target_session=None):
    """Attacker boundary: public traffic/identifiers only; never receives a key."""
    kind = spec['attack_type']
    if kind in (CONTROL, 'same_session_replay', 'prior_session_replay'):
        return envelope_bytes, dict(field=None, operation='unchanged complete envelope', byte_offset=None,
                                    before_hex=None, after_hex=None, sample_index=None, component=None, bit=None)
    env = parse_envelope(envelope_bytes)
    data = env.authenticated_bytes
    sid_offset = 21 + int.from_bytes(data[19:21], 'big')
    sequence_offset = sid_offset + 16
    window_offset = sequence_offset + 8
    capture_offset = window_offset + 2 + int.from_bytes(data[window_offset:window_offset+2], 'big')
    detail = dict(sample_index=None, component=None, bit=None)
    if kind == 'cross_device_substitution':
        offset, width, new, field = 21, sid_offset - 21, target_device.encode('ascii'), 'device_id'
    elif kind == SUPPORT:
        offset, width, new, field = sid_offset, 16, bytes.fromhex(target_session), 'session_id'
    elif kind == 'metadata_modification':
        offset, width, new, field = sequence_offset, 8, (env.window.sequence_number + 1).to_bytes(8, 'big'), 'sequence_number'
    elif kind == 'payload_modification':
        offset = capture_offset + 32 + spec['sample_index'] * 39 + 10 + spec['component'] * 4
        width = 4
        new = (int.from_bytes(data[offset:offset+4], 'big') ^ (1 << spec['mantissa_bit'])).to_bytes(4, 'big')
        field = f"samples[{spec['sample_index']}].position_m[{spec['component']}]"
        detail.update(sample_index=spec['sample_index'], component=spec['component'], bit=spec['mantissa_bit'])
    else:
        raise ValueError('unknown mutation')
    if len(new) != width or new == data[offset:offset+width]:
        raise ValueError('mutation must change exactly its declared fixed-width field')
    changed = data[:offset] + new + data[offset+width:]
    obj = json.loads(envelope_bytes)
    obj['protected']['bytes_b64'] = base64.b64encode(changed).decode('ascii')
    if kind == SUPPORT:
        obj['authentication']['key_id'] = target_session
    result = json.dumps(obj, separators=(',', ':')).encode('utf-8')
    parsed = parse_envelope(result)
    validate_quality(parsed.window)
    if parsed.tag != env.tag or changed[:offset] != data[:offset] or changed[offset+width:] != data[offset+width:]:
        raise ValueError('mutation touched bytes outside its field or changed tag')
    detail.update(field=field, operation='xor mantissa bit' if kind == 'payload_modification' else 'replace protected field',
                  byte_offset=offset, before_hex=data[offset:offset+width].hex(), after_hex=new.hex())
    return result, detail


def snapshot(verifier, session_ids):
    active = verifier.active_session_ids
    tombstones = {t.session_id.hex(): t for t in verifier.tombstones}
    # The owner is read from successful, verifier-owned establishment records.
    owners = {r['session_id']: r['device_id'] for r in verifier.audit_records
              if r['event_type'] == 'session_establishment' and r['decision'] == 'accept'}
    sessions = []
    for sid in sorted(set(session_ids) | set(active)):
        status = asdict(verifier.session_status(sid))
        terminal = tombstones.get(sid.hex())
        status.update(owner=owners.get(sid.hex()), terminal_reason=terminal.reason if terminal else None,
                      terminal_time_ns=terminal.terminal_time_ns if terminal else None)
        sessions.append(status)
    return dict(sessions=sessions, active_by_device={owners.get(s.hex(), 'unobserved'): s.hex() for s in active})


def state_entry(state, sid):
    return next(s for s in state['sessions'] if s['session_id'] == sid)


def observe(verifier, original, submitted, spec, context, session_ids, detail,
            target_device=None, target_session=None, sender_timing=None, variant=None):
    parsed = parse_envelope(original)
    sid = parsed.window.session_id.hex()
    kind = spec['attack_type']
    decision, reason, authentication, order = expected(kind)
    before = snapshot(verifier, session_ids)
    audit_before = len(verifier.audit_records)
    result = verifier.verify_window(submitted, Provenance(
        run_id=context['run_id'], source_id='tier1-synthetic-v1', config_sha256=context['config_sha256'],
        input_artifact_sha256=digest(original), source_record_id=spec['trial_id']))
    after = snapshot(verifier, session_ids)
    new_audits = verifier.audit_records[audit_before:]
    audit = next((r for r in new_audits if r['event_id'] == result.event_id), None)
    released = []
    release_error = None
    try:
        verifier.release_accepted(result, released.append)
    except ValueError:
        release_error = 'acceptance_required'
    except Exception as error:
        release_error = type(error).__name__  # Never retain exception contents.
    predicted_state = deepcopy(before)
    if decision == 'accept':
        entry = state_entry(predicted_state, sid)
        entry['accepted_count'] += 1
        entry['last_accepted'] = parsed.window.sequence_number
    state_violation = after != predicted_state
    exact_release = len(released) == 1 and released[0] == parsed.window and result.authenticated_bytes == parsed.authenticated_bytes
    release_violation = (not exact_release or release_error is not None) if decision == 'accept' else bool(released or result.accepted_window is not None or result.authenticated_bytes is not None)
    violations = []
    checks = {'decision': result.result == decision, 'reason': result.reason == reason,
              'authentication': audit is not None and audit['authentication_result'] == authentication,
              'order': audit is not None and audit['order_result'] == order,
              'state': not state_violation, 'payload_release': not release_violation,
              'single_window_audit': len(new_audits) == 1 and audit is not None and audit['event_type'] == 'window',
              'audit_decision': audit is not None and (audit['decision'], audit['reason']) == (result.result, result.reason),
              'audit_digest': audit is not None and audit['authenticated_bytes_sha256'] == (
                  digest(parse_envelope(submitted).authenticated_bytes) if authentication == 'pass' else None),
              'audit_timing': audit is not None and audit['latency_ns']['verifier_auth'] == result.verifier_auth_ns,
              'latency': type(result.verifier_auth_ns) is int and result.verifier_auth_ns >= 0,
              'release_gate': release_error is None if decision == 'accept' else release_error == 'acceptance_required',
              'verifier_running': not verifier.incomplete}
    violations.extend(k for k, ok in checks.items() if not ok)
    a, b = state_entry(before, sid), state_entry(after, sid)
    sender_ns = sender_timing.sender_prepare_ns if sender_timing is not None else None
    row = dict(result_schema_version='puf-snn-tier1-attempt-v1', trial_id=spec['trial_id'],
               trial_group_id=spec['trial_id'].split('.')[0], trial_index=spec['trial_index'],
               trial_role='legitimate_control' if kind == CONTROL else 'attack',
               attack_set_version='puf-snn-tier1-attacks-v1', attack_type=kind,
               attack_variant=variant or ('authenticated_replacement' if kind == 'prior_session_replay' else kind),
               is_legitimate_control=kind == CONTROL, is_primary=kind in PRIMARY,
               experiment_seed=context['experiment_seed'], source_device_id=parsed.window.device_id,
               target_device_id=target_device, source_session_id=sid, target_session_id=target_session,
               source_sequence=parsed.window.sequence_number, mutated_field=detail['field'],
               mutation_description=detail['operation'], mutation=detail,
               original_authenticated_bytes_sha256=digest(parsed.authenticated_bytes),
               mutated_authenticated_bytes_sha256=None if kind == CONTROL else digest(parse_envelope(submitted).authenticated_bytes),
               expected_decision=decision, expected_reason=reason, actual_decision=result.result,
               actual_reason=result.reason, authentication_result=audit['authentication_result'] if audit else None,
               order_result=audit['order_result'] if audit else None,
               state_before=before, state_after=after, verifier_state_before=before, verifier_state_after=after,
               accepted_count_before=a['accepted_count'], accepted_count_after=b['accepted_count'],
               last_accepted_before=a['last_accepted'], last_accepted_after=b['last_accepted'],
               payload_release_attempted=True, payload_released=bool(released), payload_reached_release=bool(released),
               payload_reached_inference=False, release_callback_count=len(released), exact_payload_release=exact_release,
               release_error=release_error, verifier_auth_ns=result.verifier_auth_ns,
               sender_prepare_ns=sender_ns, sender_hmac_ns=sender_timing.sender_hmac_ns if sender_timing else None,
               total_layer3_ns=sender_ns + result.verifier_auth_ns if sender_ns is not None and result.verifier_auth_ns is not None else None,
               audit_event_id=result.event_id, verifier_event_id=result.event_id,
               run_id=context['run_id'], config_sha256=context['config_sha256'],
               baseline_manifest_sha256=context['baseline_manifest_sha256'], source_hashes=context['source_hashes'],
               input_artifact_sha256=digest(original), source_record_id=spec['trial_id'],
               temperature=context['temperature'], state_mutation_violation=state_violation,
               payload_release_violation=release_violation, invariant_violations=violations,
               unexpected_behavior=bool(violations), audit_records_added=len(new_audits),
               original_envelope_b64=base64.b64encode(original).decode('ascii'),
               submitted_envelope_b64=base64.b64encode(submitted).decode('ascii'),
               lifecycle_terminal_state=a['state'] if a['state'] != 'ACTIVE' else None,
               lifecycle_terminal_reason=a['terminal_reason'])
    return row


def execute_trial(spec, config, auth_config, context, emit, flush_peers):
    """Fixture and cleanup are outside the timed submission and state interval."""
    materials = [synthetic_material(config.experiment_seed, spec['trial_index'], label) for label in ('A', 'B')]
    verifier = Verifier([m[1] for m in materials], auth_config.session_config())
    senders = []
    def start(material, suffix):
        local = Provenance(run_id=context['run_id'], source_id='tier1-synthetic-v1',
                           config_sha256=context['config_sha256'], source_record_id=spec['trial_id'] + suffix)
        sender = establish(verifier, material, auth_config, local)
        senders.append(sender)
        return sender
    def seal(sender, suffix):
        packet = sender.seal_window(synthetic_window(spec['motion_seed'], spec['trial_id'] + suffix))
        if isinstance(packet, Failure):
            raise RuntimeError('legitimate synthetic sealing failed')
        return packet
    unchanged = dict(field=None, operation='unchanged complete envelope', byte_offset=None,
                     before_hex=None, after_hex=None, sample_index=None, component=None, bit=None)
    def setup_accept(sender, packet, suffix, sids):
        setup_spec = {**spec, 'trial_id': spec['trial_id'] + suffix, 'attack_type': CONTROL}
        row = observe(verifier, packet, packet, setup_spec, context, sids, unchanged,
                      sender_timing=sender.last_window_timing, variant='setup' + suffix)
        emit('setup', row)
        if row['unexpected_behavior']:
            raise RuntimeError('valid-source setup failed; evidence retained')
    try:
        source = start(materials[0], '.source-session')
        source_sid = source.session_id
        sids = [source_sid]
        original = seal(source, '.source-window')
        target_device = target_sid = None
        if spec['attack_type'] != CONTROL:
            setup_accept(source, original, '.setup-source', sids)
        if spec['attack_type'] in ('cross_device_substitution', SUPPORT):
            target = start(materials[1], '.target-session')
            target_device, target_sid = 'sim-tier1-B', target.session_id.hex()
            sids.append(target.session_id)
            target_packet = seal(target, '.target-window')
            setup_accept(target, target_packet, '.setup-target', sids)
        elif spec['attack_type'] == 'prior_session_replay':
            target = start(materials[0], '.replacement-session')
            target_device, target_sid = 'sim-tier1-A', target.session_id.hex()
            sids.append(target.session_id)
            if verifier.session_status(source_sid).state != 'CLOSED' or verifier.session_status(target.session_id).state != 'ACTIVE':
                raise RuntimeError('authenticated replacement precondition failed')
        submitted, detail = mutate_envelope(original, spec, target_device, target_sid)
        row = observe(verifier, original, submitted, spec, context, sids, detail,
                      target_device, target_sid, source.last_window_timing if spec['attack_type'] == CONTROL else None)
        emit('formal', row)
        return row
    finally:
        try:
            if not verifier.incomplete:
                verifier.close_all_sessions()
        finally:
            flush_peers(verifier, senders)


def wilson(successes, n):
    if type(n) is not int or type(successes) is not int or not 0 <= successes <= n:
        raise ValueError('invalid binomial counts')
    if n == 0:
        return None, None
    z = 1.959963984540054
    p, d = successes / n, 1 + z*z/n
    center = (p + z*z/(2*n)) / d
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return max(0.0, center-half), min(1.0, center+half)


def summarize_group(rows, kind):
    n = len(rows)
    accepted = sum(r['actual_decision'] == 'accept' for r in rows)
    rejected = sum(r['actual_decision'] == 'reject' for r in rows)
    latency = summarize_ns(r['verifier_auth_ns'] for r in rows if r['verifier_auth_ns'] is not None)
    lo, hi = wilson(accepted if kind == CONTROL else rejected, n)
    return dict(attack_type=kind, attempts=n, accepted=accepted, rejected=rejected,
                observed_rejection_rate=rejected/n if n else None,
                legitimate_acceptance_rate=accepted/n if n and kind == CONTROL else None,
                unexpected_accepts=accepted if kind != CONTROL else 0,
                observed_unexpected_accept_rate=accepted/n if n and kind != CONTROL else None,
                expected_reason_matches=sum(r['actual_reason'] == r['expected_reason'] for r in rows),
                unexpected_reason_count=sum(r['actual_reason'] != r['expected_reason'] for r in rows),
                state_mutation_violations=sum(r['state_mutation_violation'] for r in rows),
                payload_release_violations=sum(r['payload_release_violation'] for r in rows),
                unexpected_behavior_count=sum(r['unexpected_behavior'] for r in rows),
                wilson_95_low=lo, wilson_95_high=hi,
                **{f'verifier_auth_{k}': v for k, v in latency.items()},
                verifier_auth_missing=n-latency['count'])


def aggregate(rows):
    groups = {kind: [r for r in rows if r['attack_type'] == kind] for kind in (CONTROL, *PRIMARY, SUPPORT)}
    summaries = [summarize_group(group, kind) for kind, group in groups.items()]
    reason_counts = Counter((r['attack_type'], r['attack_variant'], r['expected_reason'], r['actual_reason'],
                             r['actual_decision']) for r in rows)
    reasons = [dict(attack_type=k[0], attack_variant=k[1], expected_reason=k[2], actual_reason=k[3],
                    actual_decision=k[4], count=n) for k, n in sorted(reason_counts.items())]
    variants = [dict(attack_variant=variant, **summarize_group([r for r in rows if r['attack_type'] == kind and r['attack_variant'] == variant], kind))
                for kind, variant in sorted({(r['attack_type'], r['attack_variant']) for r in rows})]
    latencies = []
    for kind, group in [('overall', rows), *groups.items()]:
        for outcome in ('overall', 'accept', 'reject'):
            selected = [r for r in group if outcome == 'overall' or r['actual_decision'] == outcome]
            for stage in ('verifier_auth_ns', 'sender_prepare_ns', 'sender_hmac_ns', 'total_layer3_ns'):
                values = [r[stage] for r in selected if r[stage] is not None]
                latencies.append(dict(attack_type=kind, outcome=outcome, stage=stage, units='ns',
                                      missing=len(selected)-len(values), **summarize_ns(values)))
    return {'control_summary.csv': summaries[:1], 'attack_summary.csv': summaries[1:6],
            'supporting_summary.csv': summaries[6:], 'variant_summary.csv': variants,
            'reason_summary.csv': reasons, 'latency_summary.csv': latencies}


def reconcile(rows, setup, audits, plan, summaries):
    if [r['trial_id'] for r in rows] != [p['trial_id'] for p in plan] or [r['trial_index'] for r in rows] != list(range(len(plan))):
        raise ValueError('missing/duplicate/out-of-order scheduled trials')
    if [(r['attack_type'], r['trial_index']) for r in rows] != [(p['attack_type'], p['trial_index']) for p in plan]:
        raise ValueError('trial plan mismatch')
    if len({r['trial_id'] for r in rows + setup}) != len(rows + setup):
        raise ValueError('duplicate trial IDs')
    if summaries != aggregate(rows):
        raise ValueError('summary/reason/latency/invariant reconciliation failed')
    index = {r['event_id']: r for r in audits}
    if len(index) != len(audits):
        raise ValueError('duplicate audit event ID')
    window_ids = {r['event_id'] for r in audits if r['event_type'] == 'window'}
    observed_ids = [r['audit_event_id'] for r in rows + setup]
    if len(set(observed_ids)) != len(observed_ids) or window_ids != set(observed_ids):
        raise ValueError('unmatched verifier window audit')
    for row in rows + setup:
        audit = index[row['audit_event_id']]
        if (audit['decision'], audit['reason'], audit['authentication_result'], audit['order_result'],
            audit['latency_ns']['verifier_auth'], audit['provenance']['source_record_id']) != (
                row['actual_decision'], row['actual_reason'], row['authentication_result'], row['order_result'],
                row['verifier_auth_ns'], row['source_record_id']):
            raise ValueError('raw/audit decision mismatch')
        if row['actual_reason'] == 'internal_error' or row['verifier_auth_ns'] is None:
            raise ValueError('internal error or missing timing')
    for summary in summaries['attack_summary.csv'] + summaries['control_summary.csv'] + summaries['supporting_summary.csv']:
        if summary['accepted'] + summary['rejected'] != summary['attempts'] or summary['verifier_auth_count'] != summary['attempts']:
            raise ValueError('decision/timing denominator mismatch')
    # Every successful session has exactly one terminal local control record.
    # Retain its event-ID mapping independently of window trial denominators.
    establishments = [r for r in audits if r['event_type'] == 'session_establishment']
    controls = [r for r in audits if r['event_type'] == 'session_control']
    if (len(establishments) != len(plan) + sum(p['attack_type'] in ('prior_session_replay', 'cross_device_substitution', SUPPORT) for p in plan)
            or any(r['decision'] != 'accept' or r['reason'] != 'accepted' for r in establishments)
            or Counter(r['session_id'] for r in establishments) != Counter(r['session_id'] for r in controls)
            or any(n != 1 for n in Counter(r['session_id'] for r in establishments).values())
            or len(audits) != len(window_ids) + len(establishments) + len(controls)):
        raise ValueError('session audit reconciliation failed')
    return dict(passed=True, scheduled=len(plan), formal_rows=len(rows), setup_rows=len(setup),
                primary_attack_attempts=sum(r['is_primary'] for r in rows),
                legitimate_controls=sum(r['is_legitimate_control'] for r in rows),
                supporting_attempts=sum(r['attack_type'] == SUPPORT for r in rows),
                verifier_audit_records=len(audits), matched_window_audits=len(window_ids),
                matched_session_establishments=len(establishments), matched_session_controls=len(controls),
                unexpected_behavior=any(r['unexpected_behavior'] for r in rows + setup),
                state_mutation_violations=sum(r['state_mutation_violation'] for r in rows),
                payload_release_violations=sum(r['payload_release_violation'] for r in rows))


def write_json(path, obj):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(obj, stream, indent=2, allow_nan=False)
        stream.write('\n')


def write_csv(path, rows):
    with Path(path).open('x', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl(path):
    return [strict_json(line) for line in Path(path).read_text(encoding='utf-8').splitlines()]


def verify_csv(path, rows):
    with Path(path).open(encoding='utf-8', newline='') as stream:
        observed = list(csv.DictReader(stream))
    expected_rows = [{k: '' if v is None else str(v) for k, v in r.items()} for r in rows]
    if observed != expected_rows:
        raise ValueError('persisted CSV reconciliation failed')


def run_experiment(output, config_path=ROOT / CONFIG, *, execution_command=None):
    config_path, output = Path(config_path), Path(output)
    config = Config.load(config_path)
    before = check_baseline()  # Mismatch stops BEFORE provisioning/execution.
    config_bytes = config_path.read_bytes()
    source_hashes = {p: file_hash(ROOT / p) for p in EXPERIMENT_SOURCES}
    output.mkdir(parents=True, exist_ok=False)
    streams, writers = [], []
    started = utc()
    try:
        with (output / 'config.json').open('xb') as stream:
            stream.write(config_bytes)
        write_json(output / 'baseline-before.json', before)
        for source, name in ((BASELINE, 'baseline-manifest.json'), (SCHEMA, 'attempts.schema.json'),
                             ('docs/tier1-attack-experiment-plan.md', 'plan.md')):
            with (output / name).open('xb') as stream:
                stream.write((ROOT / source).read_bytes())
        config_hash = digest(config_bytes)
        context = dict(run_id=output.name, config_sha256=config_hash,
                       baseline_manifest_sha256=before['manifest_sha256'], source_hashes=source_hashes,
                       experiment_seed=config.experiment_seed, temperature='warm')
        plan = plan_trials(config)
        write_json(output / 'trial-plan.json', plan)
        auth_config = AuthConfig.load(ROOT / 'configs/authentication_v1.json')
        validator = Draft202012Validator(strict_json((ROOT / SCHEMA).read_text(encoding='utf-8')))
        audit_validator = Draft202012Validator(strict_json((ROOT / 'schemas/auth-audit-v1.schema.json').read_text(encoding='utf-8')))
        row_paths = {'formal': 'attempts.jsonl', 'setup': 'setup_attempts.jsonl', 'warmup': 'warmup_attempts.jsonl'}
        row_files = {}
        for key, name in row_paths.items():
            row_files[key] = (output / name).open('x', encoding='utf-8', newline='\n')
            streams.append(row_files[key])
        collected = {k: [] for k in row_paths}
        def emit(group, row):
            # Persist BEFORE validation; a malformed/anomalous trial is not lost.
            row_files[group].write(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n')
            row_files[group].flush()
            collected[group].append(row)
            validator.validate(row)
        receiver, sender_audits, warm_receiver, warm_sender = [], [], [], []
        for name in ('sender', 'warmup', 'warmup/sender'):
            (output / name).mkdir()
        for directory in (output, output / 'sender', output / 'warmup', output / 'warmup/sender'):
            writers.append(AuditJSONL(directory))
        receiver_writer, sender_writer, warm_receiver_writer, warm_sender_writer = writers
        def flush_peers(v, peers, warm=False):
            recv, snd = (warm_receiver, warm_sender) if warm else (receiver, sender_audits)
            rw, sw = (warm_receiver_writer, warm_sender_writer) if warm else (receiver_writer, sender_writer)
            new_receiver = v.audit_records
            new_sender = [r for peer in peers for r in peer.audit_records]
            recv.extend(new_receiver)
            snd.extend(new_sender)
            rw.flush(recv)
            sw.flush(snd)
            for row in (*new_receiver, *new_sender):
                audit_validator.validate(row)
            if v.incomplete or any(peer.incomplete for peer in peers):
                raise RuntimeError('authentication endpoint marked incomplete')
        for i in range(config.warmup_count):
            spec = dict(trial_id=f'warmup-{i:03d}', trial_index=100000+i, attack_type=CONTROL,
                        motion_seed=config.experiment_seed+i, sample_index=0, component=0, mantissa_bit=0)
            warm_context = {**context, 'temperature': 'cold' if i == 0 else 'warmup'}
            row = execute_trial(spec, config, auth_config, warm_context,
                                lambda group, row: emit('warmup', row),
                                lambda v, s: flush_peers(v, s, True))
            if row['unexpected_behavior']:
                raise RuntimeError('warmup invariant failure')
        for spec in plan:
            execute_trial(spec, config, auth_config, context, emit, flush_peers)
        for stream in streams:
            stream.close()
        for writer in writers:
            writer.close()
        # Read back persisted evidence; summaries never depend only on memory.
        rows, setup = read_jsonl(output / 'attempts.jsonl'), read_jsonl(output / 'setup_attempts.jsonl')
        audits = read_jsonl(output / 'audit.jsonl')
        if rows != collected['formal'] or setup != collected['setup'] or audits != receiver:
            raise ValueError('persisted evidence differs from observed records')
        summaries = aggregate(rows)
        for name, data in summaries.items():
            write_csv(output / name, data)
            verify_csv(output / name, data)
        reconciliation = reconcile(rows, setup, audits, plan, summaries)
        warm_rows = read_jsonl(output / 'warmup_attempts.jsonl')
        if len(warm_rows) != 20 or read_jsonl(output / 'warmup/audit.jsonl') != warm_receiver:
            raise ValueError('warmup reconciliation failed')
        if read_jsonl(output / 'sender/audit.jsonl') != sender_audits or read_jsonl(output / 'warmup/sender/audit.jsonl') != warm_sender:
            raise ValueError('sender audit reconciliation failed')
        write_json(output / 'reconciliation.json', reconciliation)
        write_json(output / 'session-audit-map.json', [
            dict(session_id=r['session_id'], owner=r['device_id'],
                 establishment_event_id=r['event_id'], source_record_id=r['provenance']['source_record_id'],
                 terminal_event_id=next(c['event_id'] for c in audits if c['event_type'] == 'session_control' and c['session_id'] == r['session_id']))
            for r in audits if r['event_type'] == 'session_establishment'])
        session_latencies = []
        for origin, records in (('sender', sender_audits), ('verifier', audits)):
            for stage in ('session_establishment', 'kdf', 'sender_prepare', 'sender_hmac', 'verifier_auth'):
                relevant = [r for r in records if r['latency_ns'][stage] is not None]
                session_latencies.append(dict(origin=origin, stage=stage, units='ns',
                                              scope='formal-fixtures-including-setup',
                                              **summarize_ns(r['latency_ns'][stage] for r in relevant)))
        write_csv(output / 'endpoint_latency_summary.csv', session_latencies)
        verify_csv(output / 'endpoint_latency_summary.csv', session_latencies)
        write_json(output / 'audit-io.json', {name: writer.io_batches for name, writer in
                    zip(('verifier', 'sender', 'warmup_verifier', 'warmup_sender'), writers)})
        metadata = dict(**context, baseline=config.baseline_version, wire_protocol='2.0',
                        protocol_profile=config.protocol_profile, source='synthetic-only',
                        candidate_source='explicit correct synthetic candidate; no reconstruction measured',
                        python=sys.version, executable=sys.executable, os=platform.platform(),
                        machine=platform.machine(), processor=platform.processor(), node=platform.node(),
                        logical_cpu_count=os.cpu_count(),
                        processor_identifier=os.environ.get('PROCESSOR_IDENTIFIER'),
                        package_versions={name: version(name) for name in ('galois', 'numpy', 'jsonschema')},
                        timer='time.perf_counter_ns', timer_resolution_seconds=time.get_clock_info('perf_counter').resolution,
                        p95_definition='linear interpolation at sorted index 0.95*(n-1)',
                        timing_claim='Python software-prototype timing on the recorded workstation',
                        timing_methodology=config.timing_methodology, warmup_count=config.warmup_count,
                        warmup_behavior='20 isolated legitimate sessions/windows; excluded from formal denominators; evidence retained',
                        trial_count=len(plan), attack_counts=dict(Counter(p['attack_type'] for p in plan)),
                        execution_command=execution_command or ' '.join(sys.argv), utc_start=started, utc_end=utc(),
                        confidence_interval_method=config.confidence_interval_method,
                        independence_limitation='fresh state per trial; shared deterministic code, seed and fixture family; conditional descriptive Wilson intervals',
                        unexpected_behavior=reconciliation['unexpected_behavior'], performance_target_verdict=None,
                        trial_plan_sha256=file_hash(output / 'trial-plan.json'),
                        preserved_session_timings='sender/audit.jsonl; verifier KDF in audit.jsonl',
                        source_baseline_hashes=before['file_sha256'])
        write_json(output / 'metadata.json', metadata)
        after = check_baseline()
        write_json(output / 'baseline-after.json', after)
        if before != after or any(file_hash(ROOT / name) != value for name, value in source_hashes.items()) or file_hash(config_path) != config_hash:
            raise ValueError('baseline/experiment source/config changed during execution')
        manifest = dict(run_id=output.name, result_schema_version=config.result_schema_version,
                        config_sha256=config_hash, baseline_manifest_sha256=before['manifest_sha256'],
                        experiment_source_sha256=source_hashes, baseline_before_after_identical=True,
                        reconciliation=reconciliation, warmup_rows_in_denominator=0,
                        files={p.relative_to(output).as_posix(): file_hash(p) for p in sorted(output.rglob('*')) if p.is_file()})
        write_json(output / 'manifest.json', manifest)
        for name, value in manifest['files'].items():
            if file_hash(output / name) != value:
                raise ValueError('artifact hashing failed')
        write_json(output / 'COMPLETE', dict(manifest_sha256=file_hash(output / 'manifest.json'),
                                           unexpected_behavior=reconciliation['unexpected_behavior']))
        return output
    except BaseException as error:
        for stream in streams:
            try:
                stream.close()
            except Exception:
                pass
        for writer in writers:
            try:
                writer.close()
            except Exception:
                pass
        failure = dict(status='INCOMPLETE', error_type=type(error).__name__, utc=utc(),
                       instruction='Preserve all partial evidence; no automatic rerun or retuning.')
        if isinstance(error, BaselineMismatch):
            failure['baseline_mismatch'] = error.report
        try:
            write_json(output / 'INCOMPLETE.json', failure)
        except OSError:
            pass
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT / CONFIG)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-baseline', action='store_true')
    args = parser.parse_args()
    if args.check_baseline:
        try:
            print(json.dumps(check_baseline(), indent=2))
            return 0
        except BaselineMismatch as error:
            print(json.dumps(error.report, indent=2))
            return 1
    output = args.output or ROOT / 'results/week-4/will/authentication' / (
        datetime.now(timezone.utc).strftime('tier1-%Y%m%dT%H%M%SZ-') + secrets.token_hex(4))
    try:
        run_experiment(output, args.config, execution_command=' '.join([sys.executable, '-B', *sys.argv]))
    except BaselineMismatch as error:
        print(json.dumps(error.report, indent=2))
        return 1
    except Exception as error:
        print(f'Tier 1 stopped ({type(error).__name__}); preserve evidence at {output}', file=sys.stderr)
        return 1
    print(f'Tier 1 evidence COMPLETE: {output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
