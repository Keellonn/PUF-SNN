using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.XR;

namespace PufSnn.QuestLogger.Tests {
    public sealed class AcceptedSourceVisitTests {
        private string root;
        private sealed class FailingStore : ITrialLedgerStore {
            private readonly FileTrialLedgerStore inner;
            private readonly string failType;
            public FailingStore(string path, string failType) { inner = new FileTrialLedgerStore(path); this.failType = failType; }
            public void Append(string json) {
                if (json.Contains("\"" + failType + "\"")) throw new IOException("injected durable append failure");
                inner.Append(json);
            }
            public void Dispose() { inner.Dispose(); }
        }
        private sealed class PartialSource : IAcceptedSourceFileStore {
            private readonly string directory;
            public PartialSource(string directory) { this.directory = directory; }
            public void WriteNew(string name, byte[] bytes) {
                using (var f = new FileStream(Path.Combine(directory, name), FileMode.CreateNew)) { f.Write(bytes, 0, 40); f.Flush(true); }
                throw new IOException("injected partial source write");
            }
        }
        [SetUp] public void Setup() {
            root = Path.Combine(Path.GetTempPath(), "puf-snn-source-visit-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
        }
        [TearDown] public void Cleanup() {
            Assert.True(Path.GetFullPath(root).StartsWith(Path.Combine(Path.GetFullPath(Path.GetTempPath()), "puf-snn-source-visit-"), StringComparison.OrdinalIgnoreCase));
            Directory.Delete(root, true);
        }
        private static LedgerPlan Plan(bool retained = true) {
            var p = QuestTrialLedger.BuildPlan("synthetic-person", "synthetic-visit", "synthetic-device", "synthetic-session", "synthetic-integration-20261103", 1, 1, 2026);
            p.window_file_name = "windows.jsonl";
            if (retained) AcceptedSourceVisit.DeclareDevelopmentPolicy(p);
            return p;
        }
        private static List<RawHeadPoseSample> Raw() => Enumerable.Range(0, 181).Select(i => new RawHeadPoseSample {
            capture_time_ns = (long)Math.Round(i * 1_000_000_000.0 / 90), position_m = new Vector3(i * .001f, 0, 0),
            orientation_xyzw = Quaternion.Euler(i * .03f, 0, 0), tracking_valid = true,
            tracking_state = InputTrackingState.Position | InputTrackingState.Rotation,
            tracking_flag_available = true, tracking_state_available = true
        }).ToList();
        private static QuestTrialMetadata Metadata(LedgerPlan p, int index = 0) => new QuestTrialMetadata {
            device_id = p.device_id, session_id = p.session_id, trial_id = p.trials[index].trial_id,
            label = p.trials[index].prompted_task, split = "validation", sequence_number = index
        };
        private static void Begin(QuestTrialLedger l, string id) { l.Record(id, "prompted"); l.Record(id, "start_requested"); l.Record(id, "recording_started"); }
        private static void Complete(QuestTrialLedger l, string id, int count = 181) { Begin(l, id); l.Record(id, "completed", rawSampleCount: count); }
        private static QuestWindowRecord Window(List<RawHeadPoseSample> raw, QuestTrialMetadata m) {
            Assert.True(QuestWindowProcessor.TryCreateWindow(raw, m, out var w, out var reason), reason); return w;
        }
        private string DirectoryPath => Path.Combine(root, "synthetic-visit-accepted-source");
        private string ManifestPath => Path.Combine(root, "synthetic-visit-accepted-source.jsonl");
        private Func<QuestWindowRecord, WindowWriteReceipt> Writer => w => QuestWindowWriter.AppendWindowWithReceipt(Path.Combine(root, "windows.jsonl"), w);

        [Test] public void LegacyPolicyRemainsTheDefaultAndMismatchedPoliciesAreRefused() {
            var p = Plan(false); Assert.AreEqual("not_saved", p.raw_retention);
            p.raw_retention = AcceptedSourceVisit.Policy; Assert.Throws<ArgumentException>(() => QuestTrialLedger.ValidatePlan(p));
            p = Plan(); p.raw_retention = "not_saved"; Assert.Throws<ArgumentException>(() => QuestTrialLedger.ValidatePlan(p));
            var go = new GameObject("synthetic-controller");
            try { Assert.False(go.AddComponent<QuestTrialController>().RetainsAcceptedSource); }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        [Test] public void RetainedVisitDeclaresItsPolicyInBothHeaders() {
            var p = Plan();
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var q = SourceQualityWriter.Create(Path.Combine(root, "quality.jsonl"), "ledger.jsonl", p, () => 3_000_000_000)) { }
            Assert.True(File.ReadAllText(Path.Combine(root, "ledger.jsonl")).Contains("quest-trial-ledger-v2"));
            string json = File.ReadAllText(Path.Combine(root, "quality.jsonl"));
            Assert.True(json.Contains("quest-source-quality-v2")); Assert.True(json.Contains(AcceptedSourceVisit.Policy));
        }
        [Test] public void AcceptanceSavesExactReplayAndDurableReceipt() {
            var p = Plan(); var raw = Raw(); var meta = Metadata(p); var w = Window(raw, meta);
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                Complete(l, meta.trial_id); s.Accept(raw, meta, w, Writer); l.EndVisit("schedule_finished"); s.Close();
            }
            string source = File.ReadAllText(Path.Combine(DirectoryPath, meta.trial_id + ".json"));
            Assert.True(source.Contains("quest-accepted-source-v2"));
            Assert.AreEqual(QuestWindowWriter.SerializeWindow(w), QuestWindowWriter.SerializeWindow(AcceptedSourceCandidate.Replay(source, out var metrics)));
            Assert.AreEqual(181, metrics.source_sample_count);
            Assert.AreEqual(3, File.ReadAllLines(ManifestPath).Length);
            Assert.Throws<IOException>(() => AcceptedSourceVisit.Preflight(root, Plan(false)));
        }
        [TestCase("rejected")] [TestCase("stopped")] [TestCase("skipped")]
        public void NonacceptedTrialsNeverSaveSource(string state) {
            var p = Plan(); var raw = Raw(); var meta = Metadata(p); var w = Window(raw, meta);
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                if (state == "rejected") { Complete(l, meta.trial_id); l.Record(meta.trial_id, state, "tracking_coverage"); }
                else if (state == "stopped") { Begin(l, meta.trial_id); l.Record(meta.trial_id, state, "operator_stop"); }
                else l.Record(meta.trial_id, state, "participant_skip");
                Assert.Throws<InvalidDataException>(() => s.Accept(raw, meta, w, Writer));
                Assert.AreEqual(0, Directory.GetFiles(DirectoryPath).Length);
                Assert.False(File.Exists(Path.Combine(root, "windows.jsonl")));
            }
        }
        [Test] public void WindowWriteFailureSavesNeitherSourceNorAcceptance() {
            var p = Plan(); var raw = Raw(); var m = Metadata(p);
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                Complete(l, m.trial_id);
                Assert.Throws<IOException>(() => s.Accept(raw, m, Window(raw, m), _ => throw new IOException("injected window write")));
                Assert.AreEqual("completed", l.Stage(m.trial_id)); Assert.AreEqual(0, Directory.GetFiles(DirectoryPath).Length);
            }
        }
        [Test] public void AcceptanceAppendFailureLeavesWindowOrphanButNoSource() {
            var p = Plan(); var raw = Raw(); var m = Metadata(p);
            using (var l = new QuestTrialLedger(new FailingStore(Path.Combine(root, "ledger.jsonl"), "accepted"), p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                Complete(l, m.trial_id); Assert.Throws<IOException>(() => s.Accept(raw, m, Window(raw, m), Writer));
                Assert.True(l.Faulted); Assert.AreEqual("completed", l.Stage(m.trial_id));
                Assert.True(File.Exists(Path.Combine(root, "windows.jsonl"))); Assert.AreEqual(0, Directory.GetFiles(DirectoryPath).Length);
                Assert.Throws<InvalidOperationException>(() => s.Close());
            }
        }
        [TestCase("partial_source")] [TestCase("manifest_receipt")]
        public void InterruptedSourceWritesRemainIncompleteAndAreNeverOverwritten(string failure) {
            var p = Plan(); var raw = Raw(); var m = Metadata(p); Directory.CreateDirectory(DirectoryPath);
            ITrialLedgerStore manifest = failure == "manifest_receipt" ? new FailingStore(ManifestPath, "accepted_source") : new FileTrialLedgerStore(ManifestPath);
            IAcceptedSourceFileStore files = failure == "partial_source" ? new PartialSource(DirectoryPath) : new AcceptedSourceFileStore(DirectoryPath);
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var s = new AcceptedSourceVisit(manifest, files, "ledger.jsonl", p, l)) {
                Complete(l, m.trial_id); Assert.Throws<IOException>(() => s.Accept(raw, m, Window(raw, m), Writer));
                Assert.AreEqual("accepted", l.Stage(m.trial_id)); Assert.True(s.Faulted);
                Assert.AreEqual(1, Directory.GetFiles(DirectoryPath).Length);
                l.EndVisit("source_write_failed"); Assert.Throws<InvalidOperationException>(() => s.Close());
            }
            Assert.AreEqual(1, File.ReadAllLines(ManifestPath).Length);
            Assert.Throws<IOException>(() => AcceptedSourceVisit.Preflight(root, p));
        }
        [Test] public void CloseRequiresTheLedgerToCloseAndDisposeDoesNotInventCompletion() {
            var p = Plan();
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) Assert.Throws<InvalidDataException>(() => s.Close());
            Assert.AreEqual(1, File.ReadAllLines(ManifestPath).Length);
        }
        [Test] public void SourceVersionAndMetadataCannotChangeMidVisit() {
            var p = Plan(); var raw = Raw(); var m = Metadata(p);
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                Complete(l, m.trial_id); m.device_id = "another-device";
                Assert.Throws<InvalidDataException>(() => s.Accept(raw, m, Window(raw, m), Writer));
                Assert.AreEqual(0, Directory.GetFiles(DirectoryPath).Length);
            }
        }
        [Test] public void ControllerCallsIntegratedWriterAndRefusesPolicyChangeDuringVisit() {
            var p = Plan(); var raw = Raw(); var go = new GameObject("synthetic-controller");
            try {
                var controller = go.AddComponent<QuestTrialController>(); var writer = go.AddComponent<QuestWindowWriter>();
                Set(writer, "outputFolderName", root); Set(writer, "outputFileName", "windows.jsonl");
                using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
                using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                    Complete(l, p.trials[0].trial_id);
                    Set(controller, "ledger", l); Set(controller, "acceptedSource", s); Set(controller, "windowWriter", writer);
                    Set(controller, "deviceId", p.device_id); Set(controller, "sessionId", p.session_id); Set(controller, "split", "validation");
                    Assert.Throws<InvalidOperationException>(() => controller.SetDevelopmentSourceRetention(true));
                    var method = typeof(QuestTrialController).GetMethod("ProcessAndSave", BindingFlags.NonPublic | BindingFlags.Instance);
                    Assert.True((bool)method.Invoke(controller, new object[] {p.trials[0], raw}));
                    Assert.AreEqual("accepted", l.Stage(p.trials[0].trial_id));
                    Set(controller, "ledger", null); Set(controller, "acceptedSource", null);
                    l.EndVisit("schedule_finished"); s.Close();
                }
            } finally { UnityEngine.Object.DestroyImmediate(go); }
        }
        private static void Set(object obj, string name, object value) => obj.GetType().GetField(name, BindingFlags.NonPublic | BindingFlags.Instance).SetValue(obj, value);

        [Test] public void ExportSyntheticVisitForIndependentInspection() {
            var p = Plan(); var raw = Raw(); var m = Metadata(p);
            using (var l = QuestTrialLedger.Create(Path.Combine(root, "ledger.jsonl"), p, () => 3_000_000_000))
            using (var q = SourceQualityWriter.Create(Path.Combine(root, "synthetic-visit-source-quality.jsonl"), "ledger.jsonl", p, () => 3_000_000_000))
            using (var s = AcceptedSourceVisit.Create(root, "ledger.jsonl", p, l)) {
                Complete(l, m.trial_id); q.Write(m.trial_id, "completed", "capture_completed", raw); s.Accept(raw, m, Window(raw, m), Writer);
                var rejected = p.trials[1].trial_id; Complete(l, rejected, 0); q.Write(rejected, "completed", "capture_completed", new List<RawHeadPoseSample>()); l.Record(rejected, "rejected", "too_few_source_samples");
                var stopped = p.trials[2].trial_id; Begin(l, stopped); q.Write(stopped, "stopped", "operator_stop", raw.Take(3).ToList()); l.Record(stopped, "stopped", "operator_stop");
                l.Record(p.trials[3].trial_id, "skipped", "participant_skip"); l.EndVisit("schedule_finished"); s.Close();
            }
            string[] args = Environment.GetCommandLineArgs(); int index = Array.IndexOf(args, "-pufAcceptedSourceVisitFixtureRoot");
            if (index >= 0 && index + 1 < args.Length) {
                string target = args[index + 1]; Assert.False(Directory.Exists(target)); Directory.CreateDirectory(target);
                foreach (string f in Directory.GetFiles(root)) File.Copy(f, Path.Combine(target, Path.GetFileName(f)));
                string dest = Path.Combine(target, Path.GetFileName(DirectoryPath)); Directory.CreateDirectory(dest);
                foreach (string f in Directory.GetFiles(DirectoryPath)) File.Copy(f, Path.Combine(dest, Path.GetFileName(f)));
            }
        }
    }
}
