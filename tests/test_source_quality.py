"""Diagnostic accounting with artificial ledger/summary files, no headset or models."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from puf_snn.source_quality import inspect_source_quality, COUNTS, TIMES


class SourceQualityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="puf-snn-source-python-")
        self.root=Path(self.temp.name);self.ledger=self.root/"ledger.jsonl";self.source=self.root/"source-quality.jsonl"
        self.plan=dict(record_type="plan",schema_version="quest-trial-ledger-v1",participant_code="synthetic-person",
                       visit_code="synthetic-visit",device_id="synthetic-device",session_id="synthetic-session",
                       processing_version="synthetic-source-test",window_file_name="windows.jsonl",
                       time_basis="head-capture-stopwatch-ns",raw_retention="not_saved",repeat_policy="none",
                       schedule_seed=2026,maximum_trials=75,created_elapsed_ns=0,
                       trials=[dict(trial_id=f"trial-{i}",trial_index=i,block_index=1,prompted_task=label,repeat_of_trial_id="")
                               for i,label in enumerate(("nod","shake","look_left_return","look_right_return","still"))])
        self.events=[]
        self.header=dict(record_type="source_quality_plan",schema_version="quest-source-quality-v1",
                         **{k:self.plan[k] for k in ("participant_code","visit_code","device_id","session_id","processing_version","time_basis","raw_retention")},
                         ledger_file_name="ledger.jsonl",interval_quantile_method="nearest_rank",gap_limit_ns=50_000_000)
        self.metrics=dict(status="available",unavailable_reason="",source_sample_count=4,first_capture_ns=0,
                          last_capture_ns=90_000_000,source_duration_ns=90_000_000,observed_rate_hz=100/3,
                          tracking_valid_count=3,tracking_invalid_count=1,tracking_flag_available_count=3,
                          tracking_state_available_count=3,positive_interval_count=3,nonpositive_interval_count=0,
                          interval_overflow_count=0,negative_timestamp_count=0,gap_over_50ms_count=1,
                          maximum_positive_gap_ns=60_000_000,median_positive_gap_ns=20_000_000,p95_positive_gap_ns=60_000_000,
                          nonfinite_pose_count=0,zero_orientation_count=0)
        self.row=dict(record_type="source_quality",summary_index=1,elapsed_ns=100_000_000,trial_id="trial-0",
                      source_stage="completed",reason_code="capture_completed",metrics=self.metrics)
        self.rows=[self.row]

    def tearDown(self):self.temp.cleanup()

    def event(self,kind,identity="trial-0",reason="",raw=-1):
        self.events.append(dict(record_type="event",event_index=len(self.events)+1,event_type=kind,elapsed_ns=100_000_000,
                                trial_id=identity,reason_code=reason,raw_sample_count=raw,window_id="",file_name="",
                                line_sha256="",file_offset=-1,line_length=0))

    def finish(self,mode="rejected",raw=4):
        self.events=[]
        for kind in ("prompted","start_requested"):self.event(kind)
        if mode!="unconfirmed":self.event("recording_started")
        if mode in {"stopped","unconfirmed"}:self.event("stopped",reason="operator_stop")
        else:
            self.event("completed",raw=raw)
            self.event("rejected" if mode=="rejected" else "processing_failed",reason="source_gap_over_limit" if mode=="rejected" else "source_quality_write_failed")
        for i in range(1,5):self.event("not_attempted",f"trial-{i}","operator_stop")
        self.event("visit_closed","","operator_stop")
        self.ledger.write_text("".join(json.dumps(v)+"\n" for v in [self.plan,*self.events]),encoding="utf-8")

    def check(self,tail=b""):
        self.source.write_bytes("".join(json.dumps(v)+"\n" for v in [self.header,*self.rows]).encode()+tail)
        return inspect_source_quality(self.ledger,self.source)

    def test_rejected_source_metrics_remain_eligible_for_accounting(self):
        self.finish();r=self.check()
        self.assertEqual(r["status"],"COMPLETE",r["issues"])
        self.assertEqual(r["counts"],dict(attempted=1,summaries=1,missing=0,measured=1,empty=0,unavailable=0))
        self.assertEqual(r["summaries"][0]["metrics"]["gap_over_50ms_count"],1)

    def test_stopped_capture_is_measured_without_becoming_a_completed_window(self):
        self.finish("stopped");self.row.update(source_stage="stopped",reason_code="operator_stop")
        self.assertEqual(self.check()["status"],"COMPLETE")

    def test_unconfirmed_capture_has_unknown_counts_not_zero(self):
        self.finish("unconfirmed")
        self.row.update(source_stage="unconfirmed",reason_code="capture_start_unconfirmed",
                        metrics=dict(status="unavailable",unavailable_reason="capture_start_unconfirmed",observed_rate_hz=-1,
                                     **{k:-1 for k in COUNTS|TIMES}))
        self.assertEqual(self.check()["counts"]["unavailable"],1)
        self.row["metrics"]["source_sample_count"]=0
        self.assertIn("unavailable_is_not_zero_samples",self.check()["issues"])

    def test_measured_empty_capture_is_distinct_from_unavailable(self):
        self.finish(raw=0)
        self.row["metrics"]=dict(status="empty",unavailable_reason="",observed_rate_hz=-1,
                                 **{k:0 for k in COUNTS},**{k:-1 for k in TIMES})
        r=self.check();self.assertEqual(r["status"],"COMPLETE",r["issues"]);self.assertEqual(r["counts"]["empty"],1)

    def test_missing_summary_is_not_a_passing_zero_attempt_visit(self):
        self.finish("processing_failed");self.rows=[]
        r=self.check();self.assertEqual(r["status"],"INVALID");self.assertEqual(r["counts"]["attempted"],1)
        self.assertEqual(r["missing_trial_summaries"],["trial-0"])

    def test_duplicate_summary_is_refused(self):
        self.finish();duplicate=copy.deepcopy(self.row);duplicate["summary_index"]=2;self.rows.append(duplicate)
        self.assertIn("unknown_unattempted_or_duplicate_summary",self.check()["issues"])

    def test_source_and_completion_counts_must_match(self):
        self.finish(raw=5)
        self.assertIn("source_count_differs_from_completion",self.check()["issues"])

    def test_invalid_time_order_has_no_invented_rate(self):
        self.finish();self.metrics.update(positive_interval_count=2,nonpositive_interval_count=1,source_duration_ns=-1,observed_rate_hz=-1)
        self.assertEqual(self.check()["status"],"COMPLETE")
        self.metrics["observed_rate_hz"]=30
        self.assertIn("invalid_clock_has_no_sampling_rate",self.check()["issues"])

    def test_sampling_rate_and_tracking_partition_are_checked(self):
        self.finish();self.metrics["observed_rate_hz"]+=1
        self.assertIn("source_rate_mismatch",self.check()["issues"])
        self.metrics["observed_rate_hz"]=100/3;self.metrics["tracking_valid_count"]=4
        self.assertIn("tracking_counts_do_not_partition",self.check()["issues"])

    def test_malformed_values_do_not_crash_or_pass(self):
        self.finish()
        for field,value in (("source_sample_count",True),("observed_rate_hz",float("nan")),("observed_rate_hz",10**500)):
            with self.subTest(field=field,value_type=type(value).__name__):
                original=self.metrics[field];self.metrics[field]=value
                self.assertEqual(self.check()["status"],"INVALID")
                self.metrics[field]=original
        self.row["source_stage"]=["completed"]
        self.assertEqual(self.check()["status"],"INVALID")

    def test_identity_and_file_reference_must_match(self):
        self.finish();self.header["visit_code"]="other-visit"
        self.assertIn("source_identity_mismatch",self.check()["issues"])
        self.header["visit_code"]=self.plan["visit_code"];self.header["ledger_file_name"]="other.jsonl"
        self.assertIn("source_policy_mismatch",self.check()["issues"])

    def test_unattempted_trials_cannot_have_source_summaries(self):
        self.finish();self.row["trial_id"]="trial-1"
        self.assertIn("unknown_unattempted_or_duplicate_summary",self.check()["issues"])

    def test_torn_source_record_is_reported_without_repair(self):
        self.finish();self.rows=[]
        r=self.check(b'{"record_type":"source_quality"');before=self.source.read_bytes()
        self.assertEqual(r["status"],"INVALID");self.assertIn("oversized_or_torn_source_record",r["issues"])
        inspect_source_quality(self.ledger,self.source)
        self.assertEqual(self.source.read_bytes(),before)

    def test_raw_pose_fields_are_not_part_of_the_summary_schema(self):
        self.finish();self.metrics["position_m"]=[1,2,3]
        self.assertIn("invalid_metric_fields",self.check()["issues"])

    def test_other_directory_is_refused(self):
        self.finish();self.check()
        other=self.root/"other";other.mkdir();p=other/"source-quality.jsonl";p.write_bytes(self.source.read_bytes())
        self.assertIn("source_file_outside_visit_directory",inspect_source_quality(self.ledger,p)["issues"])

if __name__=="__main__":unittest.main()
