using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using UnityEngine;

namespace PufSnn.QuestLogger {
    [Serializable]
    public sealed class LedgerTrial {
        public string trial_id;
        public int trial_index;
        public int block_index;
        public string prompted_task;
        public string repeat_of_trial_id = "";
    }

    [Serializable]
    public sealed class LedgerPlan {
        public string record_type = "plan";
        public string schema_version = "quest-trial-ledger-v1";
        public string participant_code;
        public string visit_code;
        public string device_id;
        public string session_id;
        public string processing_version;
        public string window_file_name = "quest-windows.jsonl";
        public string time_basis = "head-capture-stopwatch-ns";
        public string raw_retention = "not_saved";
        public string repeat_policy = "none";
        public int schedule_seed;
        public int maximum_trials = 75;
        public long created_elapsed_ns;
        public List<LedgerTrial> trials = new List<LedgerTrial>();
    }

    [Serializable]
    public sealed class LedgerEvent {
        public string record_type = "event";
        public int event_index;
        public string event_type;
        public long elapsed_ns;
        public string trial_id = "";
        public string reason_code = "";
        public int raw_sample_count = -1;
        public string window_id = "";
        public string file_name = "";
        public string line_sha256 = "";
        public long file_offset = -1;
        public int line_length;
    }

    public interface ITrialLedgerStore : IDisposable {
        void Append(string json);
    }

    // One serial writer. A failed append poisons the ledger; it cannot close successfully.
    public sealed class FileTrialLedgerStore : ITrialLedgerStore {
        private readonly FileStream stream;
        private static readonly UTF8Encoding Encoding = new UTF8Encoding(false, true);

        public FileTrialLedgerStore(string path) {
            string directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrEmpty(directory)) Directory.CreateDirectory(directory);
            stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read);
        }

        public void Append(string json) {
            if (string.IsNullOrEmpty(json) || json.IndexOfAny(new[] { '\r', '\n' }) >= 0)
                throw new InvalidDataException("A ledger event must be one nonempty JSON line.");
            byte[] bytes = Encoding.GetBytes(json + "\n");
            stream.Write(bytes, 0, bytes.Length);
            stream.Flush(true);
        }

        public void Dispose() { stream.Dispose(); }
    }

    public sealed class QuestTrialLedger : IDisposable {
        private sealed class TrialState {
            public string stage = "scheduled";
        }

        public static readonly string[] Labels = {
            "nod", "shake", "look_left_return", "look_right_return", "still"
        };
        private static readonly Regex Code = new Regex(@"\A[A-Za-z0-9][A-Za-z0-9_-]{0,127}\z");
        private readonly Dictionary<string, TrialState> states = new Dictionary<string, TrialState>();
        private readonly List<string> order = new List<string>();
        private readonly ITrialLedgerStore store;
        private readonly Func<long> clock;
        private long previousTime;
        private int nextIndex = 1;
        private bool disposed;
        private string activeTrial = "";
        public bool Faulted { get; private set; }
        public bool Closed { get; private set; }

        public static QuestTrialLedger Create(string path, LedgerPlan plan, Func<long> clock) {
            ValidatePlan(plan);
            return new QuestTrialLedger(new FileTrialLedgerStore(path), plan, clock);
        }

        public QuestTrialLedger(ITrialLedgerStore store, LedgerPlan plan, Func<long> clock) {
            this.store = store ?? throw new ArgumentNullException(nameof(store));
            this.clock = clock ?? throw new ArgumentNullException(nameof(clock));
            try {
                ValidatePlan(plan);
                // Snapshot the caller's mutable plan before recording or using it.
                LedgerPlan frozen = JsonUtility.FromJson<LedgerPlan>(JsonUtility.ToJson(plan));
                previousTime = this.clock();
                if (previousTime < 0) throw new InvalidDataException("Negative elapsed time.");
                frozen.created_elapsed_ns = previousTime;
                foreach (LedgerTrial trial in frozen.trials) {
                    states.Add(trial.trial_id, new TrialState());
                    order.Add(trial.trial_id);
                }
                this.store.Append(JsonUtility.ToJson(frozen, false));
            } catch {
                Faulted = true;
                this.store.Dispose();
                throw;
            }
        }

        public static LedgerPlan BuildPlan(string participant, string visit, string device,
            string session, string version, int blocks, int perClass, int seed, int maximumTrials = 75) {
            if (blocks <= 0 || perClass <= 0 || maximumTrials <= 0 || maximumTrials > 75 ||
                (long)blocks * perClass * Labels.Length > maximumTrials)
                throw new ArgumentException("The schedule must contain 1 to 75 trials within its declared cap.");
            LedgerPlan plan = new LedgerPlan {
                participant_code = participant, visit_code = visit, device_id = device,
                session_id = session, processing_version = version, schedule_seed = seed,
                maximum_trials = maximumTrials
            };
            System.Random random = new System.Random(seed);
            for (int block = 1; block <= blocks; block++) {
                List<string> tasks = new List<string>();
                for (int repetition = 0; repetition < perClass; repetition++) tasks.AddRange(Labels);
                for (int index = tasks.Count - 1; index > 0; index--) {
                    int other = random.Next(index + 1);
                    string task = tasks[index]; tasks[index] = tasks[other]; tasks[other] = task;
                }
                foreach (string task in tasks) {
                    int index = plan.trials.Count;
                    plan.trials.Add(new LedgerTrial {
                        trial_id = string.Format("{0}-trial-{1:D3}", visit, index),
                        trial_index = index, block_index = block, prompted_task = task
                    });
                }
            }
            ValidatePlan(plan);
            return plan;
        }

        public static void ValidatePlan(LedgerPlan plan) {
            if (plan == null) throw new ArgumentNullException(nameof(plan));
            if (plan.record_type != "plan" || plan.schema_version != "quest-trial-ledger-v1" ||
                plan.time_basis != "head-capture-stopwatch-ns" || plan.raw_retention != "not_saved" ||
                plan.repeat_policy != "none") throw new ArgumentException("Unsupported ledger policy.");
            foreach (string code in new[] { plan.participant_code, plan.visit_code, plan.device_id, plan.session_id })
                if (code == null || !Code.IsMatch(code)) throw new ArgumentException("Use nonempty coded identifiers without paths or spaces.");
            if (string.IsNullOrWhiteSpace(plan.processing_version) || plan.processing_version.Length > 256)
                throw new ArgumentException("Record the actual processing/build version before recording.");
            if (string.IsNullOrWhiteSpace(plan.window_file_name) || plan.window_file_name == "." || plan.window_file_name == ".." ||
                plan.window_file_name.IndexOfAny(new[] { '/', '\\', ':' }) >= 0)
                throw new ArgumentException("Use a local window filename.");
            if (plan.maximum_trials < 1 || plan.maximum_trials > 75 || plan.trials == null ||
                plan.trials.Count < 1 || plan.trials.Count > plan.maximum_trials)
                throw new ArgumentException("Invalid planned trial count.");
            HashSet<string> ids = new HashSet<string>();
            for (int index = 0; index < plan.trials.Count; index++) {
                LedgerTrial trial = plan.trials[index];
                if (trial == null || trial.trial_id == null || !Code.IsMatch(trial.trial_id) ||
                    !ids.Add(trial.trial_id) || trial.trial_index != index || trial.block_index < 1 ||
                    Array.IndexOf(Labels, trial.prompted_task) < 0 || !string.IsNullOrEmpty(trial.repeat_of_trial_id))
                    throw new ArgumentException("Invalid, duplicated, or repeated planned trial.");
            }
        }

        public string Stage(string trialId) {
            if (!states.TryGetValue(trialId, out TrialState state)) throw new ArgumentException("Unknown trial.");
            return state.stage;
        }

        public void Record(string trialId, string eventType, string reason = "", int rawSampleCount = -1,
            WindowWriteReceipt receipt = null) {
            EnsureOpen();
            string stage = Stage(trialId);
            if (eventType == "prompted" && !string.IsNullOrEmpty(activeTrial))
                throw new InvalidOperationException("Finish the current trial before prompting another.");
            bool allowed =
                (eventType == "prompted" && stage == "scheduled") ||
                (eventType == "start_requested" && stage == "prompted") ||
                (eventType == "recording_started" && stage == "start_requested") ||
                (eventType == "completed" && stage == "recording_started" && rawSampleCount >= 0) ||
                ((eventType == "accepted" || eventType == "rejected" || eventType == "processing_failed") && stage == "completed") ||
                ((eventType == "skipped" || eventType == "not_attempted") && (stage == "scheduled" || stage == "prompted")) ||
                (eventType == "stopped" && (stage == "start_requested" || stage == "recording_started")) ||
                (eventType == "execution_note" && (stage == "recording_started" || stage == "completed" ||
                    stage == "accepted" || stage == "rejected" || stage == "processing_failed" || stage == "stopped"));
            if (!allowed) throw new InvalidOperationException("Invalid trial transition: " + stage + " -> " + eventType);
            bool reasonRequired = eventType == "rejected" || eventType == "processing_failed" ||
                eventType == "skipped" || eventType == "not_attempted" || eventType == "stopped" || eventType == "execution_note";
            if (reasonRequired && string.IsNullOrWhiteSpace(reason)) throw new ArgumentException("A reason code is required.");
            if (reasonRequired && !Regex.IsMatch(reason, @"\A[a-z][a-z0-9_]{0,95}\z"))
                throw new ArgumentException("Use a reason code, not free text or personal details.");
            if (eventType == "execution_note" && Array.IndexOf(new[] {
                "participant_reported_mistake", "observed_nonexecution", "late_movement", "movement_after_interval"
            }, reason) < 0) throw new ArgumentException("Unsupported execution note.");
            if (!reasonRequired && !string.IsNullOrEmpty(reason)) throw new ArgumentException("Unexpected reason code.");
            if (eventType != "completed" && rawSampleCount != -1) throw new ArgumentException("Sample count belongs to completion.");
            if ((eventType == "accepted") != (receipt != null)) throw new ArgumentException("Only acceptance carries a saved-window receipt.");
            LedgerEvent entry = new LedgerEvent {
                event_index = nextIndex, event_type = eventType, elapsed_ns = NextTime(),
                trial_id = trialId, reason_code = reason, raw_sample_count = rawSampleCount
            };
            if (receipt != null) {
                if (string.IsNullOrWhiteSpace(receipt.file_name) || Path.GetFileName(receipt.file_name) != receipt.file_name ||
                    receipt.file_name == "." || receipt.file_name == ".." || receipt.file_name.IndexOfAny(new[] { '/', '\\', ':' }) >= 0 ||
                    string.IsNullOrWhiteSpace(receipt.window_id) || receipt.file_offset < 0 || receipt.line_length < 2 ||
                    receipt.line_sha256 == null || !Regex.IsMatch(receipt.line_sha256, @"\A[0-9a-f]{64}\z"))
                    throw new ArgumentException("Invalid saved-window receipt.");
                entry.window_id = receipt.window_id; entry.file_name = receipt.file_name;
                entry.file_offset = receipt.file_offset; entry.line_length = receipt.line_length;
                entry.line_sha256 = receipt.line_sha256;
            }
            Append(entry);
            if (eventType != "execution_note") states[trialId].stage = eventType;
            if (eventType == "prompted") activeTrial = trialId;
            if (trialId == activeTrial && (eventType == "accepted" || eventType == "rejected" ||
                eventType == "processing_failed" || eventType == "stopped" || eventType == "skipped" || eventType == "not_attempted"))
                activeTrial = "";
        }

        public void EndVisit(string reason) {
            EnsureOpen();
            if (string.IsNullOrWhiteSpace(reason) || !Regex.IsMatch(reason, @"\A[a-z][a-z0-9_]{0,95}\z"))
                throw new ArgumentException("A visit-end reason code is required.");
            foreach (string id in order) {
                string stage = Stage(id);
                if (stage == "scheduled" || stage == "prompted") Record(id, "not_attempted", reason);
                else if (stage == "start_requested" || stage == "recording_started") Record(id, "stopped", reason);
                else if (stage == "completed") Record(id, "processing_failed", "processing_interrupted");
            }
            Append(new LedgerEvent {
                event_index = nextIndex, event_type = "visit_closed", elapsed_ns = NextTime(), reason_code = reason
            });
            Closed = true;
        }

        private long NextTime() {
            long value = clock();
            if (value < previousTime) throw new InvalidOperationException("The monotonic clock went backward.");
            return value;
        }

        private void Append(LedgerEvent entry) {
            try { store.Append(JsonUtility.ToJson(entry, false)); }
            catch { Faulted = true; throw; }
            previousTime = entry.elapsed_ns;
            nextIndex++;
        }

        private void EnsureOpen() {
            if (disposed || Faulted || Closed) throw new InvalidOperationException("Ledger is closed or unavailable.");
        }

        // Disposing does not fabricate successful completion after a crash or failed write.
        public void Dispose() {
            if (disposed) return;
            disposed = true;
            store.Dispose();
        }
    }
}
