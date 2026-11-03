using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.XR;

namespace PufSnn.QuestLogger {
    [Serializable]
    public sealed class RetainedSourceSample {
        public long capture_time_ns;
        public int[] position_m_float32_bits;
        public int[] orientation_xyzw_float32_bits;
        public bool tracking_valid;
        public int tracking_state;
        public bool tracking_flag_available;
        public bool tracking_state_available;
    }

    [Serializable]
    public sealed class AcceptedSourceRecord {
        public string schema_version = "quest-accepted-source-candidate-v1";
        public string purpose = "synthetic_development_only";
        public string planned_acquisition_mode = "pc_hosted_quest_link";
        public string time_basis = "head-capture-stopwatch-ns";
        public string coordinate_frame = "unity_device_origin";
        public string numeric_encoding = "signed_int32_ieee754_float32_bits";
        public string outcome = "accepted";
        public string processing_version;
        public string device_id;
        public string session_id;
        public string trial_id;
        public string split;
        public string label;
        public int sequence_number;
        public List<RetainedSourceSample> samples = new List<RetainedSourceSample>();
    }

    // Offline development candidate. No scene or live controller calls this exporter.
    // A future collection integration needs a declared retention policy and ledger links.
    public static class AcceptedSourceCandidate {
        public static int Bits(float value) => BitConverter.ToInt32(BitConverter.GetBytes(value), 0);
        public static float FromBits(int value) => BitConverter.ToSingle(BitConverter.GetBytes(value), 0);

        public static string Serialize(string outcome, IReadOnlyList<RawHeadPoseSample> raw,
            QuestTrialMetadata metadata, string processingVersion, QuestWindowRecord expected) {
            if (outcome != "accepted") throw new InvalidDataException("Only accepted source is eligible for export.");
            if (string.IsNullOrWhiteSpace(processingVersion)) throw new ArgumentException("A processing version is required.");
            if (metadata == null) throw new ArgumentException("Trial metadata is required.");
            foreach (string identity in new[] {processingVersion, metadata.device_id, metadata.session_id, metadata.trial_id})
                if (identity == null || !System.Text.RegularExpressions.Regex.IsMatch(identity, @"\A[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\z"))
                    throw new InvalidDataException("Use coded source identifiers.");
            if (raw == null || raw.Count < 2 || raw.Count > 20000)
                throw new InvalidDataException("Invalid source sample count.");
            foreach (var sample in raw)
                if (sample == null || sample.capture_time_ns < 0 || sample.capture_time_ns > long.MaxValue - QuestWindowProcessor.WindowDurationNs || ((int)sample.tracking_state & ~63) != 0)
                    throw new InvalidDataException("Invalid source timestamp or tracking state.");
            if (!QuestWindowProcessor.TryCreateWindow(raw, metadata, out var replay, out var reason))
                throw new InvalidDataException("Source quality refused: " + reason);
            if (expected == null || QuestWindowWriter.SerializeWindow(replay) != QuestWindowWriter.SerializeWindow(expected))
                throw new InvalidDataException("Source does not reproduce the supplied window.");
            var record = new AcceptedSourceRecord {
                processing_version = processingVersion, device_id = metadata.device_id,
                session_id = metadata.session_id, trial_id = metadata.trial_id,
                split = metadata.split, label = metadata.label, sequence_number = metadata.sequence_number
            };
            foreach (var sample in raw) record.samples.Add(new RetainedSourceSample {
                capture_time_ns = sample.capture_time_ns,
                position_m_float32_bits = new[] {Bits(sample.position_m.x), Bits(sample.position_m.y), Bits(sample.position_m.z)},
                orientation_xyzw_float32_bits = new[] {Bits(sample.orientation_xyzw.x), Bits(sample.orientation_xyzw.y), Bits(sample.orientation_xyzw.z), Bits(sample.orientation_xyzw.w)},
                tracking_valid = sample.tracking_valid, tracking_state = (int)sample.tracking_state,
                tracking_flag_available = sample.tracking_flag_available,
                tracking_state_available = sample.tracking_state_available
            });
            return JsonUtility.ToJson(record);
        }

        public static QuestWindowRecord Replay(string json, out SourceQualityMetrics metrics) {
            if (string.IsNullOrWhiteSpace(json) || json.Length > 16 * 1024 * 1024)
                throw new InvalidDataException("Missing or oversized source record.");
            AcceptedSourceRecord record;
            try { record = JsonUtility.FromJson<AcceptedSourceRecord>(json); }
            catch (Exception error) { throw new InvalidDataException("Malformed source JSON.", error); }
            if (record == null || record.schema_version != "quest-accepted-source-candidate-v1" ||
                record.purpose != "synthetic_development_only" || record.planned_acquisition_mode != "pc_hosted_quest_link" ||
                record.time_basis != "head-capture-stopwatch-ns" || record.coordinate_frame != "unity_device_origin" ||
                record.numeric_encoding != "signed_int32_ieee754_float32_bits" || record.outcome != "accepted" ||
                string.IsNullOrWhiteSpace(record.processing_version) || record.samples == null ||
                record.samples.Count < 2 || record.samples.Count > 20000)
                throw new InvalidDataException("Unsupported or incomplete source record.");
            var raw = new List<RawHeadPoseSample>();
            foreach (var sample in record.samples) {
                if (sample == null || sample.capture_time_ns < 0 || sample.capture_time_ns > long.MaxValue - QuestWindowProcessor.WindowDurationNs || sample.position_m_float32_bits == null ||
                    sample.position_m_float32_bits.Length != 3 || sample.orientation_xyzw_float32_bits == null ||
                    sample.orientation_xyzw_float32_bits.Length != 4 || (sample.tracking_state & ~63) != 0)
                    throw new InvalidDataException("Invalid source sample.");
                var p = sample.position_m_float32_bits; var q = sample.orientation_xyzw_float32_bits;
                raw.Add(new RawHeadPoseSample {
                    capture_time_ns = sample.capture_time_ns,
                    position_m = new Vector3(FromBits(p[0]), FromBits(p[1]), FromBits(p[2])),
                    orientation_xyzw = new Quaternion(FromBits(q[0]), FromBits(q[1]), FromBits(q[2]), FromBits(q[3])),
                    tracking_valid = sample.tracking_valid, tracking_state = (InputTrackingState)sample.tracking_state,
                    tracking_flag_available = sample.tracking_flag_available,
                    tracking_state_available = sample.tracking_state_available
                });
            }
            var metadata = new QuestTrialMetadata {device_id = record.device_id, session_id = record.session_id,
                trial_id = record.trial_id, split = record.split, label = record.label, sequence_number = record.sequence_number};
            if (!QuestWindowProcessor.TryCreateWindow(raw, metadata, out var window, out var reason))
                throw new InvalidDataException("Retained source quality refused: " + reason);
            metrics = SourceQualityMetrics.Measure(raw);
            return window;
        }

        public static void ExportNew(string path, string outcome, IReadOnlyList<RawHeadPoseSample> raw,
            QuestTrialMetadata metadata, string processingVersion, QuestWindowRecord expected) {
            // Validate before touching the output path. A refused/stopped capture creates no file.
            byte[] bytes = new UTF8Encoding(false, true).GetBytes(Serialize(outcome, raw, metadata, processingVersion, expected) + "\n");
            using (var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write, FileShare.Read)) {
                stream.Write(bytes, 0, bytes.Length); stream.Flush(true);
            }
        }
    }
}
