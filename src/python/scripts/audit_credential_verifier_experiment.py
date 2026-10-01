"""Independent read-only reconciliation of safe records against saved source.

No authentication, reconstruction, simulation, or verifier imports. --seal writes
reconciliation, hashes all artifacts, and writes COMPLETE last, exclusively.
"""
from collections import Counter, defaultdict
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT=Path(__file__).resolve().parents[3]


def check(condition,reason):
    if not condition: raise ValueError(reason)


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def lines(path): return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def audit_attempt(record, source, number, enrollment, config, artifact_hash, allowed):
    check(set(record)==allowed,'unsafe_attempt_fields')
    check(record['source_row_number']==number,'source_row_order_or_duplicate')
    for key in ('phase','sweep_index','measurement_noise_std','simulation_seed','device_id','device_index','enrollment_id','attempt_number'):
        check(record[key]==source[key],'locator_mismatch')
    expected_condition='Nominal' if source['phase']=='baseline' else f"Sweep SD {float(source['measurement_noise_std'])}"
    check(record['condition']==expected_condition,'condition_mismatch')
    check(record['schema_version']==config['output_version'] and record['source_id']==config['source_id'] and
          record['source_manifest_sha256']==config['source_manifest_sha256'] and record['source_artifact_sha256']==artifact_hash,'identity_mismatch')
    check(record['reconstruction_outcome']==source['reconstruction_outcome'],'outcome_mismatch')
    valid=source['reconstruction_outcome']=='candidate_valid_format'
    check(type(record['verification_invoked']) is bool and record['verification_invoked']==valid and
          type(record['verification_calls']) is int and record['verification_calls']==int(valid),'invocation_mismatch')
    archived=source['reconstruction_latency_ns']
    check(record['archived_reconstruction_ns']==archived,'archived_latency_mismatch')
    if valid:
        correct=source['candidate_credential_hex']==enrollment['evaluator_enrolled_credential_hex']
        check(record['evaluator_label']==('correct' if correct else 'wrong'),'truth_label_mismatch')
        check(record['verifier_result']==('verified' if correct else 'credential_mismatch'),'decision_failure')
        check(record['admission_result']==('admitted' if correct else 'rejected'),'admission_failure')
        latency=record['verification_latency_ns']
        check(type(latency) is int and latency>=0,'invalid_latency')
        check(record['composite_latency_ns']==archived+latency,'composite_pairing_failure')
    else:
        check(all(record[k]=='not_checked' for k in ('evaluator_label','verifier_result','admission_result')),'unchecked_mismatch')
        check(record['verification_latency_ns'] is None and record['composite_latency_ns'] is None,'unchecked_latency')


def stats(values):
    if not values: return dict(n=0,mean_ns=None,median_ns=None,p95_ns=None,max_ns=None)
    ordered=sorted(values); x=(len(ordered)-1)*.95; i=math.floor(x)
    return dict(n=len(values),mean_ns=statistics.mean(values),median_ns=statistics.median(values),
        p95_ns=ordered[i]*(1-(x-i))+ordered[min(i+1,len(ordered)-1)]*(x-i),max_ns=max(values))


def csv_rows(path):
    with path.open(encoding='utf-8',newline='') as f: return list(csv.DictReader(f))


def equal_metrics(saved,expected):
    for key,value in expected.items():
        if value is None: check(saved[key]=='','empty_stat_mismatch')
        else: check(math.isclose(float(saved[key]),value,rel_tol=1e-12,abs_tol=1e-9),'summary_metric_mismatch')


def audit(output):
    config=load(output/'config.json'); source_dir=ROOT/config['source_evidence']
    manifest=load(source_dir/'manifest.json'); complete=load(source_dir/'COMPLETE')
    check(complete['manifest_sha256']==config['source_manifest_sha256'],'source_manifest_identity')
    for path,expected in [(source_dir/'manifest.json',config['source_manifest_sha256'])]+[(source_dir/n,h) for n,h in manifest.items()]:
        data=path.read_bytes()
        check(expected in (hashlib.sha256(data).hexdigest(),hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()),'source_hash_changed')
    before=load(output/'protected_integrity.json')['hashes_before_and_after']
    check(all((ROOT/n).is_file() and digest(ROOT/n)==h for n,h in before.items()),'protected_bytes_changed')
    existing={p.relative_to(ROOT).as_posix() for p in (ROOT/'results').rglob('*') if p.is_file() and not p.is_relative_to(output)}
    check(existing=={n for n in before if n.startswith('results/')},'historical_file_set_changed')
    schema=load(ROOT/'schemas/credential-verifier-attempt-v1.schema.json')
    allowed=set(schema['required'])
    enrollments={e['enrollment_id']:e for e in load(source_dir/'enrollments.json')}
    source=lines(source_dir/'attempts.jsonl'); attempts=lines(output/'attempts.jsonl')
    check(len(source)==len(attempts)==84000,'row_count_mismatch')
    categories=Counter(); conditions=defaultdict(list); wrong=set(); controls={}
    for number,(s,r) in enumerate(zip(source,attempts),1):
        audit_attempt(r,s,number,enrollments[s['enrollment_id']],config,manifest['attempts.jsonl'],allowed)
        category=r['evaluator_label'] if r['verification_invoked'] else r['reconstruction_outcome']
        categories[category]+=1; conditions[r['condition']].append(r)
        if category=='wrong': wrong.add(number)
        if category=='correct': controls.setdefault(r['enrollment_id'],number)
    check(categories=={'correct':56142,'wrong':430,'decoder_failure':26447,'invalid_format_or_padding':981},'population_mismatch')
    check(sum(r['verification_calls'] for r in attempts)==56572,'invocation_count_mismatch')
    check(len(controls)==len(enrollments)==120,'control_coverage_mismatch')
    integrated={}
    counter_names={'credential_verification_calls','p3rq_created','p3rq_emitted','receiver_begin_session',
        'receiver_authorization_accepted','sender_derive_session_key','receiver_derive_session_key','common_derive_session_key',
        'hkdf_extract','hkdf_expand','client_proof','server_proof','pending_session_creation','active_session_creation',
        'active_session_publication','sender_pending_transition','sender_active_transition'}
    locator_keys={'source_row_number','condition','phase','sweep_index','measurement_noise_std','simulation_seed','device_id',
        'device_index','enrollment_id','attempt_number'}
    integration_keys=locator_keys|{'population','counters','verifier_result','sender_reason','sender_state','receiver_pending_count',
        'receiver_active_count','confirmation_succeeded','invariant_passed'}
    for filename,expected_rows,population in [('integration_miscorrections.jsonl',wrong,'miscorrections'),
                                             ('integration_controls.jsonl',set(controls.values()),'positive_controls')]:
        rows=lines(output/filename)
        check(len(rows)==len(expected_rows) and {r['source_row_number'] for r in rows}==expected_rows,'integration_coverage_mismatch')
        totals=Counter()
        for r in rows:
            check(set(r)==integration_keys and set(r['counters'])==counter_names,'unsafe_integration_fields')
            check(all(type(v) is int and v>=0 for v in r['counters'].values()),'invalid_counter_type')
            original=attempts[r['source_row_number']-1]
            check(all(r[k]==original[k] for k in locator_keys),'integration_locator_mismatch')
            expected=dict.fromkeys(counter_names,0); expected['credential_verification_calls']=1
            positive=population=='positive_controls'
            if positive:
                for k in counter_names-{'common_derive_session_key'}: expected[k]=1
                for k in ('hkdf_extract','hkdf_expand','client_proof','server_proof'): expected[k]=2
            check(r['counters']==expected and r['invariant_passed'] is True,'security_invariant_failure')
            check(r['population']==population and r['verifier_result']==('verified' if positive else 'credential_mismatch'),'integration_result_mismatch')
            check(r['sender_state']==('ACTIVE' if positive else 'FAILED') and
                  r['sender_reason']==('accepted' if positive else 'credential_verification_failed'),'integration_state_mismatch')
            check(r['receiver_pending_count']==0 and r['receiver_active_count']==int(positive) and
                  r['confirmation_succeeded'] is positive,'integration_confirmation_mismatch')
            totals.update(r['counters'])
        integrated[population]={'n':len(rows),'all_passed':True,'counter_totals':dict(totals)}
    summary=csv_rows(output/'condition_summary.csv')
    check(len(summary)==len(conditions)==7,'condition_count_mismatch')
    for saved in summary:
        group=conditions[saved['condition']]
        check(len(group)==12000,'condition_population_mismatch')
        expected={'total_source_rows':len(group),'decoder_failures':sum(r['reconstruction_outcome']=='decoder_failure' for r in group),
            'invalid_format':sum(r['reconstruction_outcome']=='invalid_format_or_padding' for r in group),
            'verifier_invocations':sum(r['verification_calls'] for r in group)}
        for category in ('correct','wrong'):
            expected[category+'_valid_format']=sum(r['evaluator_label']==category for r in group)
            for decision in ('admitted','rejected'):
                expected[category+'_'+decision]=sum(r['evaluator_label']==category and r['admission_result']==decision for r in group)
        expected.update(stats([r['verification_latency_ns'] for r in group if r['verification_invoked']]))
        equal_metrics(saved,expected)
    timing=csv_rows(output/'latency_summary.csv')
    check(len(timing)==22,'latency_summary_count_mismatch')
    check(len({(r['population'],r['measurement']) for r in timing})==22,'duplicate_latency_summary')
    for saved in timing:
        pop=saved['population']; kind=saved['measurement']
        if pop in conditions: group=conditions[pop]
        elif pop=='all invocations': group=attempts
        elif pop in ('correct','wrong'): group=[r for r in attempts if r['evaluator_label']==pop]
        else: group=[r for r in attempts if r['reconstruction_outcome']==pop]
        if kind=='verification': field='verification_latency_ns'
        elif kind=='archived reconstruction + current verification composite latency': field='composite_latency_ns'
        else:
            check(kind=='archived reconstruction only; verifier not checked','unknown_latency_kind'); field='archived_reconstruction_ns'
        equal_metrics(saved,stats([r[field] for r in group if r[field] is not None]))
    for saved in csv_rows(output/'verifier_summary.csv'):
        category=saved['population']; group=[r for r in attempts if r['evaluator_label']==category]
        admitted=sum(r['admission_result']=='admitted' for r in group); n=len(group); rejected=n-admitted
        success=admitted if category=='correct' else rejected; z=1.959963984540054
        p=success/n; denominator=1+z*z/n
        center=(p+z*z/(2*n))/denominator
        delta=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denominator
        low=max(0,center-delta); high=min(1,center+delta)
        equal_metrics(saved,dict(n=n,admitted=admitted,rejected=rejected,admission_percent=100*admitted/n,
            rejection_percent=100*rejected/n,wilson_lower=low,wilson_upper=high,complementary_error_upper=1-low))
    metadata=load(output/'metadata.json')
    check(metadata['formal_verifier_calls']==56572 and metadata['forbidden_reconstruction_calls']==0,'runtime_counter_failure')
    check(load(output/'anomalies.json')==[],'decision_anomaly')
    for n,h in metadata['source_code_sha256'].items(): check(digest(ROOT/n)==h,'evaluator_code_changed')
    # Defense in depth for all JSON artifacts; schemas/allowlists enforce row safety.
    forbidden={'candidate_credential','candidate_credential_hex','credential4','enrolled_credential',
        'evaluator_enrolled_credential_hex','candidate_message','candidate_message36','tag','verifier_tag',
        'verifier_key','key','session_key','response64','selected_response63','puf_response','confirmation_proof',
        'evaluator_reference64','helper63'}
    def safe_tree(obj):
        if isinstance(obj,dict):
            check(not forbidden.intersection(obj),'secret_bearing_field')
            for value in obj.values(): safe_tree(value)
        elif isinstance(obj,list):
            for value in obj: safe_tree(value)
    for p in output.glob('*.json'): safe_tree(load(p))
    for filename in ('attempts.jsonl','integration_miscorrections.jsonl','integration_controls.jsonl'):
        for r in lines(output/filename): safe_tree(r)
    nominal=[r for r in lines(output/'integration_miscorrections.jsonl') if r['condition']=='Nominal']
    check({(r['simulation_seed'],r['device_index'],r['attempt_number']) for r in nominal}=={(2222,3,88),(6543,1,75)},'known_regression_mismatch')
    return {'status':'PASS','source_attempts':84000,'unique_source_locators':len({r['source_row_number'] for r in attempts}),
        'source_population':dict(categories),'formal_verifier_invocations':56572,'integration':integrated,
        'all_source_rows_once':True,'not_checked_only_decoder_or_format':True,'latency_pairing_and_summaries_recomputed':True,
        'safe_field_checks_passed':True,'protected_file_count':len(before),'protected_bytes_unchanged':True,
        'source_manifest_sha256':config['source_manifest_sha256'],'auditor_source_sha256':digest(Path(__file__))}


def write(path,obj):
    with path.open('x',encoding='utf-8',newline='\n') as f: json.dump(obj,f,indent=2,sort_keys=True); f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--seal',action='store_true')
    args=parser.parse_args(); config=load(ROOT/'configs/credential_verifier_experiment_v1.json'); output=ROOT/config['output_directory']
    try:
        result=audit(output)
        if args.seal:
            check(not (output/'INCOMPLETE').exists(),'incomplete_marker_present')
            check((output/'formal_results.md').is_file() and (output/'validation.json').is_file(),'report_or_validation_missing')
            check(load(output/'validation.json')['status']=='PASS','tests_not_passed')
            write(output/'reconciliation.json',result)
            manifest={p.name:digest(p) for p in sorted(output.iterdir()) if p.is_file()}
            write(output/'manifest.json',manifest)
            check(all(digest(output/n)==h for n,h in manifest.items()),'output_manifest_mismatch')
            write(output/'COMPLETE',{'experiment_version':config['experiment_version'],'output_identity':config['output_identity'],
                'attempt_count':84000,'verifier_invocations':56572,'manifest_sha256':digest(output/'manifest.json'),
                'reconciliation_sha256':digest(output/'reconciliation.json'),'status':'PASS'})
        print(json.dumps(result,indent=2))
    except Exception:
        if not (output/'COMPLETE').exists() and not (output/'INCOMPLETE').exists():
            write(output/'INCOMPLETE',{'status':'reconciliation_failed'})
        raise


if __name__=='__main__': main()
