"""Preregistered reconstruction comparison. Formal mode requires validated preflight and exact frozen population.

No historical runner imports, cached timed responses, retries, session calls, or
implicit formal population overrides. Evaluator truth is separate from runtime material.
"""
import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import csv
import hashlib
import importlib.metadata
import inspect
import json
import os
from pathlib import Path
import platform
from random import Random
import subprocess
import sys
import time

import jsonschema
import numpy as np
from scipy.stats import beta

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/python'))
from puf_snn import reconstruction_alternatives as alt
from puf_snn.puf.device import create_device
from puf_snn.puf.ro_puf import generate_pairs, generate_response
from puf_snn.puf.variables import ReadConditions
from puf_snn.reconstruction import BCHCodec, DEFAULT_CONFIG, enroll, reconstruct
from puf_snn.auth.credential_verifier import (
    CredentialVerifierRecord, CredentialVerifierStore, CredentialAdmissionService,
    InMemoryCredentialVerifierKeyProvider,
)

CONFIG_PATH = ROOT / 'configs/reconstruction_alternatives_v1.json'
CONFIG_SHA256 = '3b7caa56bf296aaa02bca8fea69d545d6f1395c9811770c6e4d19ad8ea94c18b'
SCHEMA_PATH = ROOT / 'schemas/reconstruction-alternatives-attempt-v1.schema.json'
VERSION = 'week6-reconstruction-alternatives-v1'
GROUPS = ('B0', 'A1', 'A2', 'B1')
READS = dict(zip(GROUPS, (1, 3, 5, 1)))
NOISE = {'nominal': 0.1, 'stress': 0.25}
PAIRS = generate_pairs(128, 'adjacent')


def require(test, reason):
    if not test:
        raise ValueError(reason)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf8')


def object_digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_json(path, value):
    with Path(path).open('x', encoding='utf8', newline='\n') as f:
        f.write(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n')


def load_config(path=CONFIG_PATH):
    require(digest(path) == CONFIG_SHA256, 'Frozen configuration hash mismatch')
    config = json.loads(Path(path).read_text(encoding='utf8'))
    require(digest(ROOT / config['plan_path']) == config['plan_sha256'], 'Approved plan changed')
    return config


def rng(label):
    return Random(int.from_bytes(hashlib.sha256(label.encode('ascii')).digest(), 'big'))


def compile_plan(config, mode):
    require(config == load_config(), 'Unsupported configuration')
    require(mode in ('compile', 'smoke'), 'Formal execution is disabled in Stage 2')
    smoke = mode == 'smoke'
    scope = config['smoke'] if smoke else config
    prefix = scope['prefix'] if smoke else config['streams']['prefix']
    blocks = [(p, d, c, a) for p in scope['populations']
              for d in range(scope['devices_per_population'])
              for c in config['condition_order']
              for a in range(scope['attempts_per_cell_device'])]
    Random(config['schedule_seed']).shuffle(blocks)
    schedule = []
    for b, (p, d, c, a) in enumerate(blocks):
        shift = b % 4
        order = GROUPS[shift:] + GROUPS[:shift]
        for slot, group in enumerate(order):
            schedule.append(dict(block_id=b, trial_id=f'{prefix}:{b}:{group}', slot=slot,
                                 population_seed=p, device_index=d, condition=c, attempt=a,
                                 group=group, generation=0,
                                 read_labels=[f'{prefix}:read:{p}:{d}:0:{c}:{a}:{r}'
                                              for r in range(READS[group])]))
    plan = dict(version=VERSION, mode='NONFORMAL' if smoke else 'FORMAL_PLAN_ONLY',
                prefix=prefix, config_sha256=CONFIG_SHA256, plan_sha256=config['plan_sha256'],
                expected_attempts=len(schedule), expected_read_calls=sum(READS[t['group']] for t in schedule),
                expected_unique_readings=len(blocks)*5, schedule=schedule)
    plan['trial_plan_sha256'] = object_digest(plan)
    return plan


@dataclass(frozen=True, repr=False)
class RuntimeMaterial:
    device: object
    helper: object
    binding: dict
    service: CredentialAdmissionService


def provision(plan):
    """Trusted enrollment; return runtime state separately from synthetic truth."""
    prefix = plan['prefix']
    provider = InMemoryCredentialVerifierKeyProvider.generate(prefix + '-key')
    records, pending, truth = [], {}, {}
    for p, d in sorted({(t['population_seed'], t['device_index']) for t in plan['schedule']}):
        device_id = f'{prefix}-p{p}-d{d}'
        device = create_device(device_id, 128, 1.0, rng=rng(f'{prefix}:manufacture:{p}:{d}'))
        reference = generate_response(device, PAIRS, 100.0, ReadConditions(0.0, 0.0),
                                      rng=rng(f'{prefix}:reference:{p}:{d}:0'))
        for code, bits in (('baseline', 32), ('B1', 30)):
            credential = rng(f'{prefix}:credential{bits}:{p}:{d}:0').getrandbits(bits).to_bytes(4, 'big')
            enrollment_id = f'{device_id}-{code}-g0'
            reconstruction_id = alt.CONFIG.version if code == 'B1' else DEFAULT_CONFIG.version
            helper = (alt.enroll if code == 'B1' else enroll)(reference, credential,
                                                            enrollment_id=enrollment_id)
            binding = dict(device_id=device_id, enrollment_id=enrollment_id,
                           reconstruction_id=reconstruction_id)
            records.append(CredentialVerifierRecord.enroll(**binding, credential4=credential,
                           verifier_key_id=prefix+'-key', key_provider=provider))
            pending[p, d, code] = (device, helper, binding)
            truth[p, d, code] = dict(population_seed=p, device_index=d, code=code, generation=0,
                binding=binding, reference64=''.join(map(str, reference)),
                manufacturing_variation=list(device.manufacturing_variation),
                credential_hex=credential.hex(), helper_bits=''.join(map(str, helper.helper_bits)),
                synthetic_public_research_material=True)
    service = CredentialAdmissionService(CredentialVerifierStore(records), provider)
    runtime = {key: RuntimeMaterial(*value, service) for key, value in pending.items()}
    return runtime, truth


def measured_attempt(trial, material, record):
    """Runtime only: no reference, expected credential, or evaluator labels."""
    randoms = [rng(label) for label in trial['read_labels']]
    conditions = ReadConditions(0.0, NOISE[trial['condition']])
    decode = alt.reconstruct if trial['group'] == 'B1' else reconstruct
    readings, spans = [], []
    record.update(responses64=[], stages=[], execution_error=None)
    start = time.perf_counter_ns()
    record['started_perf_ns'] = start
    def stage(name, call):
        begin = time.perf_counter_ns()
        try:
            return call()
        finally:
            spans.append(dict(name=name, start_ns=begin-start,
                              end_ns=time.perf_counter_ns()-start))
    try:
        for source in randoms:
            reading = stage('read', lambda: generate_response(material.device, PAIRS, 100.0,
                                                             conditions, rng=source))
            readings.append(reading)
        effective = (stage('vote', lambda: alt.majority_vote(tuple(readings)))
                     if len(readings) > 1 else readings[0])
        result = stage('reconstruction', lambda: decode(effective, material.helper))
        invoked = result.outcome == 'candidate_valid_format'
        decision = (stage('verification', lambda: material.service.verify(
                    result.candidate_credential, **material.binding)).outcome if invoked else 'not_invoked')
        end = time.perf_counter_ns()
    except BaseException as error:
        end = time.perf_counter_ns()
        # Exception messages/traceback locals may contain runtime secrets. Type is safe.
        record['execution_error'] = type(error).__name__
        raise
    finally:
        record['total_ns'] = end-start
        record['stages'] = spans
        record['responses64'] = [''.join(map(str, r)) for r in readings]
        for name in ('read', 'vote', 'reconstruction', 'verification'):
            record[name+'_ns'] = sum(s['end_ns']-s['start_ns'] for s in spans if s['name']==name)
    record.update(effective_response64=''.join(map(str, effective)),
                  reconstruction_outcome=result.outcome, decoder_status=result.decoder_status,
                  reported_correction_count=result.reported_correction_count,
                  candidate_message=None if result.candidate_message is None else ''.join(map(str,result.candidate_message)),
                  candidate_credential_hex=None if result.candidate_credential is None else result.candidate_credential.hex(),
                  padding_valid=result.padding_valid, failure_reason=result.failure_reason,
                  verifier_invoked=invoked, verifier_outcome=decision,
                  vote_invoked=len(readings)>1, binding=material.binding)
    return record


def score(record, truth):
    """Evaluator runs only after measured verification has returned."""
    candidate = record['candidate_credential_hex']
    outcome = record['reconstruction_outcome']
    label = ('C' if candidate == truth['credential_hex'] else 'W') if outcome == 'candidate_valid_format' else (
        'D' if outcome == 'decoder_failure' else 'I')
    errors = [sum(a != b for a,b in zip(r[:63],truth['reference64'][:63])) for r in record['responses64']]
    effective = sum(a != b for a,b in zip(record['effective_response64'][:63],truth['reference64'][:63]))
    record.update(outcome=label, raw_errors=errors, effective_errors=effective,
                  raw_ber_numerator=sum(errors), raw_ber_denominator=63*len(errors),
                  raw_ber=sum(errors)/(63*len(errors)), first_read_errors=errors[0],
                  effective_ber=effective/63, selected_bit_count=63,
                  legitimate_admitted=label=='C' and record['verifier_outcome']=='verified')
    return record


def execution_mode(plan):
    return 'FORMAL' if plan['mode']=='FORMAL_PLAN_ONLY' else plan['mode']


def new_record(trial, plan, source_id):
    group = trial['group']
    return dict(trial, schema='reconstruction-alternatives-attempt-v1', version=VERSION,
                mode=execution_mode(plan), trial_plan_sha256=plan['trial_plan_sha256'],
                config_sha256=CONFIG_SHA256, plan_sha256=plan['plan_sha256'], source_id=source_id,
                read_count=READS[group], t=6 if group=='B1' else 5,
                credential_entropy_bits=30 if group=='B1' else 32,
                noise_std=NOISE[trial['condition']])

def proportion(x, n):
    return dict(count=x, denominator=n, rate=x/n if n else None,
                ci_method='two-sided-95%-Clopper-Pearson-binomial-descriptive',
                ci_low=(0.0 if x==0 else float(beta.ppf(.025,x,n-x+1))) if n else None,
                ci_high=(1.0 if x==n else float(beta.ppf(.975,x+1,n-x))) if n else None)


def latency(values):
    return dict(sample_count=len(values), p50_ns=float(np.quantile(values,.5)) if values else None,
                p95_ns=float(np.quantile(values,.95)) if values else None,
                p99_ns=float(np.quantile(values,.99)) if values else None,
                max_ns=max(values) if values else None)


def summarize(rows):
    require(rows and all(r.get('execution_error') is None for r in rows), 'Incomplete observations')
    n = len(rows)
    counts = Counter(r['outcome'] for r in rows)
    cross = Counter(r['outcome']+('A' if r['verifier_outcome']=='verified' else 'R')
                    for r in rows if r['verifier_invoked'])
    c,d,i,w = (counts[x] for x in 'CDIW')
    ca,cr,wa,wr = (cross[x] for x in ('CA','CR','WA','WR'))
    v = sum(r['verifier_invoked'] for r in rows)
    require(n==c+d+i+w and v==c+w==ca+cr+wa+wr and ca+cr==c and wa+wr==w,
            'Outcome denominator mismatch')
    result = dict(attempt_count=n, correct=c, decoder_failure=d, invalid_format=i,
                  wrong_credential=w, CA=ca, CR=cr, WA=wa, WR=wr,
                  verifier_calls=v, verifier_not_invoked=n-v, read_calls=sum(r['read_count'] for r in rows),
                  frr=proportion(d+i+w,n), correct_rate=proportion(c,n),
                  decoder_failure_rate=proportion(d,n), invalid_format_rate=proportion(i,n),
                  wrong_credential_rate=proportion(w,n), verifier_rejections=proportion(cr+wr,v),
                  verifier_rejections_all_attempts=proportion(cr+wr,n),
                  wrong_candidate_catch=proportion(wr,w), correct_candidate_verifier_frr=proportion(cr,c),
                  legitimate_admission_failure=proportion(n-ca,n),
                  operational_nonadmission=proportion(n-ca-wa,n), wrong_acceptance=proportion(wa,n),
                  verifier_outcomes=dict(Counter(r['verifier_outcome'] for r in rows)))
    raw_num = sum(r['raw_ber_numerator'] for r in rows)
    raw_den = sum(r['raw_ber_denominator'] for r in rows)
    for name,num,den in [('raw_ber',raw_num,raw_den),
                         ('first_read_ber',sum(r['first_read_errors'] for r in rows),63*n),
                         ('effective_ber',sum(r['effective_errors'] for r in rows),63*n)]:
        result[name] = dict(numerator=num,denominator=den,value=num/den)
    result['latency'] = {k:latency([r[k] for r in rows]) for k in
                         ('read_ns','vote_ns','reconstruction_ns','verification_ns','total_ns')}
    result['latency']['verification_conditional_ns'] = latency([r['verification_ns'] for r in rows if r['verifier_invoked']])
    return result


def group_rows(rows, keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    return groups


def summaries(rows, keys):
    return [dict(zip(keys,key), **summarize(value)) for key,value in sorted(group_rows(rows,keys).items())]


def paired(rows):
    blocks = group_rows(rows, ('condition','block_id'))
    output = []
    for condition in NOISE:
        for group in GROUPS[1:]:
            counts = Counter()
            for (c,_), block in blocks.items():
                if c!=condition:
                    continue
                indexed = {r['group']:r for r in block}
                require(set(indexed)==set(GROUPS), 'Incomplete paired block')
                counts[f"B0_{int(indexed['B0']['outcome']!='C')}_ALT_{int(indexed[group]['outcome']!='C')}"] += 1
            output.append(dict(condition=condition,group=group,paired_blocks=sum(counts.values()),
                               **{k:counts[k] for k in ('B0_0_ALT_0','B0_0_ALT_1','B0_1_ALT_0','B0_1_ALT_1')}))
    return output


def cluster_intervals(rows, config):
    """Whole populations kept paired across groups and conditions. No bit independence."""
    populations = sorted({r['population_seed'] for r in rows})
    if len(populations)<2:
        return dict(status='not_estimable_single_smoke_population',population_count=len(populations))
    stats = config['statistics']
    draws = Random(stats['bootstrap_seed'])
    sample_indices = np.array([[draws.randrange(len(populations)) for _ in populations]
                              for _ in range(stats['bootstrap_resamples'])])
    cells = group_rows(rows, ('condition','group','population_seed'))
    boot, output = {}, []
    for condition in NOISE:
        for group in GROUPS:
            values = []
            for p in populations:
                s = summarize(cells[condition,group,p])
                values.append([s['frr']['rate'],s['raw_ber']['value'],s['effective_ber']['value']])
            boot[condition,group] = np.asarray(values)[sample_indices].mean(axis=1)
            for j,metric in enumerate(('frr','raw_ber','effective_ber')):
                endpoints = np.quantile(boot[condition,group][:,j],[.025,.975]).tolist()
                output.append(dict(condition=condition,group=group,metric=metric,ci=endpoints))
        for group in GROUPS[1:]:
            for j,metric in enumerate(('frr','raw_ber','effective_ber')):
                endpoints = np.quantile((boot[condition,group]-boot[condition,'B0'])[:,j],[.025,.975]).tolist()
                output.append(dict(condition=condition,group=group,metric=metric+'-minus-B0',ci=endpoints))
    return dict(status='descriptive-cluster-bootstrap',population_count=len(populations),
                seed=stats['bootstrap_seed'],resamples=stats['bootstrap_resamples'],intervals=output)


def validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf8'))
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


def reconcile(rows, plan, truth):
    if execution_mode(plan)=='FORMAL':
        validate_formal_plan(plan)
    require(len(rows)==plan['expected_attempts'], 'Missing/dropped attempts')
    require(len({r['trial_id'] for r in rows})==len(rows), 'Duplicate attempts')
    check = validator()
    for row,trial in zip(rows,plan['schedule']):
        check.validate(row)
        require(all(row[k]==v for k,v in trial.items()), 'Trial order/identity mismatch')
        require(row['mode']==execution_mode(plan) and row['trial_plan_sha256']==plan['trial_plan_sha256']
                and row['plan_sha256']==plan['plan_sha256'] and row['config_sha256']==CONFIG_SHA256,
                'Provenance mismatch')
        m = READS[row['group']]
        require(row['read_count']==m and len(row['responses64'])==m, 'Read count mismatch')
        require(row['t']==(6 if row['group']=='B1' else 5)
                and row['credential_entropy_bits']==(30 if row['group']=='B1' else 32)
                and row['noise_std']==NOISE[row['condition']], 'Group parameters mismatch')
        key = (row['population_seed'],row['device_index'],'B1' if row['group']=='B1' else 'baseline')
        expected_truth = truth[key]
        require(row['binding']==expected_truth['binding'], 'Binding mismatch')
        # No decoder/verifier rerun during evidence audit.
        scored = score(dict(row),expected_truth)
        for k in ('outcome','raw_errors','effective_errors','raw_ber_numerator','raw_ber_denominator',
                  'raw_ber','first_read_errors','effective_ber','legitimate_admitted'):
            require(row[k]==scored[k], 'Scoring mismatch: '+k)
        read_vectors = tuple(tuple(map(int,r)) for r in row['responses64'])
        effective = alt.majority_vote(read_vectors) if m>1 else read_vectors[0]
        require(row['effective_response64']==''.join(map(str,effective)), 'Voting mismatch')
        candidate = row['candidate_credential_hex']
        require(row['verifier_invoked']==(row['outcome'] in 'CW'), 'Verifier invocation mismatch')
        if row['outcome']=='D':
            require(row['decoder_status']=='uncorrectable' and row['reported_correction_count']==-1
                    and candidate is None and row['candidate_message'] is None, 'Decoder failure leaked candidate')
        else:
            require(row['decoder_status']=='decoded' and 0<=row['reported_correction_count']<=row['t'], 'Decoder status mismatch')
            message = row['candidate_message']
            require(message is not None and len(message)==(30 if row['group']=='B1' else 36), 'Message shape mismatch')
            if row['group']=='B1':
                require(row['outcome']!='I' and row['padding_valid'] is None, 'B1 has no padding')
                expected_candidate = int(message,2).to_bytes(4,'big').hex()
            else:
                valid = message[-4:]=='0000'
                require(row['padding_valid']==valid and (row['outcome']=='I')==(not valid), 'Padding mismatch')
                expected_candidate = int(message[:32],2).to_bytes(4,'big').hex() if valid else None
            require(candidate==expected_candidate, 'Credential representation mismatch')
            word=independent_encode(message,0x37CD0EB67 if row['group']=='B1' else 0x86E8113)
            received=int(row['effective_response64'][:63],2)^int(expected_truth['helper_bits'],2)
            require((received^word).bit_count()==row['reported_correction_count'],'Saved correction count/codeword mismatch')
        if row['effective_errors']<=row['t']:
            require(row['outcome']=='C', 'Within-radius failure')
        expected_verifier = 'verified' if row['outcome']=='C' else ('credential_mismatch' if row['outcome']=='W' else 'not_invoked')
        require(row['verifier_outcome']==expected_verifier, 'Unexpected verifier outcome')
        spans = row['stages']
        expected_names = ['read']*m + (['vote'] if m>1 else []) + ['reconstruction'] + (['verification'] if row['verifier_invoked'] else [])
        require([s['name'] for s in spans]==expected_names, 'Timing stage mismatch')
        last = 0
        for s in spans:
            require(last<=s['start_ns']<=s['end_ns']<=row['total_ns'], 'Overlapping/invalid timing')
            last=s['end_ns']
        for name in ('read','vote','reconstruction','verification'):
            require(row[name+'_ns']==sum(s['end_ns']-s['start_ns'] for s in spans if s['name']==name), 'Stage sum mismatch')
        require(row['vote_invoked']==(m>1) and row['selected_bit_count']==63, 'Vote/selection status mismatch')
    for block in group_rows(rows,('block_id',)).values():
        indexed = {r['group']:r for r in block}
        require(set(indexed)==set(GROUPS), 'Missing paired group')
        for group in GROUPS:
            require(indexed[group]['responses64']==indexed['A2']['responses64'][:READS[group]], 'Unmatched read prefixes')
    require(sum(r['read_count'] for r in rows)==plan['expected_read_calls'], 'Total read count mismatch')
    require(len({label for r in rows for label in r['read_labels']})==plan['expected_unique_readings'], 'Unique read count mismatch')
    devices={(t['population_seed'],t['device_index']) for t in plan['schedule']}
    require(set(truth)=={(p,d,c) for p,d in devices for c in ('baseline','B1')}, 'Enrollment population mismatch')
    require(len({r['source_id'] for r in rows})==1, 'Mixed runtime sources')
    result = summarize(rows)
    return dict(status='PASS',mode=execution_mode(plan),attempt_count=len(rows),
                cell_counts={f'{c}:{g}':len(v) for (c,g),v in group_rows(rows,('condition','group')).items()},
                read_calls=result['read_calls'], unique_readings=len({x for r in rows for x in r['read_labels']}),
                enrollment_count=len(truth), verifier_calls=result['verifier_calls'],
                no_retries=True, schema_validated_rows=len(rows))

def source_hashes():
    # Explicit allowlist: deleting a dependency cannot silently shrink a glob.
    files = source_dependencies()
    result = {}
    for relative in files:
        path = ROOT / relative
        require(path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(ROOT.resolve()),
                'Missing or unsafe source dependency: '+relative)
        result[relative] = digest(path)
    return result


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()


def environment():
    return dict(created_utc=datetime.now(timezone.utc).isoformat(), branch=git('branch','--show-current'),
                head=git('rev-parse','HEAD'),git_status=git('status','--short'),
                index_status=git('diff','--cached','--name-status'), python=sys.version,
                executable=sys.executable,os=platform.platform(),cpu=platform.processor(),machine=platform.machine(),
                packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()},
                clock=vars(time.get_clock_info('perf_counter')),command=sys.argv,
                runtime_settings={k:os.environ.get(k) for k in ('NUMBA_DISABLE_JIT','NUMBA_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')},
                background_load='uncontrolled; no outlier trimming',power_policy='not changed; not measured',
                timing_scope='local simulator generation through verification; not hardware acquisition')


def warm_up(config):
    started=time.perf_counter_ns()
    BCHCodec().initialize()
    alt.ExperimentalBCHCodec().initialize()
    initialization=time.perf_counter_ns()-started
    plan=compile_plan(config,'smoke')
    prefix=config['warmup']['prefix']
    plan.update(prefix=prefix,mode='NONFORMAL')
    plan['schedule']=[]
    for a in range(20):
        for slot,group in enumerate(GROUPS):
            plan['schedule'].append(dict(block_id=a,trial_id=f'{prefix}:{a}:{group}',slot=slot,
                population_seed=2026100701,device_index=0,condition='nominal',attempt=a,group=group,generation=0,
                read_labels=[f'{prefix}:read:2026100701:0:0:nominal:{a}:{r}' for r in range(READS[group])]))
    runtime,truth=provision(plan)
    counts=Counter()
    for trial in plan['schedule']:
        key=(trial['population_seed'],0,'B1' if trial['group']=='B1' else 'baseline')
        row=score(measured_attempt(trial,runtime[key],{}),truth[key])
        counts[row['outcome']]+=1
    for codec in (BCHCodec(),alt.ExperimentalBCHCodec()):
        for cycle in range(20):
            word=codec.encode((0,)*codec.k)
            amount=(0,codec.t,codec.t+1)[cycle%3]
            received=tuple(bit ^ int(j<amount) for j,bit in enumerate(word))
            decoded=codec.decode(received)
            if amount<=codec.t:
                require(decoded.corrected_codeword==word,'Warmup boundary failed')
            else:
                require(decoded.status=='uncorrectable', 'Pinned beyond-radius warmup fixture changed')
    material=runtime[2026100701,0,'baseline']
    credential=bytes.fromhex(truth[2026100701,0,'baseline']['credential_hex'])
    wrong=bytes([credential[0]^1])+credential[1:]
    for _ in range(100):
        require(material.service.verify(credential,**material.binding).verified,'Warmup verifier pass failed')
        require(material.service.verify(wrong,**material.binding).outcome=='credential_mismatch','Warmup mismatch failed')
    return dict(mode='NONFORMAL_WARMUP',prefix=prefix,initialization_ns=initialization,
                total_warmup_ns=time.perf_counter_ns()-started,complete_attempts=80,
                complete_attempt_outcomes=dict(counts),codec_cycles_per_code=20,
                extra_verifier_passes=100,extra_verifier_mismatches=100,
                excluded_from_measured_denominators=True)


def write_csv(path, rows):
    require(bool(rows),'Empty CSV')
    with Path(path).open('x',encoding='utf8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,sort_keys=True,allow_nan=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})


def latency_rows(rows):
    timing=[]
    for (condition_id,group),cell in group_rows(rows,('condition','group')).items():
        strata={'all':cell}
        for outcome in 'CDIW':
            strata['outcome-'+outcome]=[r for r in cell if r['outcome']==outcome]
        for outcome in ('verified','credential_mismatch','not_invoked'):
            strata['verifier-'+outcome]=[r for r in cell if r['verifier_outcome']==outcome]
        for name,subset in strata.items():
            for stage in ('read_ns','vote_ns','reconstruction_ns','verification_ns','total_ns','verification_conditional_ns'):
                values=[r['verification_ns'] for r in subset if r['verifier_invoked']] if stage=='verification_conditional_ns' else [r[stage] for r in subset]
                timing.append(dict(condition=condition_id,group=group,stratum=name,stage=stage,**latency(values)))
    return timing


def save_summaries(directory,rows,config):
    condition=summaries(rows,('condition','group'))
    devices=summaries(rows,('condition','group','population_seed','device_index'))
    populations=summaries(rows,('condition','group','population_seed'))
    comparisons=paired(rows)
    timing=latency_rows(rows)
    for filename,data in [('condition_summary.csv',condition),('per_device_summary.csv',devices),
                           ('per_population_summary.csv',populations),('paired_comparisons.csv',comparisons),
                           ('latency_summary.csv',timing)]:
        write_csv(directory/filename,data)
    mode=rows[0]['mode']
    require(all(r['mode']==mode for r in rows),'Mixed summary modes')
    report=dict(mode=mode,version=VERSION,overall=summarize(rows),conditions=condition,
                paired_comparisons=comparisons,cluster_intervals=cluster_intervals(rows,config),
                worst_observed_device_by_cell=[dict(condition=c,group=g,device_index=max(v,key=lambda r:r['frr']['rate'])['device_index'],
                    population_seed=max(v,key=lambda r:r['frr']['rate'])['population_seed'],
                    frr=max(r['frr']['rate'] for r in v)) for (c,g),v in group_rows(devices,('condition','group')).items()],
                interpretation=('NONFORMAL smoke only; no research target conclusion or formal findings' if mode=='NONFORMAL'
                                else 'FORMAL evidence; completeness does not imply the FRR target was achieved'))
    write_json(directory/'summary.json',report)
    require(json.loads((directory/'summary.json').read_text())==report,'Summary readback mismatch')
    for filename,data in [('condition_summary.csv',condition),('per_device_summary.csv',devices),
                          ('per_population_summary.csv',populations),('paired_comparisons.csv',comparisons),
                          ('latency_summary.csv',timing)]:
        verify_csv(directory/filename,data)
    return report


def safe_output(path):
    path=Path(path).resolve()
    require(not path.is_relative_to((ROOT/'results').resolve()),'Nonformal output must be outside results/')
    require(path!=ROOT and not path.exists(),'Output must be a new exclusive directory')
    return path


def run_smoke(output, config=None):
    config=load_config() if config is None else config
    return _run_evaluation(output,config,compile_plan(config,'smoke'))


def run_formal(output):
    config=load_config()
    return _run_evaluation(output,config,compile_plan(config,'compile'))


def _run_evaluation(output,config,plan):
    """Shared loop; no alternate verifier callbacks or reduced formal-plan option."""
    formal=execution_mode(plan)=='FORMAL'
    mode=execution_mode(plan)
    if formal:
        preflight=formal_preflight(output)
        validate_formal_plan(plan)
        directory=formal_output(output)
        require(source_hashes()==preflight['source_sha256'],'Source changed after preflight')
    else:
        require(plan==compile_plan(config,'smoke'),'Smoke isolation failed')
        preflight=None
        directory=safe_output(output)
    # All formal preflight checks above occur before the first output mutation.
    directory.mkdir(parents=True,exist_ok=False)
    current=None
    completed=0
    started=time.perf_counter_ns()
    try:
        hashes=source_hashes()
        source_id=object_digest(hashes)
        if formal:
            require(hashes==preflight['source_sha256'],'Source changed before snapshot')
            write_json(directory/'preflight.json',preflight)
            create_source_snapshot(directory/'source_snapshot',hashes,preflight['prerequisites'])
            snapshot_sha256=verify_source_snapshot(directory/'source_snapshot',hashes)
        with (directory/'config.json').open('xb') as snapshot:
            snapshot.write(CONFIG_PATH.read_bytes())
        write_json(directory/'trial_plan.json',plan)
        metadata=environment()
        metadata.update(mode=mode,source_sha256=hashes,source_id=source_id,
                        config_sha256=CONFIG_SHA256,plan_sha256=plan['plan_sha256'],trial_plan_sha256=plan['trial_plan_sha256'])
        if formal:
            metadata['source_snapshot_manifest_sha256']=snapshot_sha256
        write_json(directory/'metadata.json',metadata)
        write_json(directory/'warm_up.json',warm_up(config))
        write_json(directory/'backend_runtime.json',dict(mode=mode,
            gf2_mode=alt.galois.GF2.ufunc_mode,extension_mode=alt._backend().extension_field.ufunc_mode,
            numba_threads=__import__('numba').get_num_threads()))
        runtime,truth=provision(plan)
        if formal:
            validate_enrollments(plan,list(truth.values()))
        write_json(directory/'enrollments.json',list(truth.values()))
        check=validator()
        if formal:
            assert_real_runtime(runtime)
            verify_source_snapshot(directory/'source_snapshot',hashes)
            require(source_hashes()==hashes,'Source changed immediately before measurement')
        loop_start=time.perf_counter_ns()
        with (directory/'attempts.jsonl').open('x',encoding='utf8',newline='\n') as stream:
            for trial in plan['schedule']:
                current=new_record(trial,plan,source_id)
                key=(trial['population_seed'],trial['device_index'],'B1' if trial['group']=='B1' else 'baseline')
                try:
                    measured_attempt(trial,runtime[key],current)
                    score(current,truth[key])
                except BaseException as error:
                    current.setdefault('execution_error',type(error).__name__)
                    if current['execution_error'] is None:
                        current['execution_error']=type(error).__name__
                    stream.write(canonical(current).decode()+'\n')
                    stream.flush()
                    raise
                stream.write(canonical(current).decode()+'\n')
                stream.flush()
                completed+=1
                check.validate(current)
        loop_ns=time.perf_counter_ns()-loop_start
        rows=[json.loads(line) for line in (directory/'attempts.jsonl').read_text(encoding='utf8').splitlines()]
        # Rebuild truth from safe synthetic disk evidence, not verifier private records.
        saved_truth={(r['population_seed'],r['device_index'],r['code']):r for r in json.loads((directory/'enrollments.json').read_text())}
        reconciliation=reconcile(rows,plan,saved_truth)
        require(all(r['source_id']==source_id for r in rows),'Source identity mismatch')
        report=save_summaries(directory,rows,config)
        require(source_hashes()==hashes,'Runtime source changed during evaluation')
        if formal:
            assert_real_runtime(runtime)
            verify_source_snapshot(directory/'source_snapshot',hashes)
        total_ns=time.perf_counter_ns()-started
        # Conservative illustrative scaling, not a formal-run measurement.
        projected=loop_ns/1e9*(48000/len(rows))
        runtime_report=dict(mode=mode,measured_attempt_loop_ns=loop_ns,
            total_process_work_ns=total_ns,projected_48000_loop_seconds=projected,
            cautious_projection_seconds=2*projected+total_ns/1e9,
            runtime_gate_seconds=config['runtime_gate_seconds'],
            practicality_gate_passed=2*projected+total_ns/1e9<=config['runtime_gate_seconds'],
            caveat=('80 smoke attempts; stress tail, cold JIT, background load and formal summary cost may differ'
                    if not formal else 'Actual formal loop timing; projection fields are descriptive only'))
        write_json(directory/'runtime.json',runtime_report)
        write_json(directory/'reconciliation.json',reconciliation)
        write_json(directory/'post_run.json',dict(mode=mode,ended_utc=datetime.now(timezone.utc).isoformat(),
                    git_status=git('status','--short'),index_status=git('diff','--cached','--name-status'),source_sha256=source_hashes()))
        if formal:
            # Full independent disk readback, then hashes and completion seal.
            seal_formal(directory,hashes)
        else:
            manifest={p.name:digest(p) for p in sorted(directory.iterdir()) if p.is_file()}
            write_json(directory/'manifest.json',manifest)
            require(all(digest(directory/name)==h for name,h in manifest.items()),'Artifact hash mismatch')
            write_json(directory/'NONFORMAL_VALIDATED.json',dict(mode='NONFORMAL',attempt_count=80,
                        manifest_sha256=digest(directory/'manifest.json'),trial_plan_sha256=plan['trial_plan_sha256']))
            require(not (directory/'COMPLETE').exists(),'Formal marker prohibited')
        return dict(reconciliation=reconciliation,runtime=runtime_report,summary=report)
    except BaseException as error:
        write_json(directory/'INCOMPLETE.json',dict(mode=mode,completed_attempts=completed,
                   current_trial_id=None if current is None else current['trial_id'],error_type=type(error).__name__,
                   interpretation='Retained partial evidence; no full-cohort FRR or completion claim'))
        raise


PLAN_SHA256='0206983264278f1485b36bdbff29463afe2dc153aa003954506e68e75b9ced2d'
FORMAL_SCHEDULE_SHA256='d22e5eebe6ec55c9f890e02b4f010833e4f32ff9d64b5c777b22e9f794a26f10'
FORMAL_RELATIVE=Path('results/week-6/will/reconstruction-alternatives/week6-reconstruction-alternatives-v1-formal-001')
SMOKE_DIRECTORY=ROOT/'tmp/week6-reconstruction-alternatives-smoke-001'
SMOKE_MANIFEST_SHA256='91b90a2de1df3aa8652dbaa1bb7a0a73527454014a915501b2f93497b7a6bc26'
VALIDATION_PATH=ROOT/'tmp/week6-alternatives-stage3a-validation.json'
REQUIRED_SUITES=('reconstruction','credential_auth','historical_reconstruction_accounting',
                 'historical_verifier_accounting','alternatives_accounting','formal_readiness')
REQUIRED_PACKAGES={'galois':'0.4.11','numpy':'2.5.3','numba':'0.67.0','llvmlite':'0.49.0',
                   'scipy':'1.18.1','jsonschema':'4.26.0'}


def source_dependencies():
    """Closed sanitized dependency set, including transitive auth package imports.

    No directory globs: absent files fail, rather than falling out of inventory.
    Third-party installation is identified by environment, never copied.
    """
    files=['src/python/scripts/run_reconstruction_alternatives.py',
           'src/python/puf_snn/reconstruction_alternatives.py','src/python/puf_snn/__init__.py',
           'configs/reconstruction_alternatives_v1.json',
           'schemas/reconstruction-alternatives-attempt-v1.schema.json',
           'docs/week6-reconstruction-alternatives-experiment-plan.md',
           'docs/week6-reconstruction-alternatives-implementation-validation.md',
           'docs/week6-reconstruction-alternatives-formal-readiness.md',
           'requirements.txt','pyproject.toml',
           'tests/reconstruction/test_reconstruction_alternatives.py',
           'tests/experiments/test_reconstruction_alternatives_experiment.py',
           'tests/experiments/test_reconstruction_alternatives_formal.py']
    for package,names in {
        'puf':('__init__','device','ro_puf','variables','metrics'),
        'reconstruction':('__init__','bch','credential'),
        'auth':('__init__','audit','binary_window','config','credential_verifier',
                'inference_gate','sender','session','verifier','window_message'),
    }.items():
        files.extend(f'src/python/puf_snn/{package}/{name}.py' for name in names)
    return tuple(sorted(files))


def validate_formal_plan(plan):
    unsigned={k:v for k,v in plan.items() if k!='trial_plan_sha256'}
    require(plan['trial_plan_sha256']==FORMAL_SCHEDULE_SHA256
            and object_digest(unsigned)==FORMAL_SCHEDULE_SHA256,'Formal schedule digest mismatch')
    require(plan==compile_plan(load_config(),'compile'),'Formal schedule differs from recompiled plan')
    require(plan['mode']=='FORMAL_PLAN_ONLY' and plan['prefix']=='w6ra-v1','Formal stream/mode mismatch')
    schedule=plan['schedule']
    require(len(schedule)==plan['expected_attempts']==48000,'Formal population count mismatch')
    require(plan['expected_read_calls']==120000 and plan['expected_unique_readings']==60000,'Formal reading counts mismatch')
    require(Counter((t['condition'],t['group']) for t in schedule)==Counter({(c,g):6000 for c in NOISE for g in GROUPS}), 'Formal cell count mismatch')
    require(Counter((t['group'],t['slot']) for t in schedule)==Counter({(g,s):3000 for g in GROUPS for s in range(4)}),'Execution slots unbalanced')
    devices={(t['population_seed'],t['device_index']) for t in schedule}
    require(devices=={(p,d) for p in range(2026100701,2026100721) for d in range(6)},'Formal device population mismatch')
    require(len({t['trial_id'] for t in schedule})==48000,'Duplicate formal trial')
    require(len({r for t in schedule for r in t['read_labels']})==60000,'Unique formal measurements mismatch')
    return dict(attempts=48000,attempts_per_cell=6000,devices=120,enrollments=240,
                read_calls=120000,unique_readings=60000,slots_per_group=3000,
                trial_plan_sha256=FORMAL_SCHEDULE_SHA256)


def formal_output(path):
    expected=ROOT/FORMAL_RELATIVE
    candidate=Path(os.path.abspath(path))
    require(candidate==expected,'Wrong formal output path')
    require(not candidate.exists(),'Formal output already exists')
    for parent in (candidate,*candidate.parents):
        require(not parent.is_symlink() and not (hasattr(parent,'is_junction') and parent.is_junction()),
                'Linked formal output path is unsupported')
    require(candidate.resolve()==expected,'Formal output resolves outside approved location')
    return candidate


def runtime_apis():
    return (generate_response,create_device,enroll,reconstruct,alt.enroll,alt.reconstruct,
            alt.majority_vote,CredentialAdmissionService.verify,CredentialVerifierRecord.enroll.__func__,
            InMemoryCredentialVerifierKeyProvider.generate.__func__,BCHCodec.encode,BCHCodec.decode,
            alt.ExperimentalBCHCodec.encode,alt.ExperimentalBCHCodec.decode)


def assert_real_runtime(materials=None):
    require(runtime_apis()==_REAL_RUNTIME_APIS,'Dummy or substituted runtime/verification callback')
    require(all(inspect.isfunction(f) for f in runtime_apis()),'Runtime function identity mismatch')
    if materials is not None:
        require(all(type(m.service) is CredentialAdmissionService
                    and getattr(m.service.verify,'__func__',None) is _REAL_RUNTIME_APIS[7]
                    for m in materials.values()),'Nonstandard verification service')


def verify_packages():
    actual={name:importlib.metadata.version(name) for name in REQUIRED_PACKAGES}
    require(actual==REQUIRED_PACKAGES,'Required package version mismatch')
    require(sys.version_info[:3]==(3,12,4),'Validated Python version mismatch')
    return actual


def verify_prior_validation():
    """Read-only validation of pinned Stage 2 smoke and fresh Stage 3A tests."""
    require(digest(SMOKE_DIRECTORY/'manifest.json')==SMOKE_MANIFEST_SHA256,'Prior smoke manifest mismatch')
    manifest=json.loads((SMOKE_DIRECTORY/'manifest.json').read_text())
    require(all('/' not in name and '\\' not in name and name not in ('.','..') for name in manifest),'Unsafe smoke manifest')
    require(all(digest(SMOKE_DIRECTORY/name)==h for name,h in manifest.items()),'Prior smoke artifact mismatch')
    marker=json.loads((SMOKE_DIRECTORY/'NONFORMAL_VALIDATED.json').read_text())
    require(marker['manifest_sha256']==SMOKE_MANIFEST_SHA256 and marker['mode']=='NONFORMAL'
            and marker['attempt_count']==80 and not (SMOKE_DIRECTORY/'INCOMPLETE.json').exists()
            and not (SMOKE_DIRECTORY/'COMPLETE').exists(),'Prior validation incomplete')
    saved_plan=json.loads((SMOKE_DIRECTORY/'trial_plan.json').read_text())
    require(saved_plan==compile_plan(load_config(),'smoke'),'Prior smoke schedule changed')
    rows=[json.loads(line) for line in (SMOKE_DIRECTORY/'attempts.jsonl').read_text().splitlines()]
    entries=json.loads((SMOKE_DIRECTORY/'enrollments.json').read_text())
    truth={(r['population_seed'],r['device_index'],r['code']):r for r in entries}
    result=reconcile(rows,saved_plan,truth)
    require(result==json.loads((SMOKE_DIRECTORY/'reconciliation.json').read_text()),'Prior smoke reconciliation mismatch')
    old_sources=json.loads((SMOKE_DIRECTORY/'metadata.json').read_text())['source_sha256']
    allowed_changes={'src/python/scripts/run_reconstruction_alternatives.py',
                     'schemas/reconstruction-alternatives-attempt-v1.schema.json'}
    require(all(digest(ROOT/p)==h for p,h in old_sources.items() if p not in allowed_changes),
            'Scientific runtime changed since validated smoke')
    prior_runtime=json.loads((SMOKE_DIRECTORY/'runtime.json').read_text())
    require(prior_runtime['practicality_gate_passed'] is True,'Prior runtime gate failed')
    validation=json.loads(VALIDATION_PATH.read_text())
    require(validation['status']=='PASS' and validation['mode']=='TESTS_ONLY'
            and validation['source_sha256']==source_hashes(),'Missing, failed or stale Stage 3A test validation')
    suites=validation['suites']
    require(set(suites)==set(REQUIRED_SUITES),'Missing required test suites')
    for name,data in suites.items():
        require(data['exit_code']==0 and data['tests']>0 and data['failures']==0 and data['errors']==0,
                'Failed test prerequisite: '+name)
        log=Path(data['log'])
        require(log.resolve().is_relative_to((ROOT/'tmp').resolve()) and digest(log)==data['log_sha256'],
                'Test log missing or changed')
    return dict(stage2_smoke_manifest_sha256=SMOKE_MANIFEST_SHA256,
                stage2_attempt_count=result['attempt_count'],stage3a_validation_sha256=digest(VALIDATION_PATH),
                tests=sum(d['tests'] for d in suites.values()),status='PASS')


def formal_preflight(output, source_snapshot=None):
    """Read only: no output creation, device factory, measurement, encode/decode."""
    directory=formal_output(output)
    config=load_config()
    require(config['plan_sha256']==PLAN_SHA256,'Wrong approved plan hash')
    plan=compile_plan(config,'compile')
    quantities=validate_formal_plan(plan)
    hashes=source_hashes()
    require({p:h for p,h in hashes.items() if p.startswith('src/')}==_IMPORTED_RUNTIME_HASHES,
            'Loaded runtime source changed since import')
    if source_snapshot is not None:
        verify_source_snapshot(source_snapshot,hashes)
    packages=verify_packages()
    assert_real_runtime()
    DEFAULT_CONFIG.validate()
    alt.CONFIG.validate()
    require((BCHCodec.n,BCHCodec.k,BCHCodec.t)==(63,36,5)
            and (alt.ExperimentalBCHCodec.n,alt.ExperimentalBCHCodec.k,alt.ExperimentalBCHCodec.t)==(63,30,6),
            'Code parameters changed')
    # Algebra setup verifies pinned identities but performs no encoding or decoding.
    BCHCodec().initialize()
    alt.ExperimentalBCHCodec().initialize()
    for p,d in sorted({(t['population_seed'],t['device_index']) for t in plan['schedule']}):
        credential=rng(f'w6ra-v1:credential30:{p}:{d}:0').getrandbits(30).to_bytes(4,'big')
        require(alt.message_to_credential(alt.credential_to_message(credential))==credential,'Invalid B1 credential format')
        require(len(rng(f'w6ra-v1:credential32:{p}:{d}:0').getrandbits(32).to_bytes(4,'big'))==4,'Invalid baseline credential format')
    schema=validator().schema
    require(schema['additionalProperties'] is False and schema['properties']['mode']=={'enum':['NONFORMAL','FORMAL']},
            'Schema mode contract mismatch')
    prerequisites=verify_prior_validation()
    if source_snapshot is not None:
        require(json.loads((Path(source_snapshot)/'manifest.json').read_text())['prerequisites']==prerequisites,
                'Snapshot validation prerequisites mismatch')
    require(source_hashes()==hashes,'Source changed during preflight')
    return dict(status='PASS',mode='FORMAL_DRY_PREFLIGHT',output=str(directory),
                output_exists=directory.exists(),executed_attempts=0,**quantities,
                plan_sha256=PLAN_SHA256,config_sha256=CONFIG_SHA256,
                source_sha256=hashes,source_id=object_digest(hashes),packages=packages,prerequisites=prerequisites)


def create_source_snapshot(directory,hashes,prerequisites):
    directory=Path(directory)
    require(set(hashes)==set(source_dependencies()),'Incomplete snapshot allowlist')
    require(source_hashes()==hashes,'Source changed before snapshot')
    directory.mkdir(exist_ok=False)
    for relative,expected in hashes.items():
        data=(ROOT/relative).read_bytes()
        require(hashlib.sha256(data).hexdigest()==expected,'Source changed while snapshotting')
        target=directory/'files'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
    write_json(directory/'manifest.json',dict(version='w6ra-source-snapshot-v1',files=hashes,
                source_id=object_digest(hashes),prerequisites=prerequisites,
                policy='sanitized allowlist; exclusive creation; immutable by convention'))
    verify_source_snapshot(directory,hashes)


def verify_source_snapshot(directory,hashes):
    directory=Path(directory)
    manifest=json.loads((directory/'manifest.json').read_text())
    require(manifest['files']==hashes and set(hashes)==set(source_dependencies())
            and manifest['source_id']==object_digest(hashes),'Source snapshot manifest mismatch')
    expected={'manifest.json'}|{'files/'+p for p in hashes}
    actual={p.relative_to(directory).as_posix() for p in directory.rglob('*') if p.is_file()}
    require(actual==expected,'Unexpected/missing snapshot files')
    for relative,h in hashes.items():
        path=directory/'files'/relative
        require(not path.is_symlink() and path.resolve().is_relative_to(directory.resolve())
                and digest(path)==h,'Source snapshot hash mismatch')
    return digest(directory/'manifest.json')


def csv_value(value):
    if isinstance(value,(dict,list)):
        return json.dumps(value,sort_keys=True,allow_nan=False)
    return '' if value is None else str(value)


def verify_csv(path,expected):
    with Path(path).open(newline='',encoding='utf8') as stream:
        saved=list(csv.DictReader(stream))
    require(saved==[{k:csv_value(v) for k,v in row.items()} for row in expected],'CSV readback mismatch: '+Path(path).name)


def independent_encode(message, generator):
    """Readback-only GF(2) polynomial division, independent of galois."""
    shifted=int(message,2) << (generator.bit_length()-1)
    remainder=shifted
    while remainder.bit_length()>=generator.bit_length():
        remainder ^= generator << (remainder.bit_length()-generator.bit_length())
    return shifted^remainder


def validate_enrollments(plan,entries):
    devices={(t['population_seed'],t['device_index']) for t in plan['schedule']}
    expected={(p,d,c) for p,d in devices for c in ('baseline','B1')}
    truth={(r['population_seed'],r['device_index'],r['code']):r for r in entries}
    require(len(entries)==len(expected) and set(truth)==expected,'Enrollment identity mismatch')
    for (p,d,code),entry in truth.items():
        bits=30 if code=='B1' else 32
        credential=rng(f"{plan['prefix']}:credential{bits}:{p}:{d}:0").getrandbits(bits).to_bytes(4,'big')
        require(entry['credential_hex']==credential.hex() and entry['generation']==0,'Enrollment credential/format mismatch')
        reference=entry['reference64'];helper=entry['helper_bits']
        require(len(reference)==64 and set(reference)<={'0','1'} and len(helper)==63 and set(helper)<={'0','1'},'Enrollment bit format mismatch')
        message=f'{int.from_bytes(credential,"big"):0{bits}b}'+('0000' if code=='baseline' else '')
        require(int(helper,2)==int(reference[:63],2)^independent_encode(message,0x37CD0EB67 if code=='B1' else 0x86E8113),'Enrollment helper mismatch')
        device_id=f"{plan['prefix']}-p{p}-d{d}"
        require(entry['binding']==dict(device_id=device_id,enrollment_id=f'{device_id}-{code}-g0',
                    reconstruction_id=alt.CONFIG.version if code=='B1' else DEFAULT_CONFIG.version),'Enrollment binding mismatch')
        other=truth[p,d,'baseline' if code=='B1' else 'B1']
        require(entry['reference64']==other['reference64'] and entry['manufacturing_variation']==other['manufacturing_variation'], 'Enrollment device changed across codes')
    return truth


def audit_formal_evidence(directory,hashes):
    """Re-read disk records and rederive accounting; never rerun measurements."""
    directory=Path(directory)
    require(not (directory/'INCOMPLETE.json').exists(),'Incomplete formal evidence')
    require(source_hashes()==hashes,'Runtime source changed before readback')
    plan=json.loads((directory/'trial_plan.json').read_text())
    validate_formal_plan(plan)
    require(digest(directory/'config.json')==CONFIG_SHA256,'Saved configuration mismatch')
    rows=[json.loads(line) for line in (directory/'attempts.jsonl').read_text().splitlines()]
    require(len(rows)==48000 and all(r['mode']=='FORMAL' for r in rows),'Reduced/nonformal evidence cannot complete')
    entries=json.loads((directory/'enrollments.json').read_text())
    require(len(entries)==240,'Formal enrollment count mismatch')
    validate_enrollments(plan,entries)
    truth={(r['population_seed'],r['device_index'],r['code']):r for r in entries}
    require(len(truth)==240,'Duplicate formal enrollments')
    reconciliation=reconcile(rows,plan,truth)
    require(reconciliation==json.loads((directory/'reconciliation.json').read_text()),'Reconciliation readback mismatch')
    require(all(r['source_id']==object_digest(hashes) for r in rows),'Formal source ID mismatch')
    for filename,keys in [('condition_summary.csv',('condition','group')),
                          ('per_device_summary.csv',('condition','group','population_seed','device_index')),
                          ('per_population_summary.csv',('condition','group','population_seed'))]:
        verify_csv(directory/filename,summaries(rows,keys))
    verify_csv(directory/'paired_comparisons.csv',paired(rows))
    verify_csv(directory/'latency_summary.csv',latency_rows(rows))
    summary=json.loads((directory/'summary.json').read_text())
    require(summary['mode']=='FORMAL' and summary['overall']==summarize(rows)
            and summary['conditions']==summaries(rows,('condition','group'))
            and summary['paired_comparisons']==paired(rows)
            and summary['cluster_intervals']==cluster_intervals(rows,load_config()),'Summary/uncertainty readback mismatch')
    for name in ('metadata.json','backend_runtime.json','runtime.json','post_run.json'):
        require(json.loads((directory/name).read_text())['mode']=='FORMAL','Nonformal metadata in formal evidence')
    require(source_hashes()==hashes,'Runtime source changed before completion')
    metadata=json.loads((directory/'metadata.json').read_text())
    require(metadata['source_sha256']==hashes and metadata['source_id']==object_digest(hashes)
            and metadata['trial_plan_sha256']==FORMAL_SCHEDULE_SHA256,'Metadata source/plan mismatch')
    post=json.loads((directory/'post_run.json').read_text())
    require(post['source_sha256']==hashes,'Post-run source mismatch')
    snapshot_hash=verify_source_snapshot(directory/'source_snapshot',hashes)
    require(snapshot_hash==metadata['source_snapshot_manifest_sha256'],'Snapshot manifest changed after creation')
    return dict(mode='FORMAL',status='PASS',attempt_count=48000,source_snapshot_manifest_sha256=snapshot_hash)


def seal_formal(directory,hashes):
    directory=Path(directory)
    receipt=audit_formal_evidence(directory,hashes)
    require(receipt['mode']=='FORMAL' and receipt['status']=='PASS' and receipt['attempt_count']==48000,
            'Formal completion guard failed')
    manifest={p.relative_to(directory).as_posix():digest(p) for p in sorted(directory.rglob('*')) if p.is_file()}
    require(not {'COMPLETE','INCOMPLETE.json','NONFORMAL_VALIDATED.json','manifest.json'} & set(manifest),
            'Existing or conflicting formal seal')
    require(manifest['source_snapshot/manifest.json']==receipt['source_snapshot_manifest_sha256'],
            'Unbound source snapshot')
    write_json(directory/'manifest.json',manifest)
    require(all(digest(directory/name)==h for name,h in manifest.items()),'Formal artifact hash mismatch')
    require(source_hashes()==hashes,'Source changed immediately before COMPLETE')
    verify_source_snapshot(directory/'source_snapshot',hashes)
    write_json(directory/'COMPLETE.pending',dict(receipt,manifest_sha256=digest(directory/'manifest.json'),
                trial_plan_sha256=FORMAL_SCHEDULE_SHA256,source_id=object_digest(hashes),
                interpretation='Evidence integrity complete; no FRR-target success assertion'))
    require(not (directory/'COMPLETE').exists(),'Formal completion already exists')
    os.replace(directory/'COMPLETE.pending',directory/'COMPLETE')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('compile','smoke','preflight','formal'))
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--source-snapshot',type=Path,help='optional existing sanitized bundle to verify during read-only preflight')
    args=parser.parse_args(argv)
    try:
        require(args.source_snapshot is None or args.mode=='preflight','Snapshot option is preflight-only')
        if args.mode=='preflight':
            print(json.dumps(formal_preflight(args.output,args.source_snapshot),sort_keys=True))
        elif args.mode=='formal':
            result=run_formal(args.output)
            print(json.dumps(dict(**result['reconciliation'],runtime=result['runtime'])))
        elif args.mode=='compile':
            config=load_config()
            plan=compile_plan(config,'compile')
            validate_formal_plan(plan)
            output=safe_output(args.output)
            output.mkdir(parents=True,exist_ok=False)
            write_json(output/'trial_plan.json',plan)
            write_json(output/'PLAN_ONLY.json',dict(mode='FORMAL_PLAN_ONLY',executed_attempts=0,
                       expected_attempts=48000,trial_plan_sha256=plan['trial_plan_sha256']))
            print(json.dumps(dict(mode='FORMAL_PLAN_ONLY',executed_attempts=0,attempts=48000,
                                  trial_plan_sha256=plan['trial_plan_sha256'])))
        else:
            result=run_smoke(args.output)
            print(json.dumps(dict(**result['reconciliation'],runtime=result['runtime'])))
    except (ValueError,FileNotFoundError,ImportError) as error:
        parser.error(f'{type(error).__name__}: {error}')


_REAL_RUNTIME_APIS=runtime_apis()
_IMPORTED_RUNTIME_HASHES={p:digest(ROOT/p) for p in source_dependencies() if p.startswith('src/')}

if __name__=='__main__':
    main()