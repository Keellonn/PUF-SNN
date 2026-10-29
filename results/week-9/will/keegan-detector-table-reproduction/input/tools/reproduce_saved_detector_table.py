"""Recompute one historical detector table from saved scores with the standard library.

This does not run models, authenticate messages or recompute bootstrap intervals.
An implementer's dry run is not independent-person reproduction.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import platform

MANIFEST_SHA="8c053eadacf67c97f4d886a8116df17f185afb818d2e25439090fb7d7275f13e"
COMPLETE_SHA="7f6b319dc09b8d85a9ff47c9c8110ddc96ebf5c8fade134640dd02d0bf5bc4cb"
REFERENCE_SHA="dc234b0bbccbc56dacd6009b5bd444ff202ad09720fbf46443e1c87b97f41952"
INPUTS=("config.json","construction-summary.json","frozen-validation-thresholds.json","authenticated-test-predictions.jsonl")

def digest(path):
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def require(condition,message):
    if not condition:raise ValueError(message)

def load(path):return json.loads(path.read_text(encoding="utf-8"))

def reproduce(root):
    source=root/"results/week-5/keegan/stream-evaluation"
    reference=root/"results/week-6/keegan/tier2-source-uncertainty"
    verified={}
    def check(path,expected):
        actual=digest(path);require(actual==expected,"Frozen input differs: "+path.name)
        verified[path.relative_to(root).as_posix()]=actual
    check(source/"manifest.json",MANIFEST_SHA);check(source/"COMPLETE",COMPLETE_SHA)
    manifest=load(source/"manifest.json")
    for name in INPUTS:check(source/name,manifest["artifacts"][name])
    check(reference/"manifest.json",REFERENCE_SHA)
    reference_manifest=load(reference/"manifest.json")
    check(reference/"family-summary.csv",reference_manifest["artifacts"]["family-summary.csv"])
    config=load(source/"config.json");thresholds=load(source/"frozen-validation-thresholds.json")
    construction=load(source/"construction-summary.json")
    wanted={tuple(k.split(":")[1:]):v["quality_valid"] for k,v in construction.items() if k.startswith("test:")}
    require(len(wanted)==28 and sum(wanted.values())==14956,"Unexpected test cohort")
    names=set(thresholds)
    require(len(names)==6 and config["anomaly_model_seeds"]==[6007,6017,6027],"Unexpected fixed fits")
    for value in thresholds.values():
        require(value["selected_from"]=="validation" and value["comparison"]=="score >= threshold"
                and math.isfinite(value["threshold"]),"Threshold policy differs")
    conditions=Counter();flags=defaultdict(Counter);cases=set();sources={};clean=set();mh=0
    with (source/"authenticated-test-predictions.jsonl").open(encoding="utf-8") as stream:
        for line in stream:
            row=json.loads(line)
            require(row["case_id"] not in cases,"Duplicate prediction case")
            cases.add(row["case_id"])
            key=(row["attack_type"],row["severity"])
            require(key in wanted and set(row["anomaly"])==names,"Unexpected case or fit")
            conditions[key]+=1
            identity=row["source_window_id"]
            owner=(row["source_trial_id"],row["motion_label"])
            require(sources.setdefault(identity,owner)==owner,"Changed source/trial/label ownership")
            is_clean=key==("clean","clean")
            if is_clean:
                require(identity not in clean,"Duplicated clean source");clean.add(identity)
            is_mh=key[1] in {"medium","high"}
            if is_mh:mh+=1
            for name,value in row["anomaly"].items():
                score=value["score"];flag=value["flag"]
                require(type(score) in (int,float) and math.isfinite(score) and type(flag) is bool
                        and flag==(score>=thresholds[name]["threshold"]),"Score/cutoff/flag mismatch")
                if is_clean:flags[name]["clean_fp"]+=int(flag)
                if is_mh:flags[name]["mh_detected"]+=int(flag)
    require(all(conditions[key]==count for key,count in wanted.items()),"Per-condition accepted counts differ")
    require(len(clean)==600 and set(sources)==clean and mh==9095,"Accepted source cohort does not reconcile")
    planned=sum(v["planned"] for k,v in construction.items() if k.startswith("test:"))
    require(planned==16800,"Unexpected planned test denominator")
    fits=[]
    for name in sorted(names):
        fits.append(dict(detector=name,family=thresholds[name]["kind"],seed=thresholds[name]["seed"],
                         clean_count=600,clean_false_positives=flags[name]["clean_fp"],
                         medium_high_count=mh,medium_high_detected=flags[name]["mh_detected"],
                         medium_high_missed=mh-flags[name]["mh_detected"]))
    expected={}
    with (reference/"family-summary.csv").open(encoding="utf-8",newline="") as stream:
        for row in csv.DictReader(stream):expected[(row["family"],row["metric"])]=float(row["mean_fixed_model_point_estimate"])
    families=[]
    for family in ("logistic_regression","random_forest"):
        selected=[r for r in fits if r["family"]==family]
        require(len(selected)==3,"Missing fixed fit")
        recall=sum(r["medium_high_detected"]/mh for r in selected)/3
        fpr=sum(r["clean_false_positives"]/600 for r in selected)/3
        require(math.isclose(recall,expected[(family,"medium_high_recall")],rel_tol=0,abs_tol=1e-12)
                and math.isclose(fpr,expected[(family,"clean_fpr")],rel_tol=0,abs_tol=1e-12),"Recomputed table differs from retained report")
        families.append(dict(family=family,fixed_fit_count=3,unique_sources=600,
                             medium_high_eligible_per_fit=mh,clean_eligible_per_fit=600,
                             mean_medium_high_recall=recall,mean_clean_false_alert_rate=fpr,
                             recall_target_met=recall>=.9,false_alert_target_met=fpr<=.05))
    return fits,families,verified,dict(planned_test_cases=planned,accepted_test_cases=len(cases),
                                     pre_tag_blocked_test_cases=planned-len(cases),
                                     zero_eligible_conditions=[":".join(key) for key,count in wanted.items() if count==0])

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve()
    output=(args.output if args.output.is_absolute() else root/args.output).resolve()
    require(not output.exists() and output!=root and not root.is_relative_to(output)
            and not output.is_relative_to(root/"results/week-5")
            and not output.is_relative_to(root/"results/week-6"),"Use a new output folder outside historical evidence")
    fits,families,verified,cohort=reproduce(root)
    before=dict(verified)
    require(all(digest(root/name)==value for name,value in before.items()),"An input changed during replay")
    output.mkdir(parents=True,exist_ok=False)
    for name,rows in (("detector-family-table.csv",families),("per-fit-counts.csv",fits)):
        with (output/name).open("x",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)
    receipt=dict(scope="Metric recomputation from retained historical predictions; no model inference or bootstrap rerun.",
                 python=platform.python_version(),system=platform.system(),architecture=platform.machine(),
                 script_sha256=digest(Path(__file__)),verified_input_sha256=verified,
                 verified_input_bytes=sum((root/name).stat().st_size for name in verified),
                 source_files_unchanged=True,accepted_test_cases=14956,unique_sources=600,
                 medium_high_eligible_cases=9095,per_fit_clean_controls=600,
                 matches_retained_family_points=True,independent_person_reproduction_verified=False,
                 model_loading=False,model_inference=False,training=False,threshold_selection=False,
                 bootstrap_intervals_recomputed=False,authentication_reexecuted=False,
                 original_training_split_ownership_reaudited=False,
                 construction_accounting=cohort,
                 output_sha256={p.name:digest(p) for p in sorted(output.glob("*.csv"))})
    with (output/"receipt.json").open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(receipt,stream,indent=2,sort_keys=True);stream.write("\n")
    print(json.dumps(dict(table=families,matches_retained_points=True,input_bytes=receipt["verified_input_bytes"]),indent=2))

if __name__=="__main__":main()
