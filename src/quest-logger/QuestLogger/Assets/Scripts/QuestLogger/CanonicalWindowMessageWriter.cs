/*
this file creates the same canonical protected-message bytes as the Python reference implementation
it does not create or verify an HMAC because those operations belong to the authentication layer
*/

using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace PufSnn.QuestLogger {
    public static class CanonicalWindowMessageWriter {
        public const string ProtocolVersion = "1.0";
        public const string MessageSchemaVersion = "1.0";
        public const string PayloadEncoding = "puf-snn-fixed-decimal-json-v1";
        public const int ExpectedSampleCount = 120;
        public const int MinimumTrackingValidSamples = 114;

        public static string BuildCanonicalProtectedJson(QuestWindowRecord record) {
            ValidateRecord(record);

            int trackingValidCount = 0;

            foreach (QuestWindowSample sample in record.samples) {
                if (sample.tracking_valid)
                    trackingValidCount++;
            }

            if (trackingValidCount < MinimumTrackingValidSamples)
                throw new InvalidDataException("window does not meet the 95 percent tracking requirement");

            int trackingValidFractionPpm = (int)Math.Round(trackingValidCount * 1_000_000.0 / ExpectedSampleCount, MidpointRounding.ToEven);
            StringBuilder builder = new StringBuilder(32_000);

            builder.Append('{');
            AppendPropertyName(builder, "capture_end_ns");
            builder.Append(record.window_end_ns.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "capture_start_ns");
            builder.Append(record.window_start_ns.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "data_quality");
            builder.Append('{');
            AppendPropertyName(builder, "sample_count");
            builder.Append(ExpectedSampleCount.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "status");
            AppendJsonString(builder, "pass");
            builder.Append(',');
            AppendPropertyName(builder, "tracking_valid_count");
            builder.Append(trackingValidCount.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "tracking_valid_fraction_ppm");
            builder.Append(trackingValidFractionPpm.ToString(CultureInfo.InvariantCulture));
            builder.Append('}');
            builder.Append(',');
            AppendPropertyName(builder, "device_id");
            AppendJsonString(builder, record.device_id);
            builder.Append(',');
            AppendPropertyName(builder, "message_schema_version");
            AppendJsonString(builder, MessageSchemaVersion);
            builder.Append(',');
            AppendPropertyName(builder, "payload");
            AppendPayload(builder, record);
            builder.Append(',');
            AppendPropertyName(builder, "payload_encoding");
            AppendJsonString(builder, PayloadEncoding);
            builder.Append(',');
            AppendPropertyName(builder, "payload_schema_version");
            AppendJsonString(builder, record.schema_version);
            builder.Append(',');
            AppendPropertyName(builder, "protocol_version");
            AppendJsonString(builder, ProtocolVersion);
            builder.Append(',');
            AppendPropertyName(builder, "sequence_number");
            builder.Append(record.sequence_number.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "session_id");
            AppendJsonString(builder, record.session_id);
            builder.Append(',');
            AppendPropertyName(builder, "window_id");
            AppendJsonString(builder, record.window_id);
            builder.Append('}');

            return builder.ToString();
        }

        public static byte[] BuildCanonicalProtectedBytes(QuestWindowRecord record) {
            return new UTF8Encoding(false).GetBytes(BuildCanonicalProtectedJson(record));
        }

        public static string CalculateCanonicalSha256(QuestWindowRecord record) {
            byte[] canonicalBytes = BuildCanonicalProtectedBytes(record);

            using (SHA256 hashAlgorithm = SHA256.Create()) {
                byte[] hash = hashAlgorithm.ComputeHash(canonicalBytes);
                StringBuilder result = new StringBuilder(hash.Length * 2);

                foreach (byte value in hash) {
                    result.Append(value.ToString("x2", CultureInfo.InvariantCulture));
                }

                return result.ToString();
            }
        }

        private static void AppendPayload(StringBuilder builder, QuestWindowRecord record) {
            builder.Append('{');
            AppendPropertyName(builder, "coordinate_frame");
            AppendJsonString(builder, record.coordinate_frame);
            builder.Append(',');
            AppendPropertyName(builder, "samples");
            builder.Append('[');

            for (int index = 0; index < record.samples.Count; index++) {
                if (index > 0)
                    builder.Append(',');

                AppendSample(builder, record.samples[index], index);
            }

            builder.Append(']');
            builder.Append(',');
            AppendPropertyName(builder, "target_sample_rate_hz");
            builder.Append(record.target_sample_rate_hz.ToString(CultureInfo.InvariantCulture));
            builder.Append('}');
        }

        private static void AppendSample(StringBuilder builder, QuestWindowSample sample, int expectedIndex) {
            if (sample == null)
                throw new InvalidDataException("window contains a null sample");

            if (sample.sample_index != expectedIndex)
                throw new InvalidDataException("sample indexes must be consecutive from zero");

            if (sample.position_m == null || sample.position_m.Length != 3)
                throw new InvalidDataException("position_m must contain three values");

            if (sample.orientation_xyzw == null || sample.orientation_xyzw.Length != 4)
                throw new InvalidDataException("orientation_xyzw must contain four values");

            builder.Append('{');
            AppendPropertyName(builder, "capture_time_ns");
            builder.Append(sample.capture_time_ns.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "orientation_xyzw");
            AppendFloatArray(builder, sample.orientation_xyzw);
            builder.Append(',');
            AppendPropertyName(builder, "position_m");
            AppendFloatArray(builder, sample.position_m);
            builder.Append(',');
            AppendPropertyName(builder, "sample_index");
            builder.Append(sample.sample_index.ToString(CultureInfo.InvariantCulture));
            builder.Append(',');
            AppendPropertyName(builder, "tracking_valid");
            builder.Append(sample.tracking_valid ? "true" : "false");
            builder.Append('}');
        }

        private static void AppendFloatArray(StringBuilder builder, float[] values) {
            builder.Append('[');

            for (int index = 0; index < values.Length; index++) {
                if (index > 0)
                    builder.Append(',');

                AppendJsonString(builder, FormatMotionValue(values[index]));
            }

            builder.Append(']');
        }

        private static string FormatMotionValue(float value) {
            if (float.IsNaN(value) || float.IsInfinity(value))
                throw new InvalidDataException("motion values must be finite");

            decimal roundedValue = Math.Round((decimal)value, 8, MidpointRounding.ToEven);

            if (roundedValue == 0m)
                roundedValue = 0m;

            return roundedValue.ToString("F8", CultureInfo.InvariantCulture);
        }

        private static void ValidateRecord(QuestWindowRecord record) {
            if (record == null)
                throw new ArgumentNullException(nameof(record));

            if (
                string.IsNullOrWhiteSpace(record.schema_version) ||
                string.IsNullOrWhiteSpace(record.window_id) ||
                string.IsNullOrWhiteSpace(record.device_id) ||
                string.IsNullOrWhiteSpace(record.session_id) ||
                string.IsNullOrWhiteSpace(record.coordinate_frame)
            )
                throw new InvalidDataException("window is missing required protected fields");

            if (record.samples == null || record.samples.Count != ExpectedSampleCount)
                throw new InvalidDataException("window must contain exactly 120 samples");

            if (record.sequence_number < 0)
                throw new InvalidDataException("sequence number must not be negative");

            if (record.window_start_ns < 0 || record.window_end_ns <= record.window_start_ns)
                throw new InvalidDataException("window time range is invalid");
        }

        private static void AppendPropertyName(StringBuilder builder, string name) {
            AppendJsonString(builder, name);
            builder.Append(':');
        }

        private static void AppendJsonString(StringBuilder builder, string value) {
            if (value == null)
                throw new InvalidDataException("canonical string values must not be null");

            builder.Append('"');

            foreach (char character in value) {
                switch (character) {
                    case '"':
                        builder.Append("\\\"");
                        break;
                    case '\\':
                        builder.Append("\\\\");
                        break;
                    case '\b':
                        builder.Append("\\b");
                        break;
                    case '\f':
                        builder.Append("\\f");
                        break;
                    case '\n':
                        builder.Append("\\n");
                        break;
                    case '\r':
                        builder.Append("\\r");
                        break;
                    case '\t':
                        builder.Append("\\t");
                        break;
                    default:
                        if (character < 0x20)
                            builder.Append("\\u" + ((int)character).ToString("x4", CultureInfo.InvariantCulture));
                        else
                            builder.Append(character);
                        break;
                }
            }

            builder.Append('"');
        }
    }
}
