"""Saved-candidate evaluation only. Never reconstruct, simulate, or persist secrets.

Run with --preflight to validate inputs without admission; --evaluate creates a
new exclusive output directory. audit_credential_verifier_experiment.py --seal
independently reconciles records and writes COMPLETE after report/test evidence.
"""
from collections import Counter, defaultdict
from contextlib import ExitStack
from datetime import datetime, timezone
import argparse
import csv
import hashlib
import importlib
import json
import math
from pathlib import Path
import platform
from statistics import mean, median
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / 'configs/credential_verifier_experiment_v1.json'
EXPECTED = {'correct': 56142, 'wrong': 430, 'decoder_failure': 26447, 'invalid_format': 981}
LOCATOR = ('source_row_number', 'condition', 'phase', 'sweep_index', 'measurement_noise_std',
           'simulation_seed', 'device_id', 'device_index', 'enrollment_id', 'attempt_number')
ATTEMPT_FIELDS = set(LOCATOR) | {'schema_version', 'source_manifest_sha256', 'source_artifact_sha256',
    'source_id', 'reconstruction_outcome', 'evaluator_label', 'verification_invoked',
    'verification_calls', 'verifier_result', 'verification_latency_ns', 'admission_result',
    'archived_reconstruction_ns', 'composite_latency_ns'}
COUNTERS = ('credential_verification_calls', 'p3rq_created', 'p3rq_emitted', 'receiver_begin_session',
    'receiver_authorization_accepted', 'sender_derive_session_key', 'receiver_derive_session_key',
    'common_derive_session_key', 'hkdf_extract', 'hkdf_expand', 'client_proof', 'server_proof',
    'pending_session_creation', 'active_session_creation', 'active_session_publication',
    'sender_pending_transition', 'sender_active_transition')
INTEGRATION_FIELDS = set(LOCATOR) | {'population', 'counters', 'verifier_result', 'sender_reason',
    'sender_state', 'receiver_pending_count', 'receiver_active_count', 'confirmation_succeeded',
    'invariant_passed'}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)  # Reasons are fixed safe strings, never source values.


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, obj):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, indent=2, sort_keys=True, allow_nan=False)
        f.write('\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def hash_identity(path, expected):
    raw = Path(path).read_bytes()
    hashes = {'raw_sha256': hashlib.sha256(raw).hexdigest(),
              'lf_sha256': hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()}
    require(expected in hashes.values(), 'source_hash_mismatch')
    return dict(hashes, manifest_sha256=expected,
                representation='raw' if hashes['raw_sha256'] == expected else 'LF-in-memory-only')


def classify(row):
    outcome = row['reconstruction_outcome']
    if outcome == 'decoder_failure':
        return 'decoder_failure'
    if outcome == 'invalid_format_or_padding':
        return 'invalid_format'
    require(outcome == 'candidate_valid_format', 'unknown_reconstruction_outcome')
    require(row['evaluator_outcome'] in ('evaluator_correct_match', 'evaluator_wrong_match'), 'unknown_evaluator_label')
    return 'correct' if row['evaluator_outcome'] == 'evaluator_correct_match' else 'wrong'


def condition(row):
    return 'Nominal' if row['phase'] == 'baseline' else f"Sweep SD {float(row['measurement_noise_std'])}"


def locator(row, number):
    return {**{k: row[k] for k in LOCATOR if k not in ('source_row_number', 'condition')},
            'source_row_number': number, 'condition': condition(row)}


def source(config):
    path = ROOT / config['source_evidence']
    complete = read_json(path/'COMPLETE')
    require(complete['attempt_count'] == 84000 and complete['source_id'] == config['source_id'], 'source_complete_mismatch')
    require(complete['manifest_sha256'] == config['source_manifest_sha256'], 'source_identity_mismatch')
    integrity = {'manifest': hash_identity(path/'manifest.json', config['source_manifest_sha256']),
                 'complete_raw_sha256': sha(path/'COMPLETE'), 'artifacts': {}}
    for name, digest in read_json(path/'manifest.json').items():
        require(Path(name).name == name, 'invalid_manifest_path')
        integrity['artifacts'][name] = hash_identity(path/name, digest)
    enrollments = read_json(path/'enrollments.json')
    enrolled = {e['enrollment_id']: e for e in enrollments}
    require(len(enrollments) == len(enrolled) == 120, 'enrollment_count_mismatch')
    rows = [json.loads(line) for line in (path/'attempts.jsonl').read_text(encoding='utf-8').splitlines()]
    require(len(rows) == 84000 and Counter(map(classify, rows)) == EXPECTED, 'source_population_mismatch')
    seen = set()
    for r in rows:
        key = (r['simulation_seed'], r['device_id'], r['phase'], r['sweep_index'], r['attempt_number'])
        require(key not in seen, 'duplicate_source_identity'); seen.add(key)
        e = enrolled[r['enrollment_id']]
        require((r['simulation_seed'], r['device_id']) == (e['simulation_seed'], e['device_id']), 'enrollment_binding_mismatch')
        require(r['source_id'] == config['source_id'], 'row_source_id_mismatch')
        cat = classify(r)
        if cat in ('correct', 'wrong'):
            bits = r['candidate_message36']
            require(type(bits) is str and len(bits) == 36 and set(bits) <= {'0','1'} and bits[-4:] == '0000', 'invalid_saved_message')
            require(r['candidate_credential_hex'] == f'{int(bits[:32],2):08x}', 'candidate_message_mismatch')
            require(r['padding_valid'] is True and r['decoder_status'] == 'decoded', 'candidate_format_mismatch')
            # Preflight validates archived labels; runtime never receives truth.
            match = r['candidate_credential_hex'] == e['evaluator_enrolled_credential_hex']
            require(match == (cat == 'correct') == r['evaluator_success'], 'source_truth_label_mismatch')
        else:
            require(r['candidate_credential_hex'] is None and r['evaluator_outcome'] == 'no_valid_candidate', 'invalid_skipped_row')
        require(type(r['reconstruction_latency_ns']) is int and r['reconstruction_latency_ns'] >= 0, 'invalid_archived_latency')
    regressions = []
    for seed, dev, attempt in ((2222,3,88),(6543,1,75)):
        found = [(i,r) for i,r in enumerate(rows,1) if r['phase']=='baseline' and
                 (r['simulation_seed'],r['device_index'],r['attempt_number']) == (seed,dev,attempt)]
        require(len(found)==1 and classify(found[0][1])=='wrong', 'nominal_regression_missing')
        regressions.append(locator(found[0][1],found[0][0]))
    integrity.update(population=dict(Counter(map(classify,rows))), enrollment_count=len(enrolled), nominal_regressions=regressions)
    return rows, enrolled, integrity


def statistics(values):
    values = sorted(values)
    if not values:
        return dict(n=0, mean_ns=None, median_ns=None, p95_ns=None, max_ns=None)
    pos=(len(values)-1)*.95; lower=int(pos)
    return dict(n=len(values), mean_ns=mean(values), median_ns=median(values),
                p95_ns=values[lower]+(values[min(lower+1,len(values)-1)]-values[lower])*(pos-lower), max_ns=values[-1])


def wilson(successes, n):
    z=1.959963984540054; p=successes/n; d=1+z*z/n
    center=(p+z*z/(2*n))/d; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return max(0.,center-half), min(1.,center+half)


def write_csv(path, rows):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def emit(f, row, fields):
    require(set(row)==fields, 'unsafe_output_fields')
    f.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')


def provision(enrolled, config):
    from puf_snn.auth.credential_verifier import (CredentialVerifierRecord, CredentialVerifierStore,
        InMemoryCredentialVerifierKeyProvider, CredentialAdmissionService)
    provider=InMemoryCredentialVerifierKeyProvider.generate(config['verifier_key_id'])
    records=[CredentialVerifierRecord.enroll(device_id=e['device_id'], enrollment_id=e['enrollment_id'],
        reconstruction_id=config['reconstruction_profile'], verifier_key_id=config['verifier_key_id'],
        credential4=bytes.fromhex(e['evaluator_enrolled_credential_hex']),key_provider=provider) for e in enrolled.values()]
    require(all(r.schema==config['verifier_schema'] and r.algorithm==config['verifier_algorithm'] for r in records),'verifier_identifier_mismatch')
    return CredentialAdmissionService(CredentialVerifierStore(records),provider)


def warmup(config):
    fixture={'enrollment_id':'warmup-enrollment','device_id':'warmup-device',
             'evaluator_enrolled_credential_hex':'000001a5'}
    service=provision({'warmup-enrollment':fixture},config)
    for i in range(config['warmup']['count']):
        result=service.verify(b'\x00\x00\x01\xa5' if i%2==0 else bytes(4),device_id='warmup-device',
            enrollment_id='warmup-enrollment', reconstruction_id=config['reconstruction_profile'])
        require(result.verified == (i%2==0),'warmup_failed')


def reconstruction_guards(stack):
    """Raise before any codec/reconstruction operation, retaining only counts."""
    counters=Counter()
    def forbidden(*args,**kwargs):
        counters['forbidden_reconstruction_calls']+=1
        raise RuntimeError('reconstruction_forbidden')
    for target in ('puf_snn.reconstruction.reconstruct','puf_snn.reconstruction.enroll',
        'puf_snn.reconstruction.credential.reconstruct','puf_snn.reconstruction.credential.enroll',
        'puf_snn.reconstruction.bch.BCHCodec.encode','puf_snn.reconstruction.bch.BCHCodec.decode'):
        stack.enter_context(patch(target,new=forbidden))
    return counters


def integration(row, number, enrolled, service, config):
    from puf_snn.auth import session
    from puf_snn.auth.sender import Sender
    from puf_snn.auth.verifier import Verifier
    from puf_snn.auth.config import AuthConfig
    from puf_snn.auth.credential_verifier import CredentialAdmissionService
    from puf_snn.reconstruction import HelperData, ReconstructionResult
    e=enrolled[row['enrollment_id']]
    helper=HelperData(tuple(map(int,e['helper63'])),enrollment_id=e['enrollment_id'])
    binding=session.provision_device(e['device_id'],e['enrollment_id'],helper)
    auth=AuthConfig.load(ROOT/config['authentication_config'])
    sender=Sender(binding,limits=auth.session_config().limits,admission_service=service)
    receiver=Verifier([session.RegistryEntry(e['device_id'],e['enrollment_id'],
        bytes.fromhex(e['evaluator_enrolled_credential_hex']))],config=auth.session_config(),admission_service=service)
    candidate=ReconstructionResult(row['reconstruction_outcome'],row['decoder_status'],
        row['reported_correction_count'],tuple(map(int,row['candidate_message36'])),
        bytes.fromhex(row['candidate_credential_hex']),row['padding_valid'],row['reconstruction_failure_reason'])
    counts=dict.fromkeys(COUNTERS,0); outcomes=[]
    def wrap(actual, name):
        def call(*args,**kwargs):
            counts[name]+=1
            return actual(*args,**kwargs)
        return call
    actual_verify=CredentialAdmissionService.verify
    def verify(*args,**kwargs):
        counts['credential_verification_calls']+=1
        result=actual_verify(*args,**kwargs); outcomes.append(result.outcome); return result
    actual_consume=CredentialAdmissionService.consume
    def consume(*args,**kwargs):
        result=actual_consume(*args,**kwargs)
        counts['receiver_authorization_accepted']+=int(result)
        return result
    actual_frame=session.frame
    def frame(body):
        if body[:4]==b'P3RQ': counts['p3rq_created']+=1
        return actual_frame(body)
    mapping={'sender.derive_session_key':'sender_derive_session_key','verifier.derive_session_key':'receiver_derive_session_key',
        'session.derive_session_key':'common_derive_session_key','session.hkdf_extract':'hkdf_extract',
        'session.hkdf_expand':'hkdf_expand','session.client_proof':'client_proof','session.server_proof':'server_proof',
        'session._Pending':'pending_session_creation','session._Active':'active_session_creation'}
    succeeded=False
    with ExitStack() as stack:
        for target,name in mapping.items():
            mod,attr=target.split('.'); module=importlib.import_module('puf_snn.auth.'+mod)
            stack.enter_context(patch.object(module,attr,new=wrap(getattr(module,attr),name)))
        stack.enter_context(patch.object(CredentialAdmissionService,'verify',new=verify))
        stack.enter_context(patch.object(CredentialAdmissionService,'consume',new=consume))
        stack.enter_context(patch.object(session,'frame',new=frame))
        stack.enter_context(patch.object(receiver,'begin_session',new=wrap(receiver.begin_session,'receiver_begin_session')))
        request=sender.begin_attempt(candidate,f'formal-row-{number}')
        counts['sender_pending_transition']=int(sender.state=='PENDING')
        if type(request) is bytes:
            counts['p3rq_emitted']=int(request[4:8]==b'P3RQ')
            challenge=receiver.begin_session(request,admission=sender.admission)
            if challenge != session.REFUSAL:
                proof=sender.answer_challenge(challenge)
                if type(proof) is bytes:
                    response=receiver.confirm_session(proof)
                    counts['active_session_publication']=len(receiver.active_session_ids)
                    succeeded=sender.finish_session(response) is sender
        counts['sender_active_transition']=int(sender.state=='ACTIVE')
    wrong=classify(row)=='wrong'
    expected=dict.fromkeys(COUNTERS,0)
    expected['credential_verification_calls']=1
    if not wrong:
        expected.update(p3rq_created=1,p3rq_emitted=1,receiver_begin_session=1,receiver_authorization_accepted=1,
            sender_derive_session_key=1,receiver_derive_session_key=1,hkdf_extract=2,hkdf_expand=2,client_proof=2,
            server_proof=2,pending_session_creation=1,active_session_creation=1,active_session_publication=1,
            sender_pending_transition=1,sender_active_transition=1)
    passed=(counts==expected and outcomes==(['credential_mismatch'] if wrong else ['verified']) and
        (not succeeded if wrong else succeeded) and len(receiver._pending)==0 and
        len(receiver.active_session_ids)==(0 if wrong else 1) and
        (sender.reason=='credential_verification_failed' and sender.state=='FAILED' if wrong else sender.state=='ACTIVE'))
    return dict(locator(row,number),population='miscorrections' if wrong else 'positive_controls',counters=counts,
        verifier_result=outcomes[0] if len(outcomes)==1 else 'unexpected_call_count',sender_reason=sender.reason,
        sender_state=sender.state,receiver_pending_count=len(receiver._pending),receiver_active_count=len(receiver.active_session_ids),
        confirmation_succeeded=succeeded,invariant_passed=passed)


def summaries(rows, output):
    conditions=[]; timings=[]; decisions=[]
    def timing(group, population):
        invoked=[r for r in group if r['verification_invoked']]
        for kind,field in (('verification','verification_latency_ns'),('archived reconstruction + current verification composite latency','composite_latency_ns')):
            timings.append(dict(population=population,measurement=kind,**statistics([r[field] for r in invoked])))
    for name in dict.fromkeys(r['condition'] for r in rows):
        group=[r for r in rows if r['condition']==name]
        labels=Counter(r['evaluator_label'] for r in group)
        conditions.append(dict(condition=name,total_source_rows=len(group),
            decoder_failures=sum(r['reconstruction_outcome']=='decoder_failure' for r in group),
            invalid_format=sum(r['reconstruction_outcome']=='invalid_format_or_padding' for r in group),
            correct_valid_format=labels['correct'],wrong_valid_format=labels['wrong'],
            verifier_invocations=sum(r['verification_calls'] for r in group),
            correct_admitted=sum(r['evaluator_label']=='correct' and r['admission_result']=='admitted' for r in group),
            correct_rejected=sum(r['evaluator_label']=='correct' and r['admission_result']=='rejected' for r in group),
            wrong_rejected=sum(r['evaluator_label']=='wrong' and r['admission_result']=='rejected' for r in group),
            wrong_admitted=sum(r['evaluator_label']=='wrong' and r['admission_result']=='admitted' for r in group),
            **statistics([r['verification_latency_ns'] for r in group if r['verification_invoked']])))
        timing(group,name)
    for label in ('correct','wrong'):
        group=[r for r in rows if r['evaluator_label']==label]
        admitted=sum(r['admission_result']=='admitted' for r in group); rejected=len(group)-admitted
        successes=admitted if label=='correct' else rejected; low,high=wilson(successes,len(group))
        decisions.append(dict(population=label,n=len(group),admitted=admitted,rejected=rejected,
            admission_percent=100*admitted/len(group),rejection_percent=100*rejected/len(group),
            wilson_target='admission' if label=='correct' else 'rejection',wilson_lower=low,wilson_upper=high,
            complementary_error_upper=1-low))
        timing(group,label)
    timing(rows,'all invocations')
    for outcome in ('decoder_failure','invalid_format_or_padding'):
        timings.append(dict(population=outcome,measurement='archived reconstruction only; verifier not checked',
            **statistics([r['archived_reconstruction_ns'] for r in rows if r['reconstruction_outcome']==outcome])))
    write_csv(output/'condition_summary.csv',conditions); write_csv(output/'verifier_summary.csv',decisions)
    write_csv(output/'latency_summary.csv',timings)


def protected_check(before, output):
    changed=[name for name,digest in before.items() if not (ROOT/name).is_file() or sha(ROOT/name)!=digest]
    old_results={n for n in before if n.startswith('results/')}
    current={p.relative_to(ROOT).as_posix() for p in (ROOT/'results').rglob('*') if p.is_file() and not p.is_relative_to(output)}
    require(not changed and current==old_results,'protected_files_changed')
    return {'file_count':len(before),'all_raw_bytes_unchanged':True,'hashes_before_and_after':before}


def protected_snapshot():
    paths=[p for p in (ROOT/'results').rglob('*') if p.is_file()]
    paths+=list((ROOT/'src/python/puf_snn').rglob('*.py'))
    paths+=[ROOT/'docs/layer3-baseline-v1-manifest.json',ROOT/'configs/authentication_v1.json',ROOT/'configs/authentication_v2.json']
    paths+=list((ROOT/'schemas').glob('*auth*'))
    return {p.relative_to(ROOT).as_posix():sha(p) for p in paths if p.is_file()}


def evaluate(config):
    rows,enrolled,integrity=source(config)  # Stop before provisioning on any mismatch.
    before=protected_snapshot()
    output=ROOT/config['output_directory']; output.mkdir(parents=True,exist_ok=False)
    write_json(output/'config.json',config); write_json(output/'source_integrity.json',integrity)
    write_json(output/'attempt.schema.json',read_json(ROOT/'schemas/credential-verifier-attempt-v1.schema.json'))
    protected_check(before,output)
    metadata={'started_utc':datetime.now(timezone.utc).isoformat(),'python':sys.version,'platform':platform.platform(),
        'clock':vars(time.get_clock_info('perf_counter')),'source_counts':integrity['population'],
        'verifier_records':len(enrolled),'key_persisted':False,'reconstruction_rerun':False,
        'warmup':config['warmup'],'gc_policy':'default enabled','thread_policy':'single sequential evaluator thread',
        'timing_scope':config['timing'],'source_code_sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in
            [Path(__file__),ROOT/'src/python/scripts/audit_credential_verifier_experiment.py',
             ROOT/'tests/experiments/test_credential_verifier_experiment.py',
             ROOT/'configs/credential_verifier_experiment_v1.json',ROOT/'schemas/credential-verifier-attempt-v1.schema.json']}}
    try:
        from puf_snn.auth.config import AuthConfig
        from puf_snn.auth import credential_verifier as cv
        auth=AuthConfig.load(ROOT/config['authentication_config'])
        require(auth.config_version==config['authentication_config_version'] and auth.protocol_profile==config['authentication_profile'] and
                cv._DOMAIN.decode()==config['verifier_domain'],'implementation_identifier_mismatch')
        with ExitStack() as stack:
            guards=reconstruction_guards(stack)
            service=provision(enrolled,config); warmup(config)
            safe=[]; anomalies=[]; calls=0; controls={}; wrong=[]
            with (output/'attempts.jsonl').open('x',encoding='utf-8',newline='\n') as f:
                for number,row in enumerate(rows,1):
                    label=classify(row); valid=label in ('correct','wrong')
                    result='not_checked'; elapsed=None
                    if valid:
                        candidate=bytes.fromhex(row['candidate_credential_hex'])
                        # Resolve candidate and trusted binding before starting the clock.
                        context=dict(device_id=enrolled[row['enrollment_id']]['device_id'],
                            enrollment_id=row['enrollment_id'],reconstruction_id=config['reconstruction_profile'])
                        verify=service.verify
                        calls+=1
                        start=time.perf_counter_ns()
                        decision=verify(candidate,**context)
                        elapsed=time.perf_counter_ns()-start
                        result=decision.outcome
                        # Evaluator truth is consulted only after the runtime result.
                        truth_match=candidate==bytes.fromhex(enrolled[row['enrollment_id']]['evaluator_enrolled_credential_hex'])
                        require(truth_match==(label=='correct'),'post_verification_truth_mismatch')
                        if decision.verified != truth_match:
                            anomalies.append(dict(locator(row,number),verifier_result=result))
                        if label=='wrong': wrong.append((number,row))
                        elif row['enrollment_id'] not in controls: controls[row['enrollment_id']]=(number,row)
                    record=dict(locator(row,number),schema_version=config['output_version'],source_id=config['source_id'],
                        source_manifest_sha256=config['source_manifest_sha256'],
                        source_artifact_sha256=integrity['artifacts']['attempts.jsonl']['manifest_sha256'],
                        reconstruction_outcome=row['reconstruction_outcome'],evaluator_label=label if valid else 'not_checked',
                        verification_invoked=valid,verification_calls=int(valid),verifier_result=result,verification_latency_ns=elapsed,
                        admission_result=('admitted' if decision.verified else 'rejected') if valid else 'not_checked',
                        archived_reconstruction_ns=row['reconstruction_latency_ns'],
                        composite_latency_ns=row['reconstruction_latency_ns']+elapsed if valid else None)
                    emit(f,record,ATTEMPT_FIELDS); safe.append(record)
            metadata['formal_verifier_calls']=calls
            summaries(safe,output)
            write_json(output/'anomalies.json',anomalies)
            require(not anomalies,'candidate_decision_failure')
            for filename,population in (('integration_miscorrections.jsonl',wrong),('integration_controls.jsonl',list(controls.values()))):
                with (output/filename).open('x',encoding='utf-8',newline='\n') as f:
                    for number,row in population:
                        evidence=integration(row,number,enrolled,service,config)
                        emit(f,evidence,INTEGRATION_FIELDS); f.flush()
                        require(evidence['invariant_passed'],'integration_security_invariant_failure')
            metadata['forbidden_reconstruction_calls']=guards['forbidden_reconstruction_calls']
            require(not guards['forbidden_reconstruction_calls'],'reconstruction_was_called')
        write_json(output/'protected_integrity.json',protected_check(before,output))
        metadata['finished_utc']=datetime.now(timezone.utc).isoformat()
        metadata['status']='evaluated_pending_independent_reconciliation'
        write_json(output/'metadata.json',metadata)
        print(json.dumps({'status':metadata['status'],'formal_verifier_calls':calls,'wrong_integration':len(wrong),'positive_controls':len(controls)}))
    except Exception as error:
        # No repr, input values, traceback locals, or secret-containing dataclasses.
        write_json(output/'INCOMPLETE',{'status':'failed','error_type':type(error).__name__})
        if not (output/'metadata.json').exists():
            metadata['status']='failed'; write_json(output/'metadata.json',metadata)
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',action='store_true'); parser.add_argument('--evaluate',action='store_true')
    args=parser.parse_args(); config=read_json(CONFIG)
    if args.preflight:
        _,_,integrity=source(config); print(json.dumps(integrity,indent=2))
    elif args.evaluate:
        evaluate(config)
    else:
        parser.error('choose --preflight or --evaluate')


if __name__=='__main__':
    main()
