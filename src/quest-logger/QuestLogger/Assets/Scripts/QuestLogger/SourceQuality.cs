using System;
using System.Collections.Generic;
using System.IO;
using System.Text.RegularExpressions;
using UnityEngine;

namespace PufSnn.QuestLogger {
    // Diagnostics only. These calculations do not repair poses or decide acceptance.
    [Serializable]
    public sealed class SourceQualityMetrics {
        public string status = "unavailable";
        public string unavailable_reason = "not_measured";
        public int source_sample_count = -1;
        public long first_capture_ns = -1;
        public long last_capture_ns = -1;
        public long source_duration_ns = -1;
        public double observed_rate_hz = -1;
        public int tracking_valid_count = -1;
        public int tracking_invalid_count = -1;
        public int tracking_flag_available_count = -1;
        public int tracking_state_available_count = -1;
        public int positive_interval_count = -1;
        public int nonpositive_interval_count = -1;
        public int interval_overflow_count = -1;
        public int negative_timestamp_count = -1;
        public int gap_over_50ms_count = -1;
        public long maximum_positive_gap_ns = -1;
        public long median_positive_gap_ns = -1;
        public long p95_positive_gap_ns = -1;
        public int nonfinite_pose_count = -1;
        public int zero_orientation_count = -1;

        public static SourceQualityMetrics Unavailable(string reason) {
            return new SourceQualityMetrics { unavailable_reason = reason };
        }

        public static SourceQualityMetrics Measure(IReadOnlyList<RawHeadPoseSample> samples) {
            if (samples == null) throw new ArgumentNullException(nameof(samples));
            SourceQualityMetrics m = new SourceQualityMetrics {
                status = samples.Count == 0 ? "empty" : "available", unavailable_reason = "",
                source_sample_count = samples.Count, tracking_valid_count = 0, tracking_invalid_count = 0,
                tracking_flag_available_count = 0, tracking_state_available_count = 0,
                positive_interval_count = 0, nonpositive_interval_count = 0, interval_overflow_count = 0,
                negative_timestamp_count = 0, gap_over_50ms_count = 0, nonfinite_pose_count = 0,
                zero_orientation_count = 0
            };
            List<long> positive = new List<long>();
            for (int i = 0; i < samples.Count; i++) {
                RawHeadPoseSample s = samples[i];
                if (s == null) throw new ArgumentException("A source sample is missing.");
                if (s.tracking_valid) m.tracking_valid_count++; else m.tracking_invalid_count++;
                if (s.tracking_flag_available) m.tracking_flag_available_count++;
                if (s.tracking_state_available) m.tracking_state_available_count++;
                if (s.capture_time_ns < 0) m.negative_timestamp_count++;
                if (!Finite(s.position_m.x) || !Finite(s.position_m.y) || !Finite(s.position_m.z) ||
                    !Finite(s.orientation_xyzw.x) || !Finite(s.orientation_xyzw.y) ||
                    !Finite(s.orientation_xyzw.z) || !Finite(s.orientation_xyzw.w)) m.nonfinite_pose_count++;
                if (s.orientation_xyzw.x == 0 && s.orientation_xyzw.y == 0 &&
                    s.orientation_xyzw.z == 0 && s.orientation_xyzw.w == 0) m.zero_orientation_count++;
                if (i == 0) continue;
                try {
                    long gap = checked(s.capture_time_ns - samples[i - 1].capture_time_ns);
                    if (gap <= 0) m.nonpositive_interval_count++;
                    else {
                        positive.Add(gap);
                        if (gap > QuestWindowProcessor.MaximumTimestampGapNs) m.gap_over_50ms_count++;
                    }
                } catch (OverflowException) { m.interval_overflow_count++; }
            }
            m.positive_interval_count = positive.Count;
            if (samples.Count > 0) {
                m.first_capture_ns = samples[0].capture_time_ns;
                m.last_capture_ns = samples[samples.Count - 1].capture_time_ns;
                if (m.nonpositive_interval_count == 0 && m.interval_overflow_count == 0 && m.negative_timestamp_count == 0) {
                    m.source_duration_ns = m.last_capture_ns - m.first_capture_ns;
                    if (samples.Count > 1 && m.source_duration_ns > 0)
                        m.observed_rate_hz = (samples.Count - 1) * 1_000_000_000.0 / m.source_duration_ns;
                }
            }
            if (positive.Count > 0) {
                positive.Sort(); // Sort a separate interval list, never the source samples.
                m.maximum_positive_gap_ns = positive[positive.Count - 1];
                m.median_positive_gap_ns = positive[(int)Math.Ceiling(positive.Count * 0.5) - 1];
                m.p95_positive_gap_ns = positive[(int)Math.Ceiling(positive.Count * 0.95) - 1];
            }
            return m;
        }

        private static bool Finite(float value) { return !float.IsNaN(value) && !float.IsInfinity(value); }
    }

    [Serializable]
    public sealed class SourceQualityHeader {
        public string record_type = "source_quality_plan";
        public string schema_version = "quest-source-quality-v1";
        public string participant_code;
        public string visit_code;
        public string device_id;
        public string session_id;
        public string processing_version;
        public string ledger_file_name;
        public string time_basis = "head-capture-stopwatch-ns";
        public string interval_quantile_method = "nearest_rank";
        public long gap_limit_ns = QuestWindowProcessor.MaximumTimestampGapNs;
        public string raw_retention = "not_saved";
    }

    [Serializable]
    public sealed class SourceQualityRow {
        public string record_type = "source_quality";
        public int summary_index;
        public long elapsed_ns;
        public string trial_id;
        public string source_stage;
        public string reason_code;
        public SourceQualityMetrics metrics;
    }

    // A separate append-only diagnostic file keeps the published trial-ledger v1 readable.
    public sealed class SourceQualityWriter : IDisposable {
        private readonly ITrialLedgerStore store;
        private readonly Func<long> clock;
        private readonly HashSet<string> planned = new HashSet<string>();
        private readonly HashSet<string> written = new HashSet<string>();
        private int nextIndex = 1;
        private long lastTime;
        private bool disposed;
        public bool Faulted { get; private set; }

        public static SourceQualityWriter Create(string path, string ledgerFileName, LedgerPlan plan, Func<long> clock) {
            QuestTrialLedger.ValidatePlan(plan);
            return new SourceQualityWriter(new FileTrialLedgerStore(path), ledgerFileName, plan, clock);
        }

        public SourceQualityWriter(ITrialLedgerStore store, string ledgerFileName, LedgerPlan plan, Func<long> clock) {
            this.store = store ?? throw new ArgumentNullException(nameof(store));
            try {
                this.clock = clock ?? throw new ArgumentNullException(nameof(clock));
                QuestTrialLedger.ValidatePlan(plan);
                if (string.IsNullOrWhiteSpace(ledgerFileName) || ledgerFileName == "." || ledgerFileName == ".." ||
                    ledgerFileName.IndexOfAny(new[] { '/', '\\', ':' }) >= 0) throw new ArgumentException("Use a local ledger filename.");
                foreach (LedgerTrial trial in plan.trials) planned.Add(trial.trial_id);
                lastTime = clock();
                if (lastTime < 0) throw new ArgumentException("Negative clock.");
                store.Append(JsonUtility.ToJson(new SourceQualityHeader {
                    participant_code = plan.participant_code, visit_code = plan.visit_code,
                    device_id = plan.device_id, session_id = plan.session_id,
                    processing_version = plan.processing_version, ledger_file_name = ledgerFileName
                }));
            } catch { Faulted = true; store.Dispose(); throw; }
        }

        public bool HasTrial(string trialId) { return written.Contains(trialId); }

        public void Write(string trialId, string stage, string reason, IReadOnlyList<RawHeadPoseSample> samples) {
            if (disposed || Faulted) throw new InvalidOperationException("Source-quality writer unavailable.");
            if (!planned.Contains(trialId) || written.Contains(trialId)) throw new ArgumentException("Unknown or duplicated source summary.");
            if (stage != "completed" && stage != "stopped" && stage != "unconfirmed") throw new ArgumentException("Invalid source stage.");
            if (reason == null || !Regex.IsMatch(reason, @"\A[a-z][a-z0-9_]{0,95}\z")) throw new ArgumentException("Use a reason code.");
            if ((stage == "unconfirmed") != (samples == null)) throw new ArgumentException("Only unconfirmed capture uses unavailable samples.");
            long now = clock();
            if (now < lastTime) throw new InvalidOperationException("The clock went backward.");
            SourceQualityRow row = new SourceQualityRow {
                summary_index = nextIndex, elapsed_ns = now, trial_id = trialId,
                source_stage = stage, reason_code = reason,
                metrics = samples == null ? SourceQualityMetrics.Unavailable(reason) : SourceQualityMetrics.Measure(samples)
            };
            try { store.Append(JsonUtility.ToJson(row)); }
            catch { Faulted = true; throw; }
            written.Add(trialId); nextIndex++; lastTime = now;
        }

        public void Dispose() { if (!disposed) { disposed = true; store.Dispose(); } }
    }
}
