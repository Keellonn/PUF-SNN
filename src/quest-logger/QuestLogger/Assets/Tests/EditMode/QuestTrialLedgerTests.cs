using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace PufSnn.QuestLogger.Tests {
    public sealed class QuestTrialLedgerTests {
        private string root;

        private sealed class MemoryStore : ITrialLedgerStore {
            public readonly List<string> lines = new List<string>();
            public int failAt = -1;
            private int calls;
            public bool disposed;
            public void Append(string json) {
                calls++;
                if (calls == failAt) throw new IOException("synthetic append failure");
                lines.Add(json);
            }
            public void Dispose() { disposed = true; }
        }

        private sealed class AcceptanceFailingFileStore : ITrialLedgerStore {
            private readonly FileTrialLedgerStore inner;
            public AcceptanceFailingFileStore(string path) { inner = new FileTrialLedgerStore(path); }
            public void Append(string json) {
                if (JsonUtility.FromJson<LedgerEvent>(json).event_type == "accepted")
                    throw new IOException("synthetic failure after the window was saved");
                inner.Append(json);
            }
            public void Dispose() { inner.Dispose(); }
        }

        [SetUp]
        public void SetUp() {
            root = Path.Combine(Path.GetTempPath(), "puf-snn-ledger-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
        }

        [TearDown]
        public void TearDown() {
            string prefix = Path.Combine(Path.GetFullPath(Path.GetTempPath()), "puf-snn-ledger-test-");
            if (Path.GetFullPath(root).StartsWith(prefix, StringComparison.OrdinalIgnoreCase) && Directory.Exists(root))
                Directory.Delete(root, true);
        }

        private static LedgerPlan Plan(int blocks = 1, int perClass = 1) {
            LedgerPlan plan = QuestTrialLedger.BuildPlan("synthetic-person", "synthetic-visit", "synthetic-device",
                "synthetic-session", "synthetic-unit-test-build", blocks, perClass, 2026);
            plan.window_file_name = "windows.jsonl";
            return plan;
        }

        private static void Begin(QuestTrialLedger ledger, string id) {
            ledger.Record(id, "prompted");
            ledger.Record(id, "start_requested");
            ledger.Record(id, "recording_started");
        }

        [Test]
        public void ThreeBlocksAreBalancedBoundedAndSeeded() {
            LedgerPlan plan = Plan(3, 5);
            Assert.AreEqual(75, plan.trials.Count);
            CollectionAssert.AreEqual(plan.trials.Select(t => t.prompted_task), Plan(3, 5).trials.Select(t => t.prompted_task));
            foreach (var block in plan.trials.GroupBy(t => t.block_index)) {
                Assert.AreEqual(25, block.Count());
                foreach (string label in QuestTrialLedger.Labels) Assert.AreEqual(5, block.Count(t => t.prompted_task == label));
            }
            Assert.AreEqual(75, plan.trials.Select(t => t.trial_id).Distinct().Count());
            Assert.Throws<ArgumentException>(() => Plan(4, 5));
        }

        [Test]
        public void InvalidPlansAndUnreviewedRepeatsAreRefused() {
            LedgerPlan plan = Plan(); plan.processing_version = "";
            Assert.Throws<ArgumentException>(() => QuestTrialLedger.ValidatePlan(plan));
            plan = Plan(); plan.visit_code = "../outside";
            Assert.Throws<ArgumentException>(() => QuestTrialLedger.ValidatePlan(plan));
            plan = Plan(); plan.trials[1].trial_id = plan.trials[0].trial_id;
            Assert.Throws<ArgumentException>(() => QuestTrialLedger.ValidatePlan(plan));
            plan = Plan(); plan.trials[1].repeat_of_trial_id = plan.trials[0].trial_id;
            Assert.Throws<ArgumentException>(() => QuestTrialLedger.ValidatePlan(plan));
        }

        [Test]
        public void EntirePlanIsReadableBeforeFirstTrialAndCallerMutationDoesNotChangeIt() {
            string path = Path.Combine(root, "ledger.jsonl");
            LedgerPlan plan = Plan();
            using (QuestTrialLedger ledger = QuestTrialLedger.Create(path, plan, () => 10)) {
                plan.trials.Clear();
                using (FileStream stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (StreamReader reader = new StreamReader(stream)) {
                    LedgerPlan saved = JsonUtility.FromJson<LedgerPlan>(reader.ReadLine());
                    Assert.AreEqual(5, saved.trials.Count);
                    Assert.AreEqual("not_saved", saved.raw_retention);
                    Assert.IsNull(reader.ReadLine());
                }
            }
        }

        [Test]
        public void CompletedQualityRejectionHasNoWindowReferenceAndIsNotAStop() {
            MemoryStore store = new MemoryStore(); LedgerPlan plan = Plan(); string id = plan.trials[0].trial_id;
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => 10)) {
                Begin(ledger, id); ledger.Record(id, "completed", rawSampleCount: 0);
                ledger.Record(id, "rejected", "too_few_source_samples"); ledger.EndVisit("schedule_finished");
                Assert.IsTrue(ledger.Closed);
            }
            var events = store.lines.Skip(1).Select(JsonUtility.FromJson<LedgerEvent>).ToList();
            Assert.AreEqual(1, events.Count(e => e.event_type == "completed"));
            Assert.AreEqual(1, events.Count(e => e.event_type == "rejected"));
            Assert.AreEqual(0, events.Count(e => e.event_type == "stopped"));
            LedgerEvent rejection = events.Single(e => e.event_type == "rejected");
            Assert.IsTrue(string.IsNullOrEmpty(rejection.file_name));
            Assert.AreEqual(-1, rejection.file_offset);
        }

        [Test]
        public void StopAccountsForStartedAndUnstartedTrials() {
            LedgerPlan plan = Plan(); MemoryStore store = new MemoryStore();
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => 10)) {
                ledger.Record(plan.trials[0].trial_id, "skipped", "participant_skip");
                Begin(ledger, plan.trials[1].trial_id);
                ledger.EndVisit("operator_stop");
            }
            var events = store.lines.Skip(1).Select(JsonUtility.FromJson<LedgerEvent>).ToList();
            Assert.AreEqual(1, events.Count(e => e.event_type == "skipped"));
            Assert.AreEqual(1, events.Count(e => e.event_type == "stopped"));
            Assert.AreEqual(3, events.Count(e => e.event_type == "not_attempted"));
            Assert.AreEqual("visit_closed", events.Last().event_type);
        }

        [Test]
        public void DisposingAnInterruptedLedgerDoesNotInventCompletionOrResume() {
            string path = Path.Combine(root, "ledger.jsonl"); LedgerPlan plan = Plan();
            using (QuestTrialLedger ledger = QuestTrialLedger.Create(path, plan, () => 10)) {
                ledger.Record(plan.trials[0].trial_id, "prompted");
                ledger.Record(plan.trials[0].trial_id, "start_requested");
            }
            byte[] before = File.ReadAllBytes(path);
            Assert.IsFalse(File.ReadAllText(path).Contains("recording_started"));
            Assert.IsFalse(File.ReadAllText(path).Contains("visit_closed"));
            Assert.Throws<IOException>(() => QuestTrialLedger.Create(path, plan, () => 10));
            CollectionAssert.AreEqual(before, File.ReadAllBytes(path));
        }

        [Test]
        public void AppendFailurePoisonsLedgerBeforeStateOrCaptureCanAdvance() {
            MemoryStore store = new MemoryStore { failAt = 2 }; LedgerPlan plan = Plan();
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => 10)) {
                Assert.Throws<IOException>(() => ledger.Record(plan.trials[0].trial_id, "prompted"));
                Assert.IsTrue(ledger.Faulted);
                Assert.AreEqual("scheduled", ledger.Stage(plan.trials[0].trial_id));
                Assert.Throws<InvalidOperationException>(() => ledger.EndVisit("operator_stop"));
                Assert.AreEqual(1, store.lines.Count);
            }
        }

        [Test]
        public void PlanFailureDisposesTheWriterAndCreatesNoUsableLedger() {
            MemoryStore store = new MemoryStore { failAt = 1 };
            Assert.Throws<IOException>(() => new QuestTrialLedger(store, Plan(), () => 10));
            Assert.IsTrue(store.disposed);
            Assert.IsEmpty(store.lines);
        }

        [Test]
        public void InvalidTransitionsAndBackwardClockDoNotAppend() {
            MemoryStore store = new MemoryStore(); long now = 10; LedgerPlan plan = Plan(); string id = plan.trials[0].trial_id;
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => now)) {
                Assert.Throws<InvalidOperationException>(() => ledger.Record(id, "accepted"));
                now = 9;
                Assert.Throws<InvalidOperationException>(() => ledger.Record(id, "prompted"));
                Assert.AreEqual(1, store.lines.Count);
                now = 11; Begin(ledger, id); ledger.Record(id, "completed", rawSampleCount: 120);
                Assert.Throws<ArgumentException>(() => ledger.Record(id, "accepted"));
                Assert.Throws<ArgumentException>(() => ledger.Record(id, "rejected", "private free text"));
            }
        }

        [Test]
        public void AnotherTrialCannotStartWhileTheFirstIsUnresolved() {
            LedgerPlan plan = Plan(); MemoryStore store = new MemoryStore();
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => 10)) {
                Begin(ledger, plan.trials[0].trial_id);
                Assert.Throws<InvalidOperationException>(() => ledger.Record(plan.trials[1].trial_id, "prompted"));
                ledger.EndVisit("operator_stop");
                Assert.IsTrue(ledger.Closed);
            }
        }

        [Test]
        public void UnsafeReceiptCannotTurnACompletedTrialIntoAnAcceptance() {
            LedgerPlan plan = Plan(); MemoryStore store = new MemoryStore(); string id = plan.trials[0].trial_id;
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => 10)) {
                Begin(ledger, id); ledger.Record(id, "completed", rawSampleCount: 120);
                WindowWriteReceipt receipt = new WindowWriteReceipt {
                    file_name = "../outside.jsonl", window_id = "some-window", line_sha256 = new string('a', 64), file_offset = 0, line_length = 2
                };
                Assert.Throws<ArgumentException>(() => ledger.Record(id, "accepted", receipt: receipt));
                Assert.AreEqual("completed", ledger.Stage(id));
            }
        }

        [Test]
        public void SavedWindowFollowedByLedgerFailureRemainsAnUnclosedOrphanCase() {
            LedgerPlan plan = Plan(); string path = Path.Combine(root, "ledger.jsonl");
            string id = plan.trials[0].trial_id;
            using (QuestTrialLedger ledger = new QuestTrialLedger(new AcceptanceFailingFileStore(path), plan, () => 10)) {
                Begin(ledger, id); ledger.Record(id, "completed", rawSampleCount: 120);
                WindowWriteReceipt receipt = QuestWindowWriter.AppendWindowWithReceipt(Path.Combine(root, "windows.jsonl"), Window(plan.trials[0], plan));
                Assert.Throws<IOException>(() => ledger.Record(id, "accepted", receipt: receipt));
                Assert.IsTrue(ledger.Faulted);
                Assert.AreEqual("completed", ledger.Stage(id));
                Assert.Throws<InvalidOperationException>(() => ledger.EndVisit("operator_stop"));
            }
            Assert.IsFalse(File.ReadAllText(path).Contains("visit_closed"));
            string export = Environment.GetEnvironmentVariable("PUF_SNN_LEDGER_FIXTURE_ROOT");
            if (!string.IsNullOrEmpty(export)) {
                string directory = Path.Combine(export, "orphan-case");
                Directory.CreateDirectory(directory);
                File.Copy(path, Path.Combine(directory, "ledger.jsonl"), false);
                File.Copy(Path.Combine(root, "windows.jsonl"), Path.Combine(directory, "windows.jsonl"), false);
            }
        }

        [TestCase("participant_reported_mistake")]
        [TestCase("observed_nonexecution")]
        [TestCase("late_movement")]
        [TestCase("movement_after_interval")]
        public void ExecutionNotesDoNotChangeThePromptOrOutcome(string note) {
            MemoryStore store = new MemoryStore(); LedgerPlan plan = Plan(); string id = plan.trials[0].trial_id;
            using (QuestTrialLedger ledger = new QuestTrialLedger(store, plan, () => 10)) {
                Begin(ledger, id); ledger.Record(id, "execution_note", note);
                Assert.AreEqual("recording_started", ledger.Stage(id));
                ledger.Record(id, "completed", rawSampleCount: 120); ledger.Record(id, "rejected", "tracking_coverage");
                Assert.AreEqual("rejected", ledger.Stage(id));
            }
            LedgerPlan saved = JsonUtility.FromJson<LedgerPlan>(store.lines[0]);
            Assert.AreEqual(plan.trials[0].prompted_task, saved.trials[0].prompted_task);
        }

        [Test]
        public void WindowReceiptMatchesExactBytesAndOffset() {
            string path = Path.Combine(root, "windows.jsonl"); LedgerPlan plan = Plan();
            WindowWriteReceipt first = QuestWindowWriter.AppendWindowWithReceipt(path, Window(plan.trials[0], plan));
            WindowWriteReceipt second = QuestWindowWriter.AppendWindowWithReceipt(path, Window(plan.trials[1], plan));
            byte[] bytes = File.ReadAllBytes(path);
            Assert.AreEqual(0, first.file_offset);
            Assert.AreEqual(first.line_length, second.file_offset);
            using (SHA256 sha = SHA256.Create()) {
                string hash = BitConverter.ToString(sha.ComputeHash(bytes.Skip((int)second.file_offset).Take(second.line_length).ToArray())).Replace("-", "").ToLowerInvariant();
                Assert.AreEqual(hash, second.line_sha256);
            }
            Assert.AreEqual(bytes.Length, first.line_length + second.line_length);
        }

        [Test]
        public void TornWindowFileIsPreservedAndRefused() {
            string path = Path.Combine(root, "windows.jsonl"); File.WriteAllText(path, "{partial", new UTF8Encoding(false));
            byte[] before = File.ReadAllBytes(path); LedgerPlan plan = Plan();
            Assert.Throws<InvalidDataException>(() => QuestWindowWriter.AppendWindowWithReceipt(path, Window(plan.trials[0], plan)));
            CollectionAssert.AreEqual(before, File.ReadAllBytes(path));
        }

        [Test]
        public void RecordingAuthorizationStaysOffByDefault() {
            GameObject go = new GameObject("synthetic-controller-test");
            try {
                QuestTrialController controller = go.AddComponent<QuestTrialController>();
                LogAssert.Expect(LogType.Warning, "recording is disabled until the approved-recording box is enabled");
                controller.StartTrialSession();
            } finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        [Test]
        public void SyntheticMixedVisitExportsForTheIndependentValidator() {
            LedgerPlan plan = Plan(); string path = Path.Combine(root, "ledger.jsonl");
            using (QuestTrialLedger ledger = QuestTrialLedger.Create(path, plan, () => 10)) {
                string id = plan.trials[0].trial_id; Begin(ledger, id); ledger.Record(id, "completed", rawSampleCount: 120);
                WindowWriteReceipt receipt = QuestWindowWriter.AppendWindowWithReceipt(Path.Combine(root, "windows.jsonl"), Window(plan.trials[0], plan));
                ledger.Record(id, "accepted", receipt: receipt);
                id = plan.trials[1].trial_id; Begin(ledger, id); ledger.Record(id, "completed", rawSampleCount: 0);
                ledger.Record(id, "rejected", "too_few_source_samples");
                ledger.Record(plan.trials[2].trial_id, "skipped", "participant_skip");
                Begin(ledger, plan.trials[3].trial_id); ledger.Record(plan.trials[3].trial_id, "stopped", "participant_stop");
                ledger.EndVisit("operator_stop");
            }
            Assert.AreEqual("visit_closed", JsonUtility.FromJson<LedgerEvent>(File.ReadAllLines(path).Last()).event_type);
            string export = Environment.GetEnvironmentVariable("PUF_SNN_LEDGER_FIXTURE_ROOT");
            if (!string.IsNullOrEmpty(export)) {
                Directory.CreateDirectory(export);
                File.Copy(path, Path.Combine(export, "ledger.jsonl"), false);
                File.Copy(Path.Combine(root, "windows.jsonl"), Path.Combine(export, "windows.jsonl"), false);
            }
        }

        private static QuestWindowRecord Window(LedgerTrial trial, LedgerPlan plan) {
            QuestWindowRecord record = new QuestWindowRecord {
                window_id = trial.trial_id + "-window-000", source_trial_id = trial.trial_id,
                trial_id = trial.trial_id, device_id = plan.device_id, session_id = plan.session_id,
                sequence_number = trial.trial_index, split = "validation", label = trial.prompted_task,
                window_start_ns = 0, window_end_ns = 2_000_000_000
            };
            for (int i = 0; i < 120; i++) record.samples.Add(new QuestWindowSample {
                sample_index = i, capture_time_ns = (long)Math.Round(i * 1_000_000_000.0 / 60),
                position_m = new[] { 0.0f, 0.0f, 0.0f }, orientation_xyzw = new[] { 0.0f, 0.0f, 0.0f, 1.0f }, tracking_valid = true
            });
            return record;
        }
    }
}
