"""Preregistered Tier-1 v2 orchestration. No protocol policy lives here.

All runtime secrets stay in provisioning/endpoint memory. Mutation functions take
only public wire bytes and scalar public parameters. Serial execution only.
"""
from __future__ import annotations

import base64
from collections import Counter, defaultdict
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import csv
from functools import wraps
import hashlib
import json
import math
from pathlib import Path
import platform
from random import Random
import secrets
import subprocess
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
LABEL = "NONFORMAL IMPLEMENTATION VALIDATION"
REAL_LABEL = "NONFORMAL REAL-ARTIFACT FEASIBILITY VALIDATION"
FORMAL_ID = "tier1-v2-formal-001"
FORMAL_ROOT = ROOT / "results/week-6/will/authentication" / FORMAL_ID
FROZEN_CONFIG = json.loads(r'''{
  "config_version": "puf-snn-tier1-v2-config-v1",
  "experiment_id": "authentication-v2-tier1-security-evaluation",
  "experiment_version": 1,
  "run_id": "tier1-v2-formal-001",
  "plan_path": "docs/week6-tier1-v2-experiment-plan.md",
  "design_baseline_commit": "78f499a92f633a4793c776a070058e3a6a9a0b61",
  "execution_source_commit": null,
  "source_manifest_path": null,
  "protocol_profile": "puf-snn-l3-credential-admission-v1-wire2",
  "auth_config": "configs/authentication_v2.json",
  "auth_config_sha256": "b0ee45b8a3ee5cf6c4c25813e876847303ada4209abc4632bce903a331cf0f60",
  "puf_config": "configs/puf_baseline.json",
  "admission_fixture": "one_fresh_reference_condition_read_then_real_reconstruction",
  "frozen_config": "configs/week6_smoke.json",
  "frozen_config_sha256": "2b880104269800e654e4841644a0c7b6fcaad096ea25dc2970fc79126ce04d90",
  "model_condition": "snn32_seed7_forest_anomaly",
  "device_count": 6,
  "enrollment_generations_per_device": 2,
  "primary_groups": [
    "A1",
    "A2",
    "A3",
    "A4",
    "A5"
  ],
  "primary_trials_per_group": 1200,
  "control_trials": 1200,
  "trials_per_device_generation_cell": 100,
  "sequence_positions": [
    0,
    1,
    2,
    3,
    4
  ],
  "state_groups": [
    "S1",
    "S2",
    "S3",
    "S4",
    "S5",
    "S6",
    "S7",
    "S8"
  ],
  "state_scenarios_per_group": 120,
  "parser_groups": [
    "P01",
    "P02",
    "P03",
    "P04",
    "P05",
    "P06",
    "P07",
    "P08",
    "P09",
    "P10",
    "P11",
    "P12",
    "P13",
    "P14",
    "P15",
    "P16",
    "P17",
    "P18",
    "P19",
    "P20",
    "P21",
    "P22",
    "P23",
    "P24",
    "P25",
    "P26",
    "P27",
    "P28"
  ],
  "parser_scenarios_per_group": 60,
  "variation_contract": "tier1-v2-balanced-scenarios-v1",
  "measured_source_split": "test",
  "window_selection": "all_600_by_device_permuted_twice_per_primary_or_control_group",
  "seeds": {
    "puf": 6767,
    "controlled_read": 2026100601,
    "trial": 2026100602,
    "mutation": 2026100603,
    "window": 2026100604
  },
  "secret_and_protocol_randomness": "os_secrets_unmodified",
  "expiry_fixture": "receiver_monotonic_proxy_equality_or_plus_1ms",
  "timing": {
    "warmup_controls": 20,
    "warmup_split": "validation",
    "repetitions_per_submission": 1,
    "batch_size": 1,
    "native_threads": 1,
    "torch_threads": 1,
    "gc_enabled": true,
    "quantiles": "linear_q_times_n_minus_1",
    "p99_min_n": 100
  },
  "confidence_interval": {
    "method": "clopper_pearson",
    "confidence": 0.95,
    "sides": 2
  },
  "attempt_schema": "puf-snn-tier1-v2-attempt-v1",
  "output_root": "results/week-6/will/authentication",
  "execution_failure_policy": "retain_partial_no_complete_no_retry"
}
''')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(value if isinstance(value, bytes) else canonical(value).encode()).hexdigest()


def file_hash(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(_):
        raise ValueError("nonfinite JSON")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=invalid)


def validate_config(config, *, formal=False, nonformal=False):
    if formal and nonformal:
        raise ValueError("exclusive modes")
    if type(config) is not dict or set(config) != set(FROZEN_CONFIG):
        raise ValueError("config exact key set required")
    fixed = deepcopy(config)
    for key in ("execution_source_commit", "source_manifest_path"):
        value = fixed[key]
        if value is not None and (type(value) is not str or not value):
            raise ValueError("invalid provenance pin")
        fixed[key] = None
    if nonformal:
        if config["run_id"] == FORMAL_ID or not config["run_id"].startswith("nonformal-"):
            raise ValueError("nonformal identity required")
        for key in ("run_id", "output_root"):
            fixed[key] = FROZEN_CONFIG[key]
        for key in ("primary_trials_per_group", "control_trials", "trials_per_device_generation_cell",
                    "state_scenarios_per_group", "parser_scenarios_per_group"):
            if type(config[key]) is not int or not 1 <= config[key] <= FROZEN_CONFIG[key]:
                raise ValueError("illegal nonformal population")
            fixed[key] = FROZEN_CONFIG[key]
        n = config["trials_per_device_generation_cell"]
        if config["primary_trials_per_group"] != 12*n or config["control_trials"] != 12*n:
            raise ValueError("cell arithmetic")
        if config["state_scenarios_per_group"] % 12 or config["parser_scenarios_per_group"] % 12:
            raise ValueError("whole device-generation cells required")
    # Canonical bytes distinguish true from 1, recursively, including nested fields.
    if canonical(fixed) != canonical(FROZEN_CONFIG):
        raise ValueError("preregistered config/profile/populations/settings changed")
    if formal and (not config["execution_source_commit"] or not config["source_manifest_path"]):
        raise ValueError("unresolved execution source pins")
    return config


def nonformal_config(run_id="nonformal-validation"):
    config = deepcopy(FROZEN_CONFIG)
    config.update(run_id=run_id, output_root="tmp/tier1-v2-nonformal",
                  primary_trials_per_group=12, control_trials=12,
                  trials_per_device_generation_cell=1, state_scenarios_per_group=12,
                  parser_scenarios_per_group=12)
    return validate_config(config, nonformal=True)


def rng_for(identity):
    rng = Random()
    rng.seed(identity, version=2)
    return rng


def stream_id(config, stream, phase, group, d=0, g=0, t=0, role="source"):
    return f"tier1-v2-v1:{stream}:{config['seeds'][stream]}:{phase}:{group}:{d}:{g}:{t}:{role}"


VARIANTS = {
    "A1": ["exact_replay"], "A2": ["replacement", "expired_live", "expired_cleanup"],
    "A3": ["device"], "A4": ["position", "quaternion"],
    "A5": ["sequence", "window_id", "capture_start", "capture_end", "valid_count", "valid_ppm"],
    "S1": ["high63", "u64max"], "S2": ["gap1", "gap2", "gap3"],
    "S3": ["tag", "position"], "S4": ["reject_duplicate"], "S5": ["stale"],
    "S6": ["gap1", "gap2", "gap3"], "S7": ["truncate"], "S8": ["sid_and_wrapper", "wrapper"],
    "P02": ["colon", "comma"], "P03": ["outer", "protected", "authentication"],
    "P04": ["outer", "protected", "authentication"], "P09": ["short", "long"],
    "P10": ["uppercase", "nonhex"], "P12": ["protocol", "authenticated"],
    "P14": ["one", "thirtynine"], "P15": ["short", "long"], "P17": ["119", "121"],
    "P19": ["negative_zero", "infinity", "nan"], "P22": ["bom", "utf8"],
    "P23": ["short", "uppercase"],
}


def balanced(values, n, identity):
    quotient,remainder=divmod(n,len(values))
    result = [value for i,value in enumerate(values) for _ in range(quotient+int(i<remainder))]
    rng_for(identity).shuffle(result)
    return result


def expected(reason, *, window=True):
    accepted = reason == "accepted"
    hmac = ("pass" if reason in {"accepted", "duplicate_sequence", "stale_sequence", "future_sequence_gap",
                                  "invalid_key_id"} else "fail" if reason == "invalid_tag" else "not_checked")
    order = {"accepted": "pass", "duplicate_sequence": "duplicate", "stale_sequence": "stale",
             "future_sequence_gap": "gap"}.get(reason, "not_checked")
    return dict(result="accept" if accepted else "reject", reason=reason,
                hmac=hmac if window else None, identity_authenticated=(hmac == "pass" and reason != "invalid_key_id") if window else None,
                order=order if window else None, replay_state_change=accepted and window,
                **{k: int(accepted and window) for k in ("release", "preprocessing", "motion", "anomaly")})


def negative_reason(group, variant):
    if group == "A1": return "duplicate_sequence"
    if group == "A2": return "inactive_session" if variant == "replacement" else "expired_session"
    if group in {"S2", "S6"}: return "future_sequence_gap"
    if group == "S5": return "stale_sequence"
    if group == "S7": return "malformed_message"
    if group == "S8" and variant == "wrapper": return "invalid_key_id"
    if group == "P12": return "unsupported_protocol_version"
    if group in {"P13", "P16", "P17", "P18", "P19", "P20", "P21"}: return "invalid_payload_schema"
    if group.startswith("P"): return "malformed_message"
    return "invalid_tag"


def compile_trial_plan(config, *, nonformal=False):
    """Materialize all public choices and operations before any observations."""
    validate_config(config, nonformal=nonformal)
    scenarios = []
    groups = config["primary_groups"] + ["control"] + config["state_groups"] + config["parser_groups"]
    for group in groups:
        n = (config["state_scenarios_per_group"] if group.startswith("S") else
             config["parser_scenarios_per_group"] if group.startswith("P") else config["control_trials"])
        cell = n // 12
        mutation_id = stream_id(config, "mutation", "measured", group)
        variants = balanced(VARIANTS.get(group, ["boundary" if group.startswith("P") else "valid"]), n, mutation_id)
        if group == "A2": variants = [VARIANTS[group][r % 3] for r in range(n)]
        pose_schedules = {}
        for subtype in ("position", "quaternion"):
            total = variants.count(subtype)
            pose_schedules[subtype] = list(zip(
                balanced(list(range(120)), total, mutation_id+":"+subtype+":sample"),
                balanced(list(range(3 if subtype == "position" else 4)), total, mutation_id+":"+subtype+":component"),
                balanced(list(range(23)), total, mutation_id+":"+subtype+":bit")))
        used = Counter()
        for d in range(6):
            for g in range(2):
                permutation = list(range(100))
                rng_for(stream_id(config, "window", "measured", group, d, g)).shuffle(permutation)
                seconds = balanced([i for i in range(6) if i != d], cell,
                                   stream_id(config, "trial", "measured", group, d, g, role="second"))
                for t in range(cell):
                    r = cell*(2*d+g)+t
                    variant = variants[r]
                    position = 2+t%5 if group.startswith("S") else t%5
                    sid = f"{group}-d{d}-g{g}-t{t:03d}"
                    seeds = {k: stream_id(config, k, "measured", group, d,g,t) for k in ("trial","mutation","window","controlled_read")}
                    rng = rng_for(seeds["mutation"])
                    params = dict(sample_index=rng.randrange(120), component=rng.randrange(7), bit=rng.randrange(23),
                                  tag_bit=rng.randrange(256), cut=rng.randrange(1,17), selector=r%4)
                    if group == "A4":
                        sample, component, bit = pose_schedules[variant][used[variant]]
                        used[variant] += 1
                        params.update(sample_index=sample, component=component+(3 if variant=="quaternion" else 0), bit=bit)
                    gap = int(variant[-1]) if variant.startswith("gap") else 0
                    scenario = dict(scenario_id=sid, phase="measured", group=group, variant=variant,
                                    device_index=d, enrollment_generation=g, session_trial_index=t,
                                    sequence_position=position, source_window_index=permutation[t],
                                    window_permutation=permutation, second_device_index=seconds[t] if group=="A3" else (d+1)%6,
                                    replacement_device_index=d, mutation=params, seed_ids=seeds,
                                    clock_mode=("expiry_equality" if (r//3)%2==0 else "expiry_plus_1ms") if group=="A2" and variant!="replacement" else "real",
                                    withheld_disposition="close_without_submission" if group=="S2" else None, operations=[])
                    ops = scenario["operations"]
                    def add(role, action, reason="accepted", sequence=None, sender="source", boundary="pipeline.process_envelope"):
                        ordinal=len(ops)
                        ops.append(dict(operation_id=f"{sid}-op{ordinal:03d}", step_index=ordinal, role=role, action=action,
                                        sequence_number=sequence, sender_alias=sender, session_alias=sender,
                                        source_window_index=permutation[(t+ordinal)%100], boundary=boundary,
                                        expected=expected(reason, window=boundary=="pipeline.process_envelope"), parent_attack_trial_id=None))
                    handshake_parser = group in {"P25","P26","P27","P28"}
                    add("setup_handshake", "prepare_handshake" if handshake_parser else "establish", boundary="endpoints")
                    if group in {"A3", "S8"}: add("setup_handshake", "establish", sender="second", boundary="endpoints")
                    prefix=0 if handshake_parser else position+int(group in {"A1","A2"})
                    for k in range(prefix):
                        add("setup_window", "prefix", sequence=k)
                        if group in {"A1","A2"} and k==position:
                            ops[-1]["source_window_index"]=permutation[t]
                        if group=="S5" and k==position-2:
                            ops[-1]["source_window_index"]=permutation[t]
                    if group=="A2" and variant=="replacement": add("setup_handshake", "establish", sender="replacement", boundary="endpoints")
                    if group=="A2" and variant=="expired_cleanup": add("lifecycle", "expire", boundary="verifier.expire_due_sessions")
                    role="legitimate_control" if group=="control" else "primary_attack" if group.startswith("A") else "state_negative" if group.startswith("S") else "parser_negative"
                    add(role, "attack" if group!="control" else "control", "accepted" if group=="control" else negative_reason(group,variant),
                        sequence=position, boundary=("verifier.begin_session" if group in {"P25","P26"} else "verifier.confirm_session") if handshake_parser else "pipeline.process_envelope")
                    attack_id=ops[-1]["operation_id"]
                    ops[-1]["source_window_index"]=permutation[t]
                    if group=="S4": add(role,"duplicate","duplicate_sequence",sequence=position-1)
                    if group=="A2":
                        if variant!="replacement":
                            if variant=="expired_live": add("lifecycle","expire",boundary="verifier.expire_due_sessions")
                            add("recovery_handshake","establish",sender="replacement",boundary="endpoints")
                        add("recovery_window","recovery",sequence=0,sender="replacement")
                    elif handshake_parser:
                        add("recovery_handshake","finish_handshake",boundary="endpoints")
                        add("recovery_window","recovery",sequence=0)
                    elif group!="control":
                        sequences=range(position,position+gap+1) if group=="S6" else [position+1 if group=="A1" else position]
                        for k in sequences: add("recovery_window","recovery",sequence=k)
                        if group in {"A3","S8"}: add("recovery_window","recovery",sequence=0,sender="second")
                    add("lifecycle","close",boundary="verifier.close_all_sessions")
                    # The second device has its own case/generation permutation.
                    second_permutation=list(range(100))
                    rng_for(stream_id(config,"window","measured",group,scenario["second_device_index"],g)).shuffle(second_permutation)
                    scenario["second_window_index"]=second_permutation[t]
                    for op in ops:
                        if op["sender_alias"]=="second": op["source_window_index"]=second_permutation[t]
                    packets={}
                    for op in ops:
                        if op["action"]=="prefix":
                            packets[op["sender_alias"],op["sequence_number"]]=op["source_window_index"]
                    if not handshake_parser and group not in {"A1","A2"}:
                        for k in range(position,position+gap+1): packets["source",k]=permutation[(t+k-position)%100]
                        if group in {"S2","S6"}:
                            for k in range(position,position+gap): packets["source",k]=permutation[(t+k-position+1)%100]
                            packets["source",position+gap]=permutation[t]
                    if group in {"A3","S8"}: packets["second",0]=second_permutation[t]
                    for op in ops:
                        if op["boundary"]!="pipeline.process_envelope": continue
                        seq=op["sequence_number"]
                        if op["action"]=="attack":
                            seq=position-2 if group=="S5" else position+gap if group in {"S2","S6"} else position
                        key=op["sender_alias"],seq
                        packets.setdefault(key,op["source_window_index"])
                        op["source_window_index"]=packets[key]
                    scenario["packet_plan"]=[dict(sender_alias=alias,sequence_number=seq,source_window_index=index,
                        disposition="withheld_close" if group=="S2" and alias=="source" and position<seq<position+gap else "planned_submission")
                        for (alias,seq),index in sorted(packets.items())]
                    recovery_ids=[o["operation_id"] for o in ops if o["role"].startswith("recovery")]
                    for op in ops:
                        op["recovery_step_ids"]=recovery_ids if op["role"] in {"primary_attack","state_negative","parser_negative"} else []
                        if op["role"].startswith("recovery"): op["parent_attack_trial_id"]=attack_id
                    scenarios.append(scenario)
    rng_for(stream_id(config,"trial","measured","all",role="execution_order")).shuffle(scenarios)
    # Warmups precede measured scenarios, with independent validation sources.
    warm=[]
    for i in range(config["timing"]["warmup_controls"] if not nonformal else 1):
        s=deepcopy(next(s for s in scenarios if s["group"]=="control"))
        s.update(scenario_id=f"warmup-{i:02d}",phase="warmup",sequence_position=0,source_window_index=i,
                 device_index=0,enrollment_generation=0,session_trial_index=i,variant="first_use" if i==0 else "warmup")
        s["seed_ids"]={k:stream_id(config,k,"warmup","control",t=i) for k in s["seed_ids"]}
        s["operations"]=[o for o in s["operations"] if o["action"] in {"establish","control","close"}]
        s["packet_plan"]=[dict(sender_alias="source",sequence_number=0,source_window_index=i,disposition="planned_submission")]
        for j,o in enumerate(s["operations"]):
            o.update(operation_id=f"warmup-{i:02d}-op{j:03d}",step_index=j,source_window_index=i)
            if o["action"]=="control": o["sequence_number"]=0
        warm.append(s)
    scenarios=warm+scenarios
    index=0
    for s in scenarios:
        for op in s["operations"]:
            op["execution_index"]=index
            index+=1
    counts=Counter(o["role"] for s in scenarios if s["phase"]=="measured" for o in s["operations"])
    plan=dict(schema_version="puf-snn-tier1-v2-trial-plan-v1",run_id=config["run_id"],
              validation_label=LABEL if nonformal else "FORMAL",config_sha256=digest(config),
              python_version=platform.python_version(),scenarios=scenarios,
              counts=[dict(role=k,count=v) for k,v in sorted(counts.items())])
    plan["plan_sha256"]=digest(plan)
    return plan


def clopper_pearson(x, n):
    if type(x) is not int or type(n) is not int or not 0<=x<=n:
        raise ValueError("integer binomial counts required")
    from scipy.stats import beta
    return dict(method="clopper_pearson", confidence=.95, alpha=.05, sides=2, tails="equal", n=n,x=x,
                rate=x/n if n else None,
                lower=(0.0 if x==0 else float(beta.ppf(.025,x,n-x+1))) if n else None,
                upper=(1.0 if x==n else float(beta.ppf(.975,x+1,n-x))) if n else None)


def wire_parts(packet):
    envelope=strict_json(packet)
    a=bytearray(base64.b64decode(envelope["protected"]["bytes_b64"],validate=True))
    d=int.from_bytes(a[19:21],"big")
    sid=21+d
    wlen=sid+24
    w=int.from_bytes(a[wlen:wlen+2],"big")
    start=wlen+2+w
    offsets=dict(device=(21,d),sid=(sid,16),sequence=(sid+16,8),window_id=(wlen+2,w),
                 capture_start=(start,8),capture_end=(start+8,8),sample_count=(start+17,2),
                 valid_count=(start+19,2),valid_ppm=(start+21,4),payload_length=(start+25,4),
                 payload=(start+29,3),samples=(start+32,4680))
    return envelope,a,offsets


def mutation_record(category="none", field=None, operation="retain"):
    return dict(category=category,field=field,operation=operation,
                **{k:None for k in ("byte_offset","width","sample_index","component","requested_bit","actual_bit","before_hex","after_hex")})


def mutate_public(packet: bytes, group: str, variant: str, *, sample_index=0, component=0,
                  bit=0, tag_bit=0, cut=1, selector=0, target_device=None, target_sid=None):
    """Public-only byte mutation boundary: no endpoint/fixture/secret arguments."""
    if type(packet) is not bytes or any(type(x) is not int for x in (sample_index,component,bit,tag_bit,cut,selector)):
        raise ValueError("public bytes and scalar mutation parameters required")
    env,a,offsets=wire_parts(packet)
    record=mutation_record(group,variant,"byte_mutation")
    raw_override=None
    def change(field, new, at=None):
        offset,width=offsets[field] if at is None else (at,len(new))
        record.update(field=field,byte_offset=offset,width=width,before_hex=bytes(a[offset:offset+width]).hex(),after_hex=new.hex())
        a[offset:offset+width]=new
    def number(field,value):
        number_offset,width=offsets[field]
        change(field,value.to_bytes(width,"big"))
    def value(field):
        at,width=offsets[field]
        return int.from_bytes(a[at:at+width],"big")
    def pose():
        at=offsets["samples"][0]+sample_index*39+10+component*4
        word=int.from_bytes(a[at:at+4],"big")
        for shift in range(23):
            actual=(bit+shift)%23
            changed=word^(1<<actual)
            if changed!=0x80000000 and changed&0x7f800000!=0x7f800000:
                change("pose",changed.to_bytes(4,"big"),at)
                record.update(sample_index=sample_index,component=component,requested_bit=bit,actual_bit=actual)
                return
        raise ValueError("no legal mantissa mutation")
    if group=="A3":
        if type(target_device) is not str or len(target_device.encode("ascii"))!=offsets["device"][1]:
            raise ValueError("equal-width public device required")
        change("device",target_device.encode("ascii"))
    elif group=="A4" or (group=="S3" and variant=="position"):
        if group=="S3": component%=3
        pose()
    elif group=="A5":
        if variant=="window_id":
            at,_=offsets[variant]
            change(variant,b"b" if a[at]==ord("a") else b"a",at)
        elif variant=="valid_ppm": number(variant,value(variant)^1)
        elif variant=="valid_count": number(variant,119 if value(variant)==120 else value(variant)+1)
        else: number(variant,value(variant)+1)
    elif group=="S1": number("sequence",2**63 if variant=="high63" else 2**64-1)
    elif group=="S8":
        if type(target_sid) is not str or len(target_sid)!=32: raise ValueError("public SID required")
        env["authentication"]["key_id"]=target_sid
        if variant=="sid_and_wrapper": change("sid",bytes.fromhex(target_sid))
    elif group in {"S3","S4"}:
        tag=bytearray.fromhex(env["authentication"]["tag_hex"])
        tag[tag_bit//8]^=1<<(tag_bit%8)
        env["authentication"]["tag_hex"]=tag.hex()
        record.update(field="tag",requested_bit=tag_bit,actual_bit=tag_bit)
    elif group in {"S7","P01"}:
        at=packet.index(b'bytes_b64')+13+cut
        raw_override=packet[:at]
        record.update(byte_offset=at,width=len(packet)-at)
    elif group=="P02":
        mark=b":" if variant=="colon" else b","; at=packet.index(mark)
        raw_override=packet[:at]+packet[at+1:]; record.update(byte_offset=at,width=1)
    elif group=="P03":
        obj=env if variant=="outer" else env[variant]
        key=next(iter(obj)); token=canonical(key)+":"+canonical(obj[key])
        text=canonical(env); pos=text.index(token)
        raw_override=(text[:pos]+token+","+text[pos:]).encode()
    elif group=="P04": (env if variant=="outer" else env[variant])["unknown"]="boundary"
    elif group=="P05": env["protected"]["encoding"]="puf-snn-binary32-le-v2"
    elif group=="P06": env["authentication"]["algorithm"]="HMAC-SHA256"
    elif group=="P07":
        text=env["protected"]["bytes_b64"]; at=sample_index*4
        env["protected"]["bytes_b64"]=text[:at]+"!"+text[at+1:]
    elif group=="P08": env["protected"]["bytes_b64"]+="="
    elif group=="P09":
        tag=env["authentication"]["tag_hex"]
        env["authentication"]["tag_hex"]=tag[:-2] if variant=="short" else tag+"00"
    elif group=="P10":
        tag=env["authentication"]["tag_hex"]; at=tag_bit%64
        env["authentication"]["tag_hex"]=tag[:at]+("A" if variant=="uppercase" else "g")+tag[at+1:]
    elif group=="P11": change("magic",bytes([a[selector]^1]),selector)
    elif group=="P12": change("version",b"\x00\x03",4 if variant=="protocol" else 8)
    elif group=="P13": change("payload_version",b"\x00\x02",12)
    elif group=="P14":
        width=1 if variant=="one" else 39
        record.update(byte_offset=len(a)-width,width=width,before_hex=bytes(a[-width:]).hex(),after_hex="")
        del a[-width:]
    elif group=="P15": number("payload_length",4682 if variant=="short" else 4684)
    elif group=="P16": change("sample_count",b"\x78\x00")
    elif group=="P17": number("sample_count",int(variant))
    elif group=="P18": change("sample_index",((sample_index+1)%120).to_bytes(2,"big"),offsets["samples"][0]+sample_index*39)
    elif group=="P19":
        change("pose",bytes.fromhex({"negative_zero":"80000000","infinity":"7f800000","nan":"7fc00000"}[variant]),
               offsets["samples"][0]+sample_index*39+10+component*4)
    elif group=="P20": change("tracking_valid",b"\x02",offsets["samples"][0]+sample_index*39+38)
    elif group=="P21": change("payload",bytes.fromhex("01003b"))
    elif group=="P22": raw_override=b"\xef\xbb\xbf"+packet if variant=="bom" else packet[:1]+b"\xff"+packet[2:]
    elif group=="P23":
        kid=env["authentication"]["key_id"]
        env["authentication"]["key_id"]=kid[:-1] if variant=="short" else "A"+kid[1:]
    elif group=="P24":
        record.update(byte_offset=len(a),width=1,before_hex="",after_hex="00"); a.append(0)
    else: raise ValueError("unknown mutation")
    if group not in {"P07","P08"}: env["protected"]["bytes_b64"]=base64.b64encode(a).decode()
    changed=raw_override if raw_override is not None else canonical(env).encode()
    if record["byte_offset"] is None:
        # Wrapper offsets refer to UTF-8 envelope bytes; binary offsets above to A.
        start=0
        while start<min(len(packet),len(changed)) and packet[start]==changed[start]: start+=1
        end=0
        while end<min(len(packet),len(changed))-start and packet[-end-1]==changed[-end-1]: end+=1
        record.update(byte_offset=start,width=len(packet)-start-end)
    return changed,record


def mutate_handshake(packet, group, cut):
    if type(packet) is not bytes or type(cut) is not int or not 1<=cut<=16:
        raise ValueError("public handshake inputs required")
    if group not in {"P25","P26","P27","P28"}: raise ValueError("unknown handshake case")
    amount=1 if group=="P28" else cut
    changed=packet[:-amount]
    if group in {"P26","P28"}: changed=(len(changed)-4).to_bytes(4,"big")+changed[4:]
    record=mutation_record(group,"frame" if group in {"P25","P27"} else "body","truncate")
    record.update(byte_offset=len(packet)-amount,width=amount,before_hex=packet[-amount:].hex(),after_hex="")
    return changed,record


@contextmanager
def expiry_clock(deadline, mode):
    from puf_snn.auth import verifier as module
    if mode not in {"expiry_equality","expiry_plus_1ms"}: raise ValueError("expiry mode")
    original=module.time
    offset=deadline+(1_000_000 if mode=="expiry_plus_1ms" else 0)-original.monotonic_ns()
    class Proxy:
        perf_counter_ns=staticmethod(original.perf_counter_ns)
        def monotonic_ns(self):
            return deadline if mode=="expiry_equality" else original.monotonic_ns()+offset
    module.time=Proxy()
    try: yield offset
    finally: module.time=original


def pending_session_ids(verifier):
    """The sole private state observation: keys only, never pending values."""
    with verifier._lock:
        return tuple(verifier._pending.keys())


@contextmanager
def observe_pipeline(pipeline, capture):
    """Pass through the exact result once; entry counters preserve failures."""
    from puf_snn.auth.verifier import Verifier
    entries=Counter(release=0,preprocessing=0,motion=0,anomaly=0)
    observations=[]
    last_result=[None]
    def counted(name, function):
        @wraps(function)
        def call(*args,**kwargs):
            entries[name]+=1
            with capture.span(name+"_callback_entry"):
                return function(*args,**kwargs)
        return call
    original_verify=Verifier.verify_window
    original_release=Verifier.release_accepted
    def verify(owner,*args,**kwargs):
        result=original_verify(owner,*args,**kwargs)
        if owner is pipeline.verifier:
            last_result[0]=result
            observations.append({k:getattr(result,k) for k in ("result","reason","event_id","sequence_number","verifier_auth_ns","authenticated_bytes_sha256")}
                                | dict(accepted_window_present=result.accepted_window is not None,
                                       authenticated_bytes_present=result.authenticated_bytes is not None,
                                       result_authority_consistent=None))
        return result
    def release(owner,*args,**kwargs):
        if owner is pipeline.verifier:
            entries["release"]+=1
            if observations:
                observations[-1]["result_authority_consistent"]=(args[0] if args else kwargs.get("result")) is last_result[0]
        return original_release(owner,*args,**kwargs)
    with ExitStack() as stack:
        stack.enter_context(patch.object(Verifier,"verify_window",verify))
        stack.enter_context(patch.object(Verifier,"release_accepted",release))
        for name,attribute in (("preprocessing","_prepare"),("motion","_motion"),("anomaly","_anomaly")):
            stack.enter_context(patch.object(pipeline,attribute,counted(name,getattr(pipeline,attribute))))
        yield entries,observations


def snapshot_safe_state(pipeline, senders, aliases, entries, ledger):
    from puf_snn.auth import verifier as module
    verifier=pipeline.verifier
    terminal={t.session_id.hex():t for t in verifier.tombstones}
    sessions=[]
    for alias, binding in sorted(aliases.items()):
        sid,device,generation=binding
        status=verifier.session_status(sid)
        tombstone=terminal.get(sid.hex())
        coherent=status.accepted_count is not None and status.last_accepted==(status.accepted_count-1 if status.accepted_count else None)
        if status.state=="ACTIVE":
            ledger[alias]=dict(accepted_count=status.accepted_count,last_accepted=status.last_accepted,
                               event_id=next((r["event_id"] for r in reversed(verifier.audit_records) if r["event_type"]=="window" and r["session_id"]==sid.hex() and r["decision"]=="accept"),None))
        sessions.append(dict(session_alias=alias,session_id_hex=sid.hex(),owner_device_id=device,
            enrollment_generation=generation,state=status.state,accepted_count=status.accepted_count,last_accepted=status.last_accepted,
            expected_sequence=status.accepted_count if status.state=="ACTIVE" and coherent else None,
            deadline_ns=status.deadline_ns,deadline_elapsed=module.time.monotonic_ns()>=status.deadline_ns if status.deadline_ns is not None else None,
            terminal_reason=tombstone.reason if tombstone else None,terminal_time_ns=tombstone.terminal_time_ns if tombstone else None,
            last_observed_active=deepcopy(ledger.get(alias))))
    consumed=pipeline.consumed_event_ids
    return dict(sessions=sessions,active_session_ids=sorted(s.hex() for s in verifier.active_session_ids),
                pending_session_ids=sorted(s.hex() for s in pending_session_ids(verifier)),
                senders=[dict(sender_alias=a,device_id=s.enrollment.device_id,state=s.state,
                              session_id_hex=s.session_id.hex() if s.session_id else None,next_to_send=s.next_to_send) for a,s in sorted(senders.items())],
                calls=dict(release=entries["release"],**{k:getattr(pipeline.calls,k) for k in ("preprocessing","motion","anomaly")}),
                consumed_event_count=len(consumed),consumed_event_ids_sha256=digest(sorted(consumed)),
                sender_incomplete=[dict(sender_alias=a,value=s.incomplete) for a,s in sorted(senders.items())],
                verifier_incomplete=verifier.incomplete)


def stable_state(snapshot):
    result=deepcopy(snapshot)
    for s in result["sessions"]: s.pop("deadline_elapsed")
    return result


class Materials:
    """In-memory trusted provisioning; never serializable evidence."""
    def __init__(self, root=ROOT):
        from puf_snn.auth.credential_verifier import InMemoryCredentialVerifierKeyProvider, CredentialVerifierRecord
        from puf_snn.puf.device import create_device
        from puf_snn.puf.ro_puf import generate_pairs, generate_response
        from puf_snn.puf.variables import load_config
        from puf_snn.reconstruction import enroll
        self.puf=load_config(root / FROZEN_CONFIG["puf_config"])
        p=self.puf
        if (p.number_of_devices,p.number_of_oscillators,p.pairing_scheme,p.random_seed,p.nominal_frequency,
            p.manufacturing_std,p.aging_std,p.reference_conditions.environmental_offset,p.reference_conditions.measurement_noise_std)!=(6,128,"adjacent",6767,100,1,0,0,0):
            raise ValueError("PUF baseline changed")
        self.pairs=generate_pairs(128,"adjacent")
        self.provider=InMemoryCredentialVerifierKeyProvider.generate("tier1-v2-verifier-key")
        self.devices={}; self.enrollments={}; self.records=[]
        used=set()
        for d in range(6):
            device=create_device(f"t1v2-d{d}",128,1,rng=rng_for(f"week2-v1:6767:{d}:manufacturing"))
            self.devices[d]=device
            reference=generate_response(device,self.pairs,p.nominal_frequency,p.reference_conditions,rng=rng_for(f"week2-v1:6767:{d}:enrollment"))
            for g in range(2):
                credential=secrets.token_bytes(4)
                while credential in used: credential=secrets.token_bytes(4)
                used.add(credential)
                eid=f"tier1-v2-enrollment-d{d}-g{g}"
                helper=enroll(reference,credential,enrollment_id=eid)
                self.enrollments[d,g]=(eid,helper,credential)
                self.records.append(CredentialVerifierRecord.enroll(device_id=device.device_id,enrollment_id=eid,
                    reconstruction_id=helper.config.version,verifier_key_id="tier1-v2-verifier-key",credential4=credential,key_provider=self.provider))

    def read(self,d,identity):
        from puf_snn.puf.ro_puf import generate_response
        return generate_response(self.devices[d],self.pairs,self.puf.nominal_frequency,
                                 self.puf.reference_conditions,rng=rng_for(identity))

    def __repr__(self): return "Materials(<redacted>)"


def additional_handshake(sender, verifier, read_response, attempt_id):
    """Same supported admission/endpoints as establish; one read/decode, no retry."""
    from puf_snn.reconstruction import reconstruct
    from puf_snn.auth.session import Failure, REFUSAL
    result=reconstruct(read_response(),sender.enrollment.helper_data)
    request=sender.begin_attempt(result,attempt_id)
    if isinstance(request,Failure): raise RuntimeError("controlled_admission_failure")
    challenge=verifier.begin_session(request,admission=sender.admission)
    if challenge==REFUSAL: raise RuntimeError("controlled_admission_failure")
    confirmation=sender.answer_challenge(challenge)
    if isinstance(confirmation,Failure): raise RuntimeError("controlled_admission_failure")
    response=verifier.confirm_session(confirmation)
    if sender.finish_session(response) is not sender: raise RuntimeError("controlled_admission_failure")


def nonformal_record(index=0, device=0, split="test"):
    """Explicitly synthetic in-memory validation data; never formal model data."""
    return dict(window_id=f"nonformal-d{device}-{split}-{index:03d}",device_id=f"fixture-d{device}",split=split,label="nod",
                window_start_ns=1_000_000_000,window_end_ns=3_000_000_000,
                samples=[dict(sample_index=i,capture_time_ns=1_000_000_000+i*16_666_667,
                              position_m=[i/1000.,index/1000.,.1],orientation_xyzw=[0.,0.,0.,1.],tracking_valid=True) for i in range(120)])


def empty_observed():
    return dict.fromkeys(("result","reason","stage","authentication","identity_authenticated","order",
                          "missing_start","missing_end","missing_count","authenticated_bytes_sha256",
                          "accepted_window_present","authenticated_bytes_present","result_authority_consistent","model_output_identity_consistent"))


def attempt_row(config,plan,scenario,op):
    return dict(schema_version=config["attempt_schema"],experiment_id=config["experiment_id"],experiment_version=1,
        run_id=config["run_id"],validation_label=plan["validation_label"],config_sha256=digest(config),trial_plan_sha256=plan["plan_sha256"],
        trial_id=op["operation_id"],scenario_id=scenario["scenario_id"],step_index=op["step_index"],execution_index=op["execution_index"],
        phase=scenario["phase"],role=op["role"],attack_group=scenario["group"],attack_variant=scenario["variant"],
        injection_boundary=op["boundary"],parent_attack_trial_id=op["parent_attack_trial_id"],seed_ids=scenario["seed_ids"],
        device_index=scenario["device_index"],device_id=f"t1v2-d{scenario['device_index']}",enrollment_generation=scenario["enrollment_generation"],
        session_trial_index=scenario["session_trial_index"],source_session_alias=op["sender_alias"],
        target_device_id=f"t1v2-d{scenario['second_device_index']}" if scenario["group"] in {"A3","S8"} else None,
        target_session_alias="second" if scenario["group"] in {"A3","S8"} else None,
        source=dict(dataset_sha256=None,record_id=None,record_sha256=None,split=None,packet_id=None,sequence_number=None,window_id=None),
        submitted=dict(packet_id=None,byte_length=None,sequence_number=None),mutation=mutation_record(),expected=op["expected"],
        execution_status="not_submitted",observed=empty_observed(),event_id=None,audit_event_ids=[],state_before=None,state_after=None,
        calls_delta=None,callback_entry_delta=None,consumed_event_delta=None,
        latency_ns=dict(verifier_native=None,receiver_path=None,sender_prepare=None,sender_hmac=None),trace_id=None,
        clock_mode=scenario["clock_mode"] if op["action"] in {"attack","expire"} else "real",clock_offset_ns=None,
        recovery=dict(required_step_ids=op["recovery_step_ids"],attempted_step_ids=[],complete=False),violations=[],error=None,notes=[])


class Scenario:
    def __init__(self,materials,scenario,callbacks,source_for):
        from puf_snn.auth.config import AuthConfig
        from puf_snn.auth.credential_verifier import CredentialAdmissionService, CredentialVerifierStore
        from puf_snn.auth.session import RegistryEntry
        from puf_snn.auth.verifier import Verifier
        from puf_snn.pipeline_v2 import V2InferencePipeline
        self.materials,self.scenario,self.source_for=materials,scenario,source_for
        self.config=AuthConfig.load(ROOT/FROZEN_CONFIG["auth_config"])
        self.service=CredentialAdmissionService(CredentialVerifierStore(materials.records),materials.provider)
        g=scenario["enrollment_generation"]
        entries=[RegistryEntry(f"t1v2-d{d}",materials.enrollments[d,g][0],materials.enrollments[d,g][2]) for d in range(6)]
        self.verifier=Verifier(entries,self.config.session_config(),admission_service=self.service)
        self.senders={}; self.aliases={}; self.ledger={}; self.packets={}; self.sources={}; self.prepared=False
        self.make_sender("source")
        self.pipeline=V2InferencePipeline(self.senders["source"],self.verifier,*callbacks)
        self.audit_seen=set()
        self.handshake_traffic=[]

    def make_sender(self,alias):
        from puf_snn.auth.sender import Sender
        from puf_snn.auth.session import provision_device
        d=self.scenario["second_device_index"] if alias=="second" else self.scenario["device_index"]
        g=self.scenario["enrollment_generation"]
        eid,helper,_=self.materials.enrollments[d,g]
        sender=Sender(provision_device(f"t1v2-d{d}",eid,helper),self.config.session_config().limits,admission_service=self.service)
        self.senders[alias]=sender
        return sender

    def bind(self,alias,sid=None):
        sender=self.senders[alias]
        self.aliases[alias]=(sid or sender.session_id,sender.enrollment.device_id,self.scenario["enrollment_generation"])

    def read(self,alias):
        d=self.scenario["second_device_index"] if alias=="second" else self.scenario["device_index"]
        identity=self.scenario["seed_ids"]["controlled_read"].rsplit(":",1)[0]+":"+alias
        return self.materials.read(d,identity)

    def establish(self,alias,opid):
        if alias not in self.senders: self.make_sender(alias)
        sender=self.senders[alias]
        if alias=="source":
            outcome=self.pipeline.establish(lambda:self.read(alias),opid)
            if outcome.decision!="accept": raise RuntimeError("controlled_admission_failure")
        else: additional_handshake(sender,self.verifier,lambda:self.read(alias),opid)
        self.bind(alias)

    def seal(self,alias,sequence,index):
        from puf_snn.integration import processed_record_to_wire_window
        from puf_snn.auth.session import Failure
        key=(alias,sequence)
        if key in self.packets: return self.packets[key]
        scheduled=next((p for p in self.scenario["packet_plan"] if (p["sender_alias"],p["sequence_number"])==key),None)
        if scheduled is None: raise RuntimeError("unplanned_packet")
        index=scheduled["source_window_index"]
        sender=self.senders[alias]
        if sender.next_to_send!=sequence: raise RuntimeError("planned_sender_sequence_mismatch")
        d=self.scenario["second_device_index"] if alias=="second" else self.scenario["device_index"]
        source=self.source_for(d,index,self.scenario["phase"])
        packet=sender.seal_window(processed_record_to_wire_window(source))
        if isinstance(packet,Failure): raise RuntimeError("packet_preparation_failure")
        self.packets[key]=packet; self.sources[key]=source
        return packet

    def prepare_handshake(self,opid):
        from puf_snn.reconstruction import reconstruct
        from puf_snn.auth.session import Failure, REFUSAL, Transcript, unframe
        s=self.senders["source"]
        self.request=s.begin_attempt(reconstruct(self.read("source"),s.enrollment.helper_data),opid)
        if isinstance(self.request,Failure): raise RuntimeError("controlled_admission_failure")
        if self.scenario["group"] in {"P27","P28"}:
            challenge=self.verifier.begin_session(self.request,admission=s.admission)
            if challenge==REFUSAL: raise RuntimeError("controlled_admission_failure")
            reader=unframe(challenge); reader.expect(b"P3CH")
            self.bind("source",Transcript.parse(reader.lp()).session_id)
            self.confirmation=s.answer_challenge(challenge)
            if isinstance(self.confirmation,Failure): raise RuntimeError("controlled_admission_failure")

    def finish_handshake(self):
        from puf_snn.auth.session import Failure
        s=self.senders["source"]
        if self.scenario["group"] in {"P25","P26"}:
            self.confirmation=s.answer_challenge(self.verifier.begin_session(self.request,admission=s.admission))
            if isinstance(self.confirmation,Failure): raise RuntimeError("recovery_handshake_failure")
        if s.finish_session(self.verifier.confirm_session(self.confirmation)) is not s:
            raise RuntimeError("recovery_handshake_failure")
        self.bind("source")

    def prepare_attack(self):
        s=self.scenario; group=s["group"]; n=s["sequence_position"]
        if group in {"P25","P26","P27","P28"}: return
        if group not in {"A1","A2"}:
            gap=int(s["variant"][-1]) if group in {"S2","S6"} else 0
            for k in range(n,n+gap+1):
                self.seal("source",k,s["window_permutation"][(s["session_trial_index"]+k-n)%100])
            if group in {"A3","S8"}: self.seal("second",0,s["second_window_index"])
        self.prepared=True

    def attack_packet(self,action):
        s=self.scenario; group=s["group"]; n=s["sequence_position"]
        if group in {"P25","P26","P27","P28"}:
            original=self.request if group in {"P25","P26"} else self.confirmation
            changed,mutation=mutate_handshake(original,group,s["mutation"]["cut"])
            return original,changed,mutation,None
        sequence=n-1 if action=="duplicate" else n-2 if group=="S5" else n+int(s["variant"][-1]) if group in {"S2","S6"} else n
        original=self.packets["source",sequence]
        if group in {"A1","A2","S2","S5","S6"} or action=="duplicate":
            return original,original,mutation_record(group,None,"exact_replay"),sequence
        params=dict(s["mutation"])
        params["target_device"]=f"t1v2-d{s['second_device_index']}"
        params["target_sid"]=self.senders["second"].session_id.hex() if "second" in self.senders else None
        changed,mutation=mutate_public(original,group,s["variant"],**params)
        return original,changed,mutation,sequence

    def snapshot(self,entries):
        return snapshot_safe_state(self.pipeline,self.senders,self.aliases,entries,self.ledger)

    def emit_audits(self,writer):
        for boundary,packet in self.handshake_traffic: writer.traffic(packet,boundary)
        self.handshake_traffic.clear()
        for alias,endpoint in [("verifier",self.verifier),*self.senders.items()]:
            for native in endpoint.audit_records:
                if native["event_id"] not in self.audit_seen:
                    writer.audit(self.scenario["scenario_id"],alias,native)
                    self.audit_seen.add(native["event_id"])


def operation_violations(row):
    violations=[]
    o=row["observed"]; e=row["expected"]
    if row["execution_status"]!="completed": return violations
    for k in ("result","reason"):
        if o[k]!=e[k]: violations.append("unexpected_"+k)
    if row["injection_boundary"]=="pipeline.process_envelope":
        for k,ek in (("authentication","hmac"),("identity_authenticated","identity_authenticated"),("order","order")):
            if o[k]!=e[ek]: violations.append("unexpected_"+k)
        accepted=o["result"]=="accept"
        wanted=int(accepted)
        if row["calls_delta"]!={k:wanted for k in ("release","preprocessing","motion","anomaly")}:
            violations.append("call_delta")
        if row["callback_entry_delta"]!={k:wanted for k in ("preprocessing","motion","anomaly")}:
            violations.append("callback_entry_delta")
        if row["consumed_event_delta"]!=wanted: violations.append("consumed_event_delta")
        if o["accepted_window_present"]!=accepted or o["authenticated_bytes_present"]!=accepted: violations.append("accepted_authority")
        if accepted and o["result_authority_consistent"] is not True: violations.append("result_object_authority")
        if accepted and row["validation_label"] in {"FORMAL",REAL_LABEL} and o["model_output_identity_consistent"] is not True: violations.append("model_output_identity")
        if o["order"]=="gap":
            source=next(s for s in row["state_before"]["sessions"] if s["session_alias"]==row["source_session_alias"])
            start=source["expected_sequence"]; end=row["submitted"]["sequence_number"]-1
            if (o["missing_start"],o["missing_end"],o["missing_count"])!=(start,end,end-start+1): violations.append("missing_range")
        if not accepted and stable_state(row["state_before"])!=stable_state(row["state_after"]): violations.append("rejected_state_changed")
        if accepted:
            before={s["session_id_hex"]:s for s in row["state_before"]["sessions"]}
            changes=0
            for after in row["state_after"]["sessions"]:
                b=before[after["session_id_hex"]]
                if b["accepted_count"]!=after["accepted_count"]:
                    changes+=1
                    if (b["accepted_count"] is None or after["accepted_count"]!=b["accepted_count"]+1
                        or after["last_accepted"]!=row["submitted"]["sequence_number"]
                        or b["deadline_ns"]!=after["deadline_ns"]): violations.append("accepted_state_transition")
            if changes!=1: violations.append("accepted_session_count")
    elif row["role"]=="parser_negative":
        if stable_state(row["state_before"])!=stable_state(row["state_after"]): violations.append("handshake_rejection_state_changed")
        if any(row["calls_delta"].values()): violations.append("handshake_calls")
    return violations


def schema_validator(kind):
    from jsonschema import Draft202012Validator
    schema=strict_json((ROOT/f"schemas/tier1-v2-{kind}-v1.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def write_json(path,value):
    with Path(path).open("x",encoding="utf-8",newline="\n") as handle:
        handle.write(canonical(value)+"\n")


ATTEMPT_FILES=("attempts","controls","state_safety","parser_negative","setup","recovery","warmup")


def validate_nonformal_output(path):
    path=Path(path).resolve()
    if path==FORMAL_ROOT.resolve() or path.is_relative_to(FORMAL_ROOT.resolve()) or FORMAL_ID in path.parts:
        raise ValueError("nonformal output cannot target formal identity")
    if path.is_relative_to((ROOT/"results").resolve()):
        raise ValueError("nonformal output must be temporary, outside results")
    if path.exists(): raise ValueError("nonformal output already exists")


class EvidenceWriter:
    def __init__(self,path,config,plan,*,nonformal):
        self.path=Path(path).resolve(); self.nonformal=nonformal
        validate_config(config,formal=not nonformal,nonformal=nonformal)
        if nonformal: validate_nonformal_output(self.path)
        self.label=plan["validation_label"]
        if self.label not in ({LABEL,REAL_LABEL} if nonformal else {"FORMAL"}): raise ValueError("validation label mismatch")
        if not nonformal and self.path!=FORMAL_ROOT.resolve(): raise ValueError("formal output identity mismatch")
        self.path.mkdir(parents=True,exist_ok=False)
        (self.path/"INCOMPLETE").write_text(self.label+"\n",encoding="utf-8",newline="\n")
        (self.path/".gitattributes").write_text("* text eol=lf\n",encoding="utf-8",newline="\n")
        self.attempt_validator=schema_validator("attempt")
        from jsonschema import Draft202012Validator
        self.audit_schema=strict_json((ROOT/"schemas/auth-audit-v1.schema.json").read_text())
        self.audit_validator=Draft202012Validator(self.audit_schema)
        self.handles={}; self.packets=set(); self.failed=False
        try:
            for name in (*ATTEMPT_FILES,"traffic","audit","timing_traces"):
                self.handles[name]=(self.path/(name+".jsonl")).open("x",encoding="utf-8",newline="\n")
            schema_validator("trial-plan").validate(plan)
            write_json(self.path/"config.json",config); write_json(self.path/"trial-plan.json",plan)
            (self.path/"plan.md").write_bytes((ROOT/config["plan_path"]).read_bytes())
        except BaseException:
            self.close(); raise

    def append(self,name,row):
        if self.failed: raise RuntimeError("evidence_writer_stopped")
        try:
            self.handles[name].write(canonical(row)+"\n"); self.handles[name].flush()
        except BaseException:
            self.failed=True; raise

    def attempt(self,row):
        self.attempt_validator.validate(row)
        name="warmup" if row["phase"]=="warmup" else {
            "primary_attack":"attempts","legitimate_control":"controls","state_negative":"state_safety",
            "parser_negative":"parser_negative","recovery_window":"recovery","recovery_handshake":"recovery"}.get(row["role"],"setup")
        self.append(name,row)

    def traffic(self,packet,boundary):
        if type(packet) is not bytes or boundary not in {"pipeline.process_envelope","verifier.begin_session","verifier.confirm_session","endpoints"}:
            raise ValueError("only public wire traffic is exportable")
        pid=digest(packet)
        if pid not in self.packets:
            self.append("traffic",dict(validation_label=self.label,packet_id=pid,boundary=boundary,bytes_b64=base64.b64encode(packet).decode()))
            self.packets.add(pid)
        return pid

    def audit(self,scenario_id,endpoint,native):
        # Schema is an explicit recursive allowlist, including latency/provenance.
        clean={k:native[k] for k in self.audit_schema["properties"]}
        self.audit_validator.validate(clean)
        self.append("audit",dict(validation_label=self.label,scenario_id=scenario_id,endpoint=endpoint,record=clean))

    def trace(self,trial_id,trace):
        # No arguments, model returns, exception strings or arbitrary object data.
        fields=("path","elapsed_ns","thread_cpu_ns","gc_spanning_trace_end")
        clean={k:trace[k] for k in fields}
        clean["spans"]=[{k:s[k] for k in ("id","parent_id","stage","start_ns","wall_ns","thread_cpu_ns","wall_minus_thread_cpu_ns","exception")} for s in trace["spans"]]
        clean["gc_events"]=[{k:e[k] for k in ("generation","start_ns","end_ns","collected","uncollectable")} for e in trace["gc_events"]]
        self.append("timing_traces",dict(validation_label=self.label,trial_id=trial_id,trace=clean))

    def close(self):
        for handle in self.handles.values(): handle.close()


def execute_scenario(config,plan,s,materials,callbacks,source_for,writer,dataset_hash=None):
    from puf_snn.pipeline_timing import TimingCapture, instrument_pipeline
    from puf_snn.auth.session import REFUSAL
    capture=TimingCapture(); fixture=None; blocked=None
    try:
        fixture=Scenario(materials,s,callbacks,source_for)
    except Exception:
        blocked=s["operations"][0]["operation_id"]
    context=ExitStack(); expiry_context=ExitStack(); expiry_offset=None
    try:
        if fixture:
            context.enter_context(instrument_pipeline(capture))
            entries,observations=context.enter_context(observe_pipeline(fixture.pipeline,capture))
            from puf_snn.auth.verifier import Verifier
            for method in ("begin_session","confirm_session"):
                original_method=getattr(Verifier,method)
                def observe_handshake(owner,packet,*args,_method=method,_original=original_method,**kwargs):
                    # Only the explicit public byte argument/return; admission stays private.
                    if owner is fixture.verifier: fixture.handshake_traffic.append(("verifier."+_method,packet))
                    result=_original(owner,packet,*args,**kwargs)
                    if owner is fixture.verifier and type(result) is bytes: fixture.handshake_traffic.append(("endpoints",result))
                    return result
                context.enter_context(patch.object(Verifier,method,observe_handshake))
        for op in s["operations"]:
            row=attempt_row(config,plan,s,op); action=op["action"]
            if blocked:
                row["error"]=dict(category="dependency_failure",stage="setup" if fixture is None else "operation",dependency_trial_id=blocked)
                if fixture is None and op["operation_id"]==blocked:
                    row["execution_status"]="execution_failure"; row["error"]["category"]="fixture_failure"
                writer.attempt(row); continue
            offset=None; raw=None; original=None; sequence=None; mutation=mutation_record()
            observation_start=len(observations); audit_start={r["event_id"] for r in fixture.verifier.audit_records}
            capture.last_trace=None
            before_entries=dict(entries)
            clock=ExitStack()
            try:
                if action=="establish" and op["sender_alias"]=="replacement": expiry_context.close()
                if action in {"attack","duplicate"}:
                    if not fixture.prepared: fixture.prepare_attack()
                    original,raw,mutation,sequence=fixture.attack_packet(action)
                elif action in {"prefix","control","recovery"}:
                    raw=fixture.seal(op["sender_alias"],op["sequence_number"],op["source_window_index"])
                    original=raw; sequence=op["sequence_number"]
                if raw is not None:
                    row["source"]["packet_id"]=writer.traffic(original,op["boundary"])
                    row["source"]["sequence_number"]=sequence
                    packet_id=writer.traffic(raw,op["boundary"])
                    if op["boundary"]=="pipeline.process_envelope":
                        try:
                            from puf_snn.auth.binary_window import parse_envelope
                            parsed=parse_envelope(raw).window
                            row["submitted"]["sequence_number"]=parsed.sequence_number
                        except Exception: pass  # Representation negatives intentionally fail parsing.
                    source=fixture.sources.get((op["sender_alias"],sequence))
                    if source:
                        row["source"].update(dataset_sha256=dataset_hash,record_id=source["window_id"],record_sha256=digest(source),
                                              split=source["split"],window_id=source["window_id"])
                    row["mutation"]=mutation
                if row["clock_mode"]!="real":
                    if expiry_offset is None:
                        deadline=fixture.verifier.session_status(fixture.aliases["source"][0]).deadline_ns
                        expiry_offset=expiry_context.enter_context(expiry_clock(deadline,row["clock_mode"]))
                    row["clock_offset_ns"]=expiry_offset
                row["state_before"]=fixture.snapshot(entries)
                row["execution_status"]="execution_failure"
                if raw is not None:
                    row["submitted"].update(packet_id=packet_id,byte_length=len(raw))
                    if op["boundary"]=="pipeline.process_envelope": call=lambda:fixture.pipeline.process_envelope(raw)
                    elif op["boundary"]=="verifier.begin_session": call=lambda:fixture.verifier.begin_session(raw,admission=fixture.senders["source"].admission)
                    else: call=lambda:fixture.verifier.confirm_session(raw)
                    result=capture.measure("receiver_path",call)
                    if op["boundary"]=="pipeline.process_envelope" and result.decision=="accept" and plan["validation_label"] in {"FORMAL",REAL_LABEL}:
                        row["observed"]["model_output_identity_consistent"]=(type(result.inference.motion) is dict
                            and set(result.inference.motion)=={"snn_32_seed_7"} and type(result.inference.anomaly) is dict
                            and set(result.inference.anomaly)=={"anomaly_random_forest_seed6007"})
                    if op["boundary"]!="pipeline.process_envelope":
                        row["observed"].update(result="reject" if result==REFUSAL else "accept",
                                               reason=fixture.verifier.last_reason if result==REFUSAL else "accepted",stage="handshake_receiver")
                else:
                    if action=="establish": fixture.establish(op["sender_alias"],op["operation_id"])
                    elif action=="prepare_handshake": fixture.prepare_handshake(op["operation_id"])
                    elif action=="finish_handshake": fixture.finish_handshake()
                    elif action=="expire": fixture.verifier.expire_due_sessions()
                    elif action=="close": fixture.verifier.close_all_sessions()
                    else: raise RuntimeError("unknown_planned_action")
                    row["observed"].update(result="accept",reason="accepted",stage=action)
                row["execution_status"]="completed"
            except Exception:
                # Never log exception text/args/locals. Preserve raw acceptance below.
                row["execution_status"]="execution_failure"
                row["error"]=dict(category="execution_failure",stage="receiver" if raw is not None else "preparation_or_setup",dependency_trial_id=None)
                blocked=op["operation_id"]
            finally:
                try:
                    row["state_after"]=fixture.snapshot(entries)
                    if row["state_before"]:
                        row["calls_delta"]={k:row["state_after"]["calls"][k]-row["state_before"]["calls"][k] for k in entries}
                        row["callback_entry_delta"]={k:entries[k]-before_entries[k] for k in ("preprocessing","motion","anomaly")}
                        row["consumed_event_delta"]=row["state_after"]["consumed_event_count"]-row["state_before"]["consumed_event_count"]
                except Exception:
                    row["execution_status"]="execution_failure"; blocked=op["operation_id"]
                    row["error"]=dict(category="observation_failure",stage="snapshot",dependency_trial_id=None)
                finally: clock.close()
            native=[r for r in fixture.verifier.audit_records if r["event_id"] not in audit_start]
            row["audit_event_ids"]=[r["event_id"] for r in native]
            if len(observations)>observation_start:
                observed=observations[-1]; row["event_id"]=observed["event_id"]
                row["observed"].update({k:observed[k] for k in ("result","reason","authenticated_bytes_sha256","accepted_window_present","authenticated_bytes_present","result_authority_consistent")})
                row["observed"]["stage"]="window_verification"
                audit=next((r for r in native if r["event_id"]==observed["event_id"]),None)
                if audit:
                    row["observed"].update(authentication=audit["authentication_result"],identity_authenticated=audit["identity_authenticated"],order=audit["order_result"],
                                          **{k:audit[k] for k in ("missing_start","missing_end","missing_count")})
                row["latency_ns"]["verifier_native"]=observed["verifier_auth_ns"]
            if raw is not None and capture.last_trace is not None:
                row["latency_ns"]["receiver_path"]=capture.last_trace["elapsed_ns"]
                row["trace_id"]=op["operation_id"]; writer.trace(op["operation_id"],capture.last_trace)
            if fixture.verifier.incomplete or any(v.incomplete for v in fixture.senders.values()):
                row["execution_status"]="execution_failure"; blocked=op["operation_id"]
                row["error"]=dict(category="endpoint_incomplete",stage="operation",dependency_trial_id=None)
            row["violations"]=operation_violations(row)
            fixture.emit_audits(writer)
            writer.attempt(row)
    finally:
        expiry_context.close()
        context.close()
        # Ordinary close is scheduled and observed. Incomplete endpoints must stop.


def read_rows(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [strict_json(line) for line in handle if line.strip()]


def summarize(config,plan,rows,evidence_complete):
    from puf_snn.pipeline_timing import latency_statistics
    by_key=defaultdict(list); reasons=Counter(); coverage=Counter(); latency=defaultdict(list)
    for r in rows:
        key=(r["phase"],r["role"],r["attack_group"])
        by_key[(*key,None)].append(r); by_key[(*key,r["attack_variant"])].append(r)
        reasons[(*key,r["attack_variant"],r["expected"]["reason"],r["observed"]["reason"])]+=1
        if r["role"] in {"primary_attack","legitimate_control","state_negative","parser_negative"} and r["phase"]=="measured":
            for dim,value in (("device",r["device_index"]),("generation",r["enrollment_generation"]),("variant",r["attack_variant"]),
                              ("sequence",r["source"]["sequence_number"]),("source_window",r["source"]["record_id"]),
                              ("sample",r["mutation"]["sample_index"]),("component",r["mutation"]["component"]),("actual_bit",r["mutation"]["actual_bit"])):
                coverage[r["attack_group"],dim,str(value)]+=1
        for metric,value in r["latency_ns"].items():
            if value is not None: latency[(*key,r["attack_variant"],r["observed"]["result"],r["observed"]["reason"],r["clock_mode"],metric)].append(value)
    count_rows=[]
    for key,items in sorted(by_key.items(),key=lambda kv:canonical(kv[0])):
        phase,role,group,variant=key
        statuses=Counter(r["execution_status"] for r in items)
        outcomes=Counter(r["observed"]["result"] for r in items if r["execution_status"]=="completed")
        raw=Counter(r["observed"]["result"] for r in items if r["injection_boundary"]=="pipeline.process_envelope")
        a,b=outcomes["accept"],outcomes["reject"]
        estimate="attack_acceptance" if role=="primary_attack" else "valid_message_rejection" if role=="legitimate_control" else None
        submitted=sum(r["submitted"]["packet_id"] is not None or r["execution_status"]=="completed" for r in items)
        count_rows.append(dict(phase=phase,role=role,group=group,variant=variant,scheduled=len(items),submitted=submitted,
                               A=a,R=b,F=statuses["execution_failure"],U=statuses["not_submitted"],
                               submitted_failures=sum(r["execution_status"]=="execution_failure" and r["submitted"]["packet_id"] is not None for r in items),
                               authentication_accept=raw["accept"],authentication_reject=raw["reject"],estimand=estimate,
                               interval=clopper_pearson(a if role=="primary_attack" else b,a+b) if estimate else None))
    latencies=[]
    for key,values in sorted(latency.items(),key=lambda kv:canonical(kv[0])):
        stats=latency_statistics(values); stats["mean_ms"]=sum(values)/len(values)/1e6
        stats["p99_status"]="reported" if len(values)>=100 else "insufficient_n"
        if len(values)<100: stats["p99_ms"]=None
        latencies.append(dict(zip(("phase","role","group","variant","result","reason","clock_mode","metric"),key))|stats)
    lookup={r["trial_id"]:r for r in rows}; recovery=[]
    for r in rows:
        required=r["recovery"]["required_step_ids"]
        if not required: continue
        rr=[lookup[i] for i in required if i in lookup]
        recovery.append(dict(parent_trial_id=r["trial_id"],required=len(required),attempted=sum(x["execution_status"]!="not_submitted" for x in rr),
                             accepted=sum(x["execution_status"]=="completed" and x["observed"]["result"]=="accept" for x in rr),
                             rejected=sum(x["execution_status"]=="completed" and x["observed"]["result"]=="reject" for x in rr),
                             failed=sum(x["execution_status"]=="execution_failure" for x in rr),not_submitted=sum(x["execution_status"]=="not_submitted" for x in rr),
                             complete=len(rr)==len(required) and all(x["execution_status"]=="completed" for x in rr)))
    violations=[dict(trial_id=r["trial_id"],checks=operation_violations(r)) for r in rows if operation_violations(r)]
    return dict(schema_version="puf-snn-tier1-v2-summary-v1",experiment_id=config["experiment_id"],run_id=config["run_id"],validation_label=plan["validation_label"],
        execution_source_commit=config["execution_source_commit"],config_sha256=digest(config),trial_plan_sha256=plan["plan_sha256"],
        evidence_complete=evidence_complete,expected_behavior_observed=not violations and all(r["execution_status"]=="completed" for r in rows),
        counts=count_rows,reasons=[dict(zip(("phase","role","group","variant","expected","observed"),k),count=v) for k,v in sorted(reasons.items(),key=lambda kv:canonical(kv[0]))],
        coverage=[dict(group=k[0],dimension=k[1],value=k[2],count=v) for k,v in sorted(coverage.items())],latencies=latencies,violations=violations,recovery=recovery,
        limitations=["Finite dependent observations: six devices, twelve enrollments, reused windows and one model pair; binomial intervals assume independent equal-probability trials.",
                     "Controlled reference-condition admission is not noisy reconstruction FRR.","Expiry uses a scoped simulated receiver clock, not five minutes of elapsed time."]+([LABEL+"; synthetic inputs and dummy callbacks; no statistical security conclusion."] if plan["validation_label"]==LABEL else
                     [REAL_LABEL+"; compact schedule with real frozen synthetic inputs/models; feasibility only, no attack-performance or statistical security conclusion."] if plan["validation_label"]==REAL_LABEL else []))


def source_files(root=ROOT):
    fixed=["docs/week6-tier1-v2-experiment-plan.md","docs/authentication-v2-protocol-spec.md","pyproject.toml","requirements.txt"]
    return sorted(set(fixed+[p.relative_to(root).as_posix() for directory in ("src/python","tests","configs","schemas")
                              for p in (root/directory).rglob("*") if p.is_file() and p.suffix in {".py",".json"}]))


def git(root,*args):
    return subprocess.run(["git","-c",f"safe.directory={root.resolve().as_posix()}",*args],cwd=root,
                          check=True,capture_output=True,text=True).stdout.strip()


def safe_path(root,relative):
    p=Path(relative)
    result=(root/p).resolve()
    if p.is_absolute() or ".." in p.parts or not result.is_relative_to(root.resolve()) or result==root.resolve():
        raise ValueError("path must remain in scoped root")
    return result


def verify_pins(root,files):
    if type(files) is not dict or not files: return False
    for relative,sha in files.items():
        if type(sha) is not str or len(sha)!=64: return False
        path=safe_path(root,relative)
        if not path.is_file() or file_hash(path)!=sha: return False
    return True


def artifact_inventory(root=ROOT):
    """Hash preflight only, before deserializing ANY model."""
    frozen=strict_json((root/FROZEN_CONFIG["frozen_config"]).read_text())
    files={frozen["input_path"]:frozen["input_sha256"]}
    for role,setting in frozen["bundles"].items():
        directory=setting["directory"]
        manifest_path=safe_path(root,directory+"/manifest.json")
        if file_hash(manifest_path)!=setting["manifest_sha256"]: raise ValueError("artifact manifest hash mismatch")
        files[directory+"/manifest.json"]=setting["manifest_sha256"]
        manifest=strict_json(manifest_path.read_text())
        if manifest["input_sha256"]!=frozen["input_sha256"]: raise ValueError("artifact dataset mismatch")
        complete=safe_path(root,directory+"/COMPLETE")
        if not complete.is_file(): raise ValueError("missing historical COMPLETE")
        files[directory+"/COMPLETE"]=file_hash(complete)
        for path,sha in manifest["artifacts"].items(): files[directory+"/"+path]=sha
        for path,item in manifest.get("local_model_artifacts",{}).items(): files[directory+"/"+path]=item["sha256"]
    return files


def formal_preflight(config,output,*,dummy_callbacks=False,root=ROOT):
    validate_config(config,formal=True)
    if dummy_callbacks: raise ValueError("dummy callbacks prohibited in formal mode")
    if Path(output).resolve()!=(root/config["output_root"]/config["run_id"]).resolve(): raise ValueError("formal output mismatch")
    if Path(output).exists(): raise ValueError("formal output already exists")
    if git(root,"rev-parse","HEAD")!=config["execution_source_commit"] or git(root,"status","--porcelain"):
        raise ValueError("execution provenance requires clean pinned source")
    # Changes in protocol behavior require re-audit; instrumentation-only lazy
    # imports in pipeline_timing are intentionally pinned in the new source tree.
    protocol_paths=["src/python/puf_snn/auth","src/python/puf_snn/reconstruction","src/python/puf_snn/puf",
                    "src/python/puf_snn/integration.py","src/python/puf_snn/pipeline_v2.py","configs/puf_baseline.json"]
    if git(root,"diff",config["design_baseline_commit"],"--",*protocol_paths): raise ValueError("protocol baseline changed; re-audit required")
    for name in ("auth","frozen"):
        if file_hash(root/config[name+"_config"])!=config[name+"_config_sha256"]: raise ValueError("config hash mismatch")
    manifest_path=Path(config["source_manifest_path"])
    if not manifest_path.is_absolute(): manifest_path=safe_path(root,config["source_manifest_path"])
    manifest=strict_json(manifest_path.read_text(encoding="utf-8"))
    if set(manifest)!={"execution_source_commit","files"} or manifest["execution_source_commit"]!=config["execution_source_commit"]:
        raise ValueError("source manifest identity")
    if set(manifest["files"])!=set(source_files(root)) or not verify_pins(root,manifest["files"]):
        raise ValueError("missing/mismatched source pins")
    artifacts=artifact_inventory(root)
    if not verify_pins(root,artifacts): raise ValueError("missing exact frozen artifacts; restore archives, never regenerate")
    plan=compile_trial_plan(config)
    schema_validator("trial-plan").validate(plan)
    return manifest,dict(files=artifacts),plan


def compact_nonformal_plan(config):
    full=compile_trial_plan(config,nonformal=True)
    seen=set(); chosen=[]
    for s in full["scenarios"]:
        key=(s["phase"],s["group"],s["variant"],s["clock_mode"])
        if key not in seen:
            seen.add(key); chosen.append(s)
    full["scenarios"]=chosen
    index=0
    for s in chosen:
        for op in s["operations"]: op["execution_index"]=index; index+=1
    counts=Counter(op["role"] for s in chosen if s["phase"]=="measured" for op in s["operations"])
    full["counts"]=[dict(role=k,count=v) for k,v in sorted(counts.items())]
    del full["plan_sha256"]; full["plan_sha256"]=digest(full)
    return full


def reconcile(path,config,plan,source_manifest,artifact_manifest):
    """Recompute from disk; behavior findings do not invalidate full evidence."""
    path=Path(path); rows=[]; checks=[]
    def check(name,okay,details=None): checks.append(dict(name=name,passed=bool(okay),details=details))
    check("persisted_config_and_plan",strict_json((path/"config.json").read_text(encoding="utf-8"))==config
          and strict_json((path/"trial-plan.json").read_text(encoding="utf-8"))==plan)
    check("persisted_source_and_artifact_manifests",strict_json((path/"source_manifest.json").read_text(encoding="utf-8"))==source_manifest
          and strict_json((path/"artifact_manifest.json").read_text(encoding="utf-8"))==artifact_manifest)
    check("trial_plan_schema",schema_validator("trial-plan").is_valid(plan))
    validator=schema_validator("attempt")
    valid=True; routing=True
    for name in ATTEMPT_FILES:
        for row in read_rows(path/(name+".jsonl")):
            if not validator.is_valid(row): valid=False
            wanted="warmup" if row["phase"]=="warmup" else {
                "primary_attack":"attempts","legitimate_control":"controls","state_negative":"state_safety",
                "parser_negative":"parser_negative","recovery_window":"recovery","recovery_handshake":"recovery"}.get(row["role"],"setup")
            if name!=wanted: routing=False
            rows.append(row)
    check("attempt_schemas",valid)
    check("population_file_routing",routing)
    check("evidence_identities",all(r["run_id"]==config["run_id"] and r["config_sha256"]==digest(config)
          and r["trial_plan_sha256"]==plan["plan_sha256"] and r["validation_label"]==plan["validation_label"] for r in rows))
    rows.sort(key=lambda r:r["execution_index"])
    planned=[(s,op) for s in plan["scenarios"] for op in s["operations"]]
    check("unique_ordered_operation_ids",[r["trial_id"] for r in rows]==[op["operation_id"] for s,op in planned])
    check("exact_plan_assignments",len(rows)==len(planned) and all(
        r["execution_index"]==op["execution_index"] and r["scenario_id"]==s["scenario_id"] and r["role"]==op["role"]
        and r["expected"]==op["expected"] and r["attack_variant"]==s["variant"] and r["attack_group"]==s["group"]
        and r["device_index"]==s["device_index"] and r["enrollment_generation"]==s["enrollment_generation"]
        and r["parent_attack_trial_id"]==op["parent_attack_trial_id"] and r["recovery"]["required_step_ids"]==op["recovery_step_ids"]
        for r,(s,op) in zip(rows,planned)))
    planned_counts=Counter(op["role"] for s,op in planned if s["phase"]=="measured")
    actual_counts=Counter(r["role"] for r in rows if r["phase"]=="measured")
    check("exact_population_counts",actual_counts==planned_counts)
    if plan["validation_label"]=="FORMAL":
        check("formal_plan_regeneration",compile_trial_plan(config)==plan)
    check("no_execution_failures_or_unsubmitted",all(r["execution_status"]=="completed" for r in rows))
    check("all_state_observations",all(r["state_before"] is not None and r["state_after"] is not None and r["calls_delta"] is not None for r in rows))
    audit_rows=read_rows(path/"audit.jsonl"); audits={r["record"]["event_id"]:r for r in audit_rows}
    check("unique_audit_ids",len(audits)==len(audit_rows))
    from jsonschema import Draft202012Validator
    av=Draft202012Validator(strict_json((ROOT/"schemas/auth-audit-v1.schema.json").read_text()))
    check("audit_schemas",all(av.is_valid(r["record"]) for r in audit_rows))
    windows=[r for r in rows if r["injection_boundary"]=="pipeline.process_envelope" and r["submitted"]["packet_id"] is not None]
    join_ok=True
    for r in windows:
        joined=[audits[i]["record"] for i in r["audit_event_ids"] if i in audits and audits[i]["record"]["event_type"]=="window"]
        if len(joined)!=1: join_ok=False; continue
        a=joined[0]; o=r["observed"]
        if (a["event_id"]!=r["event_id"] or a["decision"]!=o["result"] or a["reason"]!=o["reason"]
            or a["authentication_result"]!=o["authentication"] or a["identity_authenticated"]!=o["identity_authenticated"]
            or a["order_result"]!=o["order"] or a["latency_ns"]["verifier_auth"]!=r["latency_ns"]["verifier_native"]): join_ok=False
    check("one_native_decision_per_submitted_window",join_ok and len(windows)==sum(r["record"]["event_type"]=="window" for r in audit_rows))
    traces=read_rows(path/"timing_traces.jsonl"); trace_ids=[t["trial_id"] for t in traces]
    submitted=[r for r in rows if r["submitted"]["packet_id"] is not None]
    check("timing_coverage",len(trace_ids)==len(set(trace_ids)) and set(trace_ids)=={r["trial_id"] for r in submitted}
          and all(r["latency_ns"]["receiver_path"] is not None for r in submitted))
    traffic_rows=read_rows(path/"traffic.jsonl"); traffic={r["packet_id"]:base64.b64decode(r["bytes_b64"],validate=True) for r in traffic_rows}
    check("traffic_dedup_hashes",len(traffic_rows)==len(traffic) and all(digest(raw)==pid for pid,raw in traffic.items()))
    check("traffic_references",all(r["submitted"]["packet_id"] in traffic and r["source"]["packet_id"] in traffic for r in submitted))
    source_assignment=True
    by_id={r["trial_id"]:r for r in rows}
    for s,op in planned:
        r=by_id.get(op["operation_id"])
        if not r or r["source"]["packet_id"] is None or op["boundary"]!="pipeline.process_envelope": continue
        raw=traffic.get(r["source"]["packet_id"])
        if raw is None: source_assignment=False; continue
        from puf_snn.auth.binary_window import parse_envelope
        try:
            parsed=parse_envelope(raw).window
            if parsed.window_id!=r["source"]["window_id"] or parsed.sequence_number!=r["source"]["sequence_number"]: source_assignment=False
        except Exception: source_assignment=False
    check("source_packet_identity",source_assignment)
    replay_ok=tag_ok=True
    for r in submitted:
        original=traffic.get(r["source"]["packet_id"]); raw=traffic.get(r["submitted"]["packet_id"])
        if r["mutation"]["operation"]=="exact_replay" and original!=raw: replay_ok=False
        if r["attack_group"] in {"A3","A4","A5","S1","S8"} and r["role"] in {"primary_attack","state_negative"}:
            if strict_json(original)["authentication"]["tag_hex"]!=strict_json(raw)["authentication"]["tag_hex"]: tag_ok=False
        if r["attack_group"]=="S6" and r["role"]=="state_negative":
            linked=[x for x in rows if x["parent_attack_trial_id"]==r["trial_id"] and x["role"]=="recovery_window"]
            if not linked or linked[-1]["submitted"]["packet_id"]!=r["submitted"]["packet_id"]: replay_ok=False
    check("exact_replays_and_S6_retry",replay_ok); check("stale_tags_retained",tag_ok)
    recovery_ok=True
    for r in rows:
        parent=r["parent_attack_trial_id"]
        if parent is not None:
            if parent not in by_id or r["trial_id"] not in by_id[parent]["recovery"]["required_step_ids"] or r["scenario_id"]!=by_id[parent]["scenario_id"]: recovery_ok=False
        if any(step not in by_id for step in r["recovery"]["required_step_ids"]): recovery_ok=False
    check("recovery_links",recovery_ok)
    check("no_incomplete_endpoint",all(not r["state_after"]["verifier_incomplete"] and not any(x["value"] for x in r["state_after"]["sender_incomplete"]) for r in rows if r["state_after"]))
    check("source_pins_unchanged",verify_pins(ROOT,source_manifest["files"]))
    check("artifact_pins_unchanged",verify_pins(ROOT,artifact_manifest["files"]) if artifact_manifest["files"] else plan["validation_label"]==LABEL)
    check("plan_digest",digest({k:v for k,v in plan.items() if k!="plan_sha256"})==plan["plan_sha256"])
    complete=all(c["passed"] for c in checks)
    summary=summarize(config,plan,rows,complete)
    check("summary_schema",schema_validator("summary").is_valid(summary))
    check("A_R_F_U",all(c["A"]+c["R"]+c["F"]+c["U"]==c["scheduled"] for c in summary["counts"]))
    check("window_submission_arithmetic",all(c["submitted"]==c["A"]+c["R"]+c["submitted_failures"] for c in summary["counts"]
          if c["role"] in {"primary_attack","legitimate_control","state_negative","parser_negative","setup_window","recovery_window"}))
    summary["evidence_complete"]=all(c["passed"] for c in checks)
    return dict(schema_version="tier1-v2-reconciliation-v1",validation_label=plan["validation_label"],checks=checks,
                evidence_complete=summary["evidence_complete"],expected_behavior_observed=summary["expected_behavior_observed"],
                behavior_checks=[dict(name="reason_state_authority_counter_expectations",passed=not summary["violations"],
                                      discrepancies=summary["violations"])]),summary


def csv_rows(path,rows):
    if not rows:
        with Path(path).open("x",encoding="utf-8",newline="") as handle: handle.write("validation_label\n")
        return
    with Path(path).open("x",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]),lineterminator="\n"); writer.writeheader()
        for row in rows: writer.writerow({k:canonical(v) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def finalize(writer,config,plan,source_manifest,artifact_manifest):
    writer.close()
    reconciliation,summary=reconcile(writer.path,config,plan,source_manifest,artifact_manifest)
    write_json(writer.path/"summary.json",summary)
    tables={"attack_summary":[r for r in summary["counts"] if r["role"]=="primary_attack"],
            "control_summary":[r for r in summary["counts"] if r["role"]=="legitimate_control"],
            "reason_summary":summary["reasons"],"latency_summary":summary["latencies"],"recovery_summary":summary["recovery"]}
    for name,rows in tables.items(): csv_rows(writer.path/(name+".csv"),[dict(validation_label=writer.label,**r) for r in rows])
    from io import StringIO
    csv_match=True
    for name,rows in tables.items():
        buffer=StringIO(newline="")
        formatted=[dict(validation_label=writer.label,**r) for r in rows]
        if formatted:
            csv_writer=csv.DictWriter(buffer,fieldnames=list(formatted[0]),lineterminator="\n")
            csv_writer.writeheader()
            for r in formatted: csv_writer.writerow({k:canonical(v) if isinstance(v,(dict,list)) else v for k,v in r.items()})
        else: buffer.write("validation_label\n")
        csv_match &= (writer.path/(name+".csv")).read_bytes()==buffer.getvalue().encode("utf-8")
    # Independently regenerate from persisted raw files, then compare the saved summary.
    _,again=reconcile(writer.path,config,plan,source_manifest,artifact_manifest)
    same=again==strict_json((writer.path/"summary.json").read_text())
    reconciliation["checks"].append(dict(name="summary_reproducibility",passed=same,details=None))
    reconciliation["checks"].append(dict(name="csv_reproducibility",passed=csv_match,details=None))
    reconciliation["evidence_complete"] &= same and csv_match
    reconciliation["verified_file_hashes"]={p.name:file_hash(p) for p in sorted(writer.path.iterdir()) if p.is_file() and p.name!="INCOMPLETE"}
    write_json(writer.path/"reconciliation.json",reconciliation)
    files={p.name:file_hash(p) for p in sorted(writer.path.iterdir()) if p.is_file() and p.name not in {"INCOMPLETE","COMPLETE","manifest.json"}}
    write_json(writer.path/"manifest.json",dict(validation_label=writer.label,files=files))
    saved_manifest=strict_json((writer.path/"manifest.json").read_text(encoding="utf-8"))
    if saved_manifest!=dict(validation_label=writer.label,files=files) or not verify_pins(writer.path,saved_manifest["files"]):
        raise RuntimeError("output_manifest_mismatch")
    if reconciliation["evidence_complete"] and not writer.nonformal:
        write_json(writer.path/"COMPLETE",dict(run_id=config["run_id"],manifest_sha256=file_hash(writer.path/"manifest.json"),
            counts=summary["counts"],expected_behavior_observed=summary["expected_behavior_observed"]))
        (writer.path/"INCOMPLETE").unlink()
    # NONFORMAL never receives COMPLETE, regardless of observed outcomes.
    return reconciliation,summary


def machine_observation():
    """Allowlisted environment facts, outside all receiver timing spans."""
    from datetime import datetime, timezone
    from importlib.metadata import version, PackageNotFoundError
    import gc
    import os
    packages={}
    for package in ("numpy","scipy","galois","numba","scikit-learn","joblib","torch","jsonschema","threadpoolctl"):
        try: packages[package]=version(package)
        except PackageNotFoundError: packages[package]=None
    power=None
    if platform.system()=="Windows":
        try:
            power=subprocess.run(["powercfg","/getactivescheme"],capture_output=True,text=True,check=True,timeout=5).stdout.strip()[:512]
        except (OSError,subprocess.SubprocessError): pass
    timer=time.get_clock_info("perf_counter")
    return dict(utc=datetime.now(timezone.utc).isoformat(),python=platform.python_version(),platform=platform.platform(),
                cpu=platform.processor(),cpu_count=os.cpu_count(),packages=packages,gc_enabled=gc.isenabled(),
                timer=dict(implementation=timer.implementation,resolution=timer.resolution,monotonic=timer.monotonic),
                active_power_plan=power,background_load=None,background_load_status="not measured; no causal attribution")


def run_nonformal(output,*,callbacks=None,config=None,plan=None):
    config=nonformal_config() if config is None else config
    validate_config(config,nonformal=True)
    plan=compact_nonformal_plan(config) if plan is None else plan
    if plan["run_id"]!=config["run_id"] or plan["validation_label"]!=LABEL: raise ValueError("nonformal plan identity")
    callbacks=callbacks or (lambda record:(record,record),lambda value:None,lambda value:None)
    sources=dict(validation_label=LABEL,execution_source_commit=git(ROOT,"rev-parse","HEAD"),files={p:file_hash(ROOT/p) for p in source_files()})
    artifacts=dict(validation_label=LABEL,files={})
    writer=EvidenceWriter(output,config,plan,nonformal=True)
    started=machine_observation()
    try:
        write_json(writer.path/"source_manifest.json",sources); write_json(writer.path/"artifact_manifest.json",artifacts)
        metadata=dict(validation_label=LABEL,run_id=config["run_id"],formal=False,
            dummy_callbacks=True,python=platform.python_version(),platform=platform.platform(),source_commit=sources["execution_source_commit"],
            randomness="OS secrets unmodified; deterministic nonsecret planning/read streams",model_condition="NONFORMAL dummy callbacks",
            clock="real perf_counter_ns; scoped receiver expiry proxy",input_condition="synthetic in-memory public windows",start=started)
        materials=Materials()
        for s in plan["scenarios"]:
            execute_scenario(config,plan,s,materials,callbacks,lambda d,i,phase:nonformal_record(i,d,"validation" if phase=="warmup" else "test"),writer)
        metadata["end"]=machine_observation(); write_json(writer.path/"metadata.json",metadata)
        return finalize(writer,config,plan,sources,artifacts)
    finally: writer.close()


def run_real_nonformal(output):
    """One compact real-artifact feasibility pass; never calls formal execution.

    All frozen hashes are checked before the unchanged loader deserializes any
    model. Public input/model sanity facts and setup costs are measured outside
    receiver timing. Unexpected scenario outcomes are retained without retries.
    """
    began=time.perf_counter()
    validate_nonformal_output(output)
    config=nonformal_config("nonformal-real-artifact-feasibility")
    for name in ("auth","frozen"):
        if file_hash(ROOT/config[name+"_config"])!=config[name+"_config_sha256"]:
            raise ValueError("config hash mismatch")
    files=artifact_inventory()
    if not verify_pins(ROOT,files):
        raise ValueError("missing exact frozen artifacts; restore archives, never regenerate")
    from puf_snn.frozen_pipeline import load_frozen_bundle
    from puf_snn.pipeline_timing import one_model_bundle, CONDITIONS, select_timing_sources
    from puf_snn.attacks.evaluation import prepare_model_inputs
    from puf_snn.snn.dataset import load_records
    from puf_snn.integration import processed_record_to_wire_window
    from puf_snn.auth.binary_window import encode_window
    from threadpoolctl import threadpool_limits
    import gc
    frozen=strict_json((ROOT/config["frozen_config"]).read_text())
    load_start=time.perf_counter()
    bundle=load_frozen_bundle(ROOT,frozen)
    load_seconds=time.perf_counter()-load_start
    condition=next(dict(name=n,motion=m,anomaly=a) for n,m,a in CONDITIONS if n==config["model_condition"])
    selected=one_model_bundle(bundle,condition)
    test,warm=select_timing_sources(load_records(ROOT/frozen["input_path"]))
    devices=sorted({r["device_id"] for r in test})
    by_device={d:[r for r in test if r["device_id"]==device] for d,device in enumerate(devices)}
    def source_for(d,index,phase): return warm[index] if phase=="warmup" else by_device[d][index]
    plan=compact_nonformal_plan(config)
    plan["validation_label"]=REAL_LABEL
    del plan["plan_sha256"]; plan["plan_sha256"]=digest(plan)
    for source in test+warm: encode_window(processed_record_to_wire_window(source))
    sanity_start=time.perf_counter()
    with threadpool_limits(limits=1):
        sequence,features=prepare_model_inputs(warm[0])
        motion=selected.motion_predictions(sequence)
        anomaly=selected.anomaly_predictions(features)
    sanity=dict(motion_shape=list(sequence.shape),anomaly_shape=list(features.shape),
                motion_models=sorted(motion),anomaly_models=sorted(anomaly),
                finite_outputs_validated=True,seconds=time.perf_counter()-sanity_start)
    if (sanity["motion_shape"]!=[120,7] or sanity["anomaly_shape"]!=[48]
            or sanity["motion_models"]!=["snn_32_seed_7"]
            or sanity["anomaly_models"]!=["anomaly_random_forest_seed6007"]):
        raise ValueError("selected model sanity mismatch")
    sources=dict(validation_label=REAL_LABEL,execution_source_commit=None,
                 observed_repository_head=git(ROOT,"rev-parse","HEAD"),
                 files={p:file_hash(ROOT/p) for p in source_files()})
    artifacts=dict(validation_label=REAL_LABEL,files=files)
    started=machine_observation()
    gc.enable()
    provision_start=time.perf_counter(); materials=Materials()
    provision_seconds=time.perf_counter()-provision_start
    writer=EvidenceWriter(output,config,plan,nonformal=True)
    setup=[]
    try:
        write_json(writer.path/"source_manifest.json",sources)
        write_json(writer.path/"artifact_manifest.json",artifacts)
        run_start=time.perf_counter()
        with threadpool_limits(limits=1),ExitStack() as context:
            for name in ("establish","prepare_handshake","finish_handshake"):
                original=getattr(Scenario,name)
                def measured(owner,*args,_original=original,_name=name,**kwargs):
                    before=time.perf_counter_ns()
                    try: return _original(owner,*args,**kwargs)
                    finally: setup.append(dict(operation=_name,wall_ns=time.perf_counter_ns()-before))
                context.enter_context(patch.object(Scenario,name,measured))
            for scenario in plan["scenarios"]:
                execute_scenario(config,plan,scenario,materials,
                    (prepare_model_inputs,selected.motion_predictions,selected.anomaly_predictions),
                    source_for,writer,frozen["input_sha256"])
        metadata=dict(validation_label=REAL_LABEL,run_id=config["run_id"],formal=False,dummy_callbacks=False,
            model_condition=config["model_condition"],source_devices=devices,native_threads=1,torch_threads=1,
            gc_enabled=gc.isenabled(),start=started,end=machine_observation(),inference_sanity=sanity,
            bundle_load_seconds=load_seconds,provision_seconds=provision_seconds,
            scenario_execution_seconds=time.perf_counter()-run_start,
            pre_finalization_seconds=time.perf_counter()-began,setup_observations=setup,
            input_condition="verified frozen synthetic dataset; compact nonformal schedule",
            model_load_policy="complete hash gate; unchanged frozen loader; predeclared pair; CPU; eval; batch one",
            warmup_policy="one compact validation warmup; prior standalone sanity inference; not formal warmup policy",
            clock="real perf_counter_ns; scoped receiver expiry proxy",
            timing_limitation="setup wrappers include orchestration; receiver spans exclude evidence writes; no formal performance claim")
        write_json(writer.path/"metadata.json",metadata)
        return finalize(writer,config,plan,sources,artifacts)
    finally: writer.close()


def run_formal(config,output):
    """Explicit entry point only. Never called by validation/default CLI modes."""
    sources,artifacts,plan=formal_preflight(config,output)
    from puf_snn.frozen_pipeline import load_frozen_bundle
    from puf_snn.pipeline_timing import one_model_bundle, CONDITIONS, select_timing_sources
    from puf_snn.attacks.evaluation import prepare_model_inputs
    from puf_snn.snn.dataset import load_records
    from threadpoolctl import threadpool_limits
    import gc
    frozen=strict_json((ROOT/config["frozen_config"]).read_text())
    bundle=load_frozen_bundle(ROOT,frozen)
    condition=next(dict(name=n,motion=m,anomaly=a) for n,m,a in CONDITIONS if n==config["model_condition"])
    selected=one_model_bundle(bundle,condition)
    test,warm=select_timing_sources(load_records(ROOT/frozen["input_path"]))
    devices=sorted({r["device_id"] for r in test})
    by_device={d:[r for r in test if r["device_id"]==device] for d,device in enumerate(devices)}
    def source_for(d,index,phase): return warm[index] if phase=="warmup" else by_device[d][index]
    # Representation preflight before allocation, without authenticating windows.
    from puf_snn.integration import processed_record_to_wire_window
    from puf_snn.auth.binary_window import encode_window
    for source in test+warm: encode_window(processed_record_to_wire_window(source))
    gc.enable()
    materials=Materials()
    writer=EvidenceWriter(output,config,plan,nonformal=False)
    started=machine_observation()
    try:
        write_json(writer.path/"source_manifest.json",sources); write_json(writer.path/"artifact_manifest.json",artifacts)
        metadata=dict(validation_label="FORMAL",run_id=config["run_id"],formal=True,dummy_callbacks=False,
            python=platform.python_version(),platform=platform.platform(),model_condition=config["model_condition"],
            source_devices=devices,source_commit=config["execution_source_commit"],native_threads=1,torch_threads=1,gc_enabled=gc.isenabled(),
            clock="real perf_counter_ns; scoped receiver expiry proxy",start=started,
            model_load_policy="verify complete frozen bundle before deserialization; one pair; eval; CPU; batch one",
            warmup_policy="20 distinct validation sequence-zero scenarios; first-use labeled")
        with threadpool_limits(limits=1):
            for s in plan["scenarios"]:
                execute_scenario(config,plan,s,materials,(prepare_model_inputs,selected.motion_predictions,selected.anomaly_predictions),source_for,writer,frozen["input_sha256"])
        metadata["end"]=machine_observation(); write_json(writer.path/"metadata.json",metadata)
        return finalize(writer,config,plan,sources,artifacts)
    finally: writer.close()
