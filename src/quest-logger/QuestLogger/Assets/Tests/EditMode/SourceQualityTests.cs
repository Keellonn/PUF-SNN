using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;
using UnityEngine.XR;

namespace PufSnn.QuestLogger.Tests {
    public sealed class SourceQualityTests {
        private string root;
        private sealed class MemoryStore : ITrialLedgerStore {
            public readonly List<string> lines = new List<string>();
            public bool fail;
            public void Append(string line) { if (fail) throw new IOException("synthetic source write failure"); lines.Add(line); }
            public void Dispose() { }
        }
        private sealed class FailingFileStore : ITrialLedgerStore {
            private readonly FileTrialLedgerStore inner;
            private int calls;
            public FailingFileStore(string path) { inner = new FileTrialLedgerStore(path); }
            public void Append(string json) { if (++calls == 2) throw new IOException("synthetic source write failure"); inner.Append(json); }
            public void Dispose() { inner.Dispose(); }
        }
        [SetUp] public void SetUp() { root=Path.Combine(Path.GetTempPath(),"puf-snn-source-quality-"+Guid.NewGuid().ToString("N")); Directory.CreateDirectory(root); }
        [TearDown] public void TearDown() {
            string prefix=Path.Combine(Path.GetFullPath(Path.GetTempPath()),"puf-snn-source-quality-");
            Assert.True(Path.GetFullPath(root).StartsWith(prefix,StringComparison.OrdinalIgnoreCase));
            if (Directory.Exists(root)) Directory.Delete(root,true);
        }
        private static LedgerPlan Plan() {
            LedgerPlan p=QuestTrialLedger.BuildPlan("synthetic-person","synthetic-visit","synthetic-device","synthetic-session","synthetic-source-test",1,1,2026);
            p.window_file_name="windows.jsonl"; return p;
        }
        private static RawHeadPoseSample Pose(long time,bool valid=true) {
            return new RawHeadPoseSample {capture_time_ns=time,position_m=Vector3.zero,orientation_xyzw=Quaternion.identity,
                tracking_valid=valid,tracking_flag_available=true,tracking_state_available=true,
                tracking_state=valid ? InputTrackingState.Position | InputTrackingState.Rotation : InputTrackingState.None};
        }
        private static List<RawHeadPoseSample> Source(int count=181) {
            return Enumerable.Range(0,count).Select(i=>Pose((long)Math.Round(i*1_000_000_000.0/90))).ToList();
        }
        private static void Begin(QuestTrialLedger ledger,string id,bool confirm=true) {
            ledger.Record(id,"prompted");ledger.Record(id,"start_requested");if(confirm)ledger.Record(id,"recording_started");
        }
        [Test] public void SourceCadenceIsNotTheResampled120SampleGrid() {
            var raw=Source();var m=SourceQualityMetrics.Measure(raw);
            Assert.AreEqual(181,m.source_sample_count);Assert.AreEqual(90,m.observed_rate_hz,1e-6);
            var meta=new QuestTrialMetadata {device_id="synthetic-device",session_id="synthetic-session",trial_id="trial-0",label="still",split="validation",sequence_number=0};
            Assert.True(QuestWindowProcessor.TryCreateWindow(raw,meta,out var window,out var reason),reason);
            Assert.AreEqual(120,window.samples.Count);
        }
        [Test] public void SourceGapsAndTrackingRemainVisibleBeforeAQualityRejection() {
            var raw=new List<RawHeadPoseSample>{Pose(0),Pose(10_000_000,false),Pose(30_000_000),Pose(90_000_000)};
            raw[1].tracking_flag_available=false;raw[1].tracking_state_available=false;
            var m=SourceQualityMetrics.Measure(raw);
            Assert.AreEqual(1,m.gap_over_50ms_count);Assert.AreEqual(20_000_000,m.median_positive_gap_ns);
            Assert.AreEqual(60_000_000,m.p95_positive_gap_ns);Assert.AreEqual(3,m.tracking_valid_count);
            Assert.AreEqual(1,m.tracking_invalid_count);Assert.AreEqual(3,m.tracking_flag_available_count);
            Assert.AreEqual(100.0/3,m.observed_rate_hz,1e-6);
        }
        [Test] public void Exact50MillisecondGapDoesNotExceedTheLimit() {
            var m=SourceQualityMetrics.Measure(new[]{Pose(0),Pose(50_000_000),Pose(100_000_001)});
            Assert.AreEqual(1,m.gap_over_50ms_count);Assert.AreEqual(50_000_001,m.maximum_positive_gap_ns);
        }
        [Test] public void BackwardAndDuplicateTimestampsHaveNoReportedSamplingRate() {
            var m=SourceQualityMetrics.Measure(new[]{Pose(100),Pose(100),Pose(90),Pose(110)});
            Assert.AreEqual(2,m.nonpositive_interval_count);Assert.AreEqual(1,m.positive_interval_count);
            Assert.AreEqual(-1,m.observed_rate_hz);Assert.AreEqual(-1,m.source_duration_ns);
        }
        [Test] public void EmptySingleSampleAndUnavailableAreDifferent() {
            var empty=SourceQualityMetrics.Measure(new RawHeadPoseSample[0]);
            var single=SourceQualityMetrics.Measure(new[]{Pose(10)});
            var unknown=SourceQualityMetrics.Unavailable("capture_start_unconfirmed");
            Assert.AreEqual("empty",empty.status);Assert.AreEqual(0,empty.source_sample_count);
            Assert.AreEqual("available",single.status);Assert.AreEqual(0,single.source_duration_ns);
            Assert.AreEqual(-1,single.observed_rate_hz);Assert.AreEqual("unavailable",unknown.status);
            Assert.AreEqual(-1,unknown.source_sample_count);
        }
        [Test] public void NonfiniteAndZeroPosesAreCountedWithoutSavingTheirValues() {
            var raw=Source(2);raw[0].position_m=new Vector3(float.NaN,0,0);raw[1].orientation_xyzw=new Quaternion(0,0,0,0);
            var m=SourceQualityMetrics.Measure(raw);
            Assert.AreEqual(1,m.nonfinite_pose_count);Assert.AreEqual(1,m.zero_orientation_count);
            string json=JsonUtility.ToJson(m);Assert.False(json.Contains("position_m"));Assert.False(json.Contains("orientation_xyzw"));Assert.False(json.Contains("NaN"));
        }
        [Test] public void IntervalOverflowIsMeasuredRatherThanWrappingIntoAValidGap() {
            var m=SourceQualityMetrics.Measure(new[]{Pose(long.MinValue),Pose(long.MaxValue)});
            Assert.AreEqual(1,m.interval_overflow_count);Assert.AreEqual(1,m.negative_timestamp_count);
            Assert.AreEqual(-1,m.observed_rate_hz);
        }
        [Test] public void DiagnosticsNeverReorderOrRepairTheSource() {
            var raw=new[]{Pose(90),Pose(10),Pose(100)};var before=raw.Select(s=>s.capture_time_ns).ToArray();
            SourceQualityMetrics.Measure(raw);CollectionAssert.AreEqual(before,raw.Select(s=>s.capture_time_ns).ToArray());
        }
        [Test] public void HeaderAndOneSummaryAreDurableAndDuplicatesAreRefused() {
            string path=Path.Combine(root,"source-quality.jsonl");var p=Plan();
            using(var writer=SourceQualityWriter.Create(path,"ledger.jsonl",p,()=>3_000_000_000)) {
                Assert.AreEqual(1,SharedLines(path).Length);
                writer.Write(p.trials[0].trial_id,"completed","capture_completed",Source());
                Assert.AreEqual(2,SharedLines(path).Length);
                Assert.Throws<ArgumentException>(()=>writer.Write(p.trials[0].trial_id,"completed","capture_completed",Source()));
            }
            Assert.Throws<IOException>(()=>SourceQualityWriter.Create(path,"ledger.jsonl",p,()=>3_000_000_000));
        }
        private static string[] SharedLines(string path) {
            using(var file=new FileStream(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite))
            using(var reader=new StreamReader(file)) return reader.ReadToEnd().Split(new[]{'\n'},StringSplitOptions.RemoveEmptyEntries);
        }
        [Test] public void FailedAppendDoesNotMarkAnAttemptAsSaved() {
            var store=new MemoryStore();var p=Plan();
            using(var writer=new SourceQualityWriter(store,"ledger.jsonl",p,()=>3_000_000_000)) {
                store.fail=true;
                Assert.Throws<IOException>(()=>writer.Write(p.trials[0].trial_id,"completed","capture_completed",Source()));
                Assert.True(writer.Faulted);Assert.False(writer.HasTrial(p.trials[0].trial_id));
                Assert.Throws<InvalidOperationException>(()=>writer.Write(p.trials[0].trial_id,"completed","capture_completed",Source()));
            }
        }
        [Test] public void UnknownCaptureIsExplicitlyUnavailableAndCannotMasqueradeAsEmpty() {
            var store=new MemoryStore();var p=Plan();
            using(var writer=new SourceQualityWriter(store,"ledger.jsonl",p,()=>3_000_000_000)) {
                writer.Write(p.trials[0].trial_id,"unconfirmed","capture_start_unconfirmed",null);
                var row=JsonUtility.FromJson<SourceQualityRow>(store.lines[1]);
                Assert.AreEqual(-1,row.metrics.source_sample_count);Assert.AreEqual("unavailable",row.metrics.status);
                Assert.Throws<ArgumentException>(()=>writer.Write(p.trials[1].trial_id,"stopped","operator_stop",null));
            }
        }
        [TestCase(false)] [TestCase(true)]
        public void ControllerPreservesStoppedSamplesEvenAfterCaptureComponentDisables(bool pause) {
            var p=Plan();string ledgerPath=Path.Combine(root,"ledger.jsonl"),qualityPath=Path.Combine(root,"source-quality.jsonl");
            var ledger=QuestTrialLedger.Create(ledgerPath,p,()=>3_000_000_000);
            var quality=SourceQualityWriter.Create(qualityPath,"ledger.jsonl",p,()=>3_000_000_000);
            Begin(ledger,p.trials[0].trial_id);
            GameObject go=new GameObject("synthetic-source-test");
            try {
                var head=go.AddComponent<HeadPoseCapture>();var controller=go.AddComponent<QuestTrialController>();
                void Set(string field,object value){typeof(QuestTrialController).GetField(field,BindingFlags.Instance|BindingFlags.NonPublic).SetValue(controller,value);}
                Set("headPoseCapture",head);Set("ledger",ledger);Set("sourceQuality",quality);Set("plan",p);
                Set("activeTrialId",p.trials[0].trial_id);Set("capturePending",true);
                head.BeginCapture();var buffer=(RawPoseBuffer)typeof(HeadPoseCapture).GetField("sampleBuffer",BindingFlags.Instance|BindingFlags.NonPublic).GetValue(head);
                foreach(var sample in Source(4))buffer.Enqueue(sample);
                typeof(HeadPoseCapture).GetMethod("OnDisable",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(head,null);
                Assert.False(head.CaptureActive);
                if(pause)typeof(QuestTrialController).GetMethod("OnApplicationPause",BindingFlags.Instance|BindingFlags.NonPublic).Invoke(controller,new object[]{true});
                else controller.StopTrialSession();
                var row=JsonUtility.FromJson<SourceQualityRow>(File.ReadAllLines(qualityPath)[1]);
                Assert.AreEqual(4,row.metrics.source_sample_count);Assert.AreEqual("stopped",row.source_stage);
                Assert.AreEqual("stopped",ledger.Stage(p.trials[0].trial_id));Assert.True(ledger.Closed);
            } finally {UnityEngine.Object.DestroyImmediate(go);ledger.Dispose();quality.Dispose();}
        }
        [Test] public void ExportMixedNativeSourceFixtureForPythonReconciliation() {
            var p=Plan();string ledgerPath=Path.Combine(root,"ledger.jsonl"),qualityPath=Path.Combine(root,"source-quality.jsonl");
            using(var ledger=QuestTrialLedger.Create(ledgerPath,p,()=>3_000_000_000))
            using(var quality=SourceQualityWriter.Create(qualityPath,"ledger.jsonl",p,()=>3_000_000_000)) {
                var raw=Source();string id=p.trials[0].trial_id;Begin(ledger,id);
                quality.Write(id,"completed","capture_completed",raw);ledger.Record(id,"completed",rawSampleCount:raw.Count);
                var meta=new QuestTrialMetadata{device_id=p.device_id,session_id=p.session_id,trial_id=id,label=p.trials[0].prompted_task,split="validation",sequence_number=0};
                Assert.True(QuestWindowProcessor.TryCreateWindow(raw,meta,out var window,out var reason),reason);
                ledger.Record(id,"accepted",receipt:QuestWindowWriter.AppendWindowWithReceipt(Path.Combine(root,"windows.jsonl"),window));
                id=p.trials[1].trial_id;Begin(ledger,id);raw=new List<RawHeadPoseSample>{Pose(0),Pose(10_000_000),Pose(100_000_000,false)};
                quality.Write(id,"completed","capture_completed",raw);ledger.Record(id,"completed",rawSampleCount:raw.Count);
                Assert.False(QuestWindowProcessor.TryCreateWindow(raw,meta,out _,out reason));
                ledger.Record(id,"rejected","source_gap_over_limit");
                id=p.trials[2].trial_id;Begin(ledger,id);quality.Write(id,"stopped","operator_stop",Source(13));ledger.Record(id,"stopped","operator_stop");
                id=p.trials[3].trial_id;Begin(ledger,id,false);quality.Write(id,"unconfirmed","capture_start_unconfirmed",null);
                ledger.EndVisit("operator_stop");
            }
            Export(root,"");
        }
        [Test] public void ExportFailedSourceWriteWithoutInventingAQualityRejection() {
            var p=Plan();string folder=Path.Combine(root,"source-write-failed");Directory.CreateDirectory(folder);
            using(var ledger=QuestTrialLedger.Create(Path.Combine(folder,"ledger.jsonl"),p,()=>3_000_000_000))
            using(var quality=new SourceQualityWriter(new FailingFileStore(Path.Combine(folder,"source-quality.jsonl")),"ledger.jsonl",p,()=>3_000_000_000)) {
                string id=p.trials[0].trial_id;Begin(ledger,id);ledger.Record(id,"completed",rawSampleCount:181);
                Assert.Throws<IOException>(()=>quality.Write(id,"completed","capture_completed",Source()));
                ledger.Record(id,"processing_failed","source_quality_write_failed");ledger.EndVisit("source_quality_write_failed");
            }
            Export(folder,"source-write-failed");
        }
        private static void Export(string folder,string child) {
            string export=Environment.GetEnvironmentVariable("PUF_SNN_SOURCE_FIXTURE_ROOT");
            if(string.IsNullOrWhiteSpace(export)) {
                string[] args=Environment.GetCommandLineArgs();
                int i=Array.IndexOf(args,"-pufSourceFixtureRoot");
                if(i>=0 && i+1<args.Length) export=args[i+1];
            }
            if(string.IsNullOrWhiteSpace(export))return;
            string target=string.IsNullOrEmpty(child)?export:Path.Combine(export,child);
            Directory.CreateDirectory(target);
            foreach(string name in new[]{"ledger.jsonl","source-quality.jsonl","windows.jsonl"})
                if(File.Exists(Path.Combine(folder,name)))File.Copy(Path.Combine(folder,name),Path.Combine(target,name),false);
        }
    }
}
