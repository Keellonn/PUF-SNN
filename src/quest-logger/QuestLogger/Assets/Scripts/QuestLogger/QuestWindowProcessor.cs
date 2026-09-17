/*
this file checks raw head poses and converts one two-second trial into 120 ordered samples
position uses linear interpolation and orientation uses normalized quaternion slerp
*/

using System;
using System.Collections.Generic;
using UnityEngine;

namespace PufSnn.QuestLogger {
    public static class QuestWindowProcessor {
        public const int TargetSampleRateHz = 60;
        public const int TargetSampleCount = 120;
        public const long WindowDurationNs = 2_000_000_000;
        public const long MaximumTimestampGapNs = 50_000_000;
        public const float MinimumTrackingValidFraction = 0.95f;

        private static readonly HashSet<string> Labels = new HashSet<string> {
            "nod",
            "shake",
            "look_left_return",
            "look_right_return",
            "still",
        };

        private static readonly HashSet<string> Splits = new HashSet<string> {
            "train",
            "validation",
            "test",
        };

        public static bool TryCreateWindow(IReadOnlyList<RawHeadPoseSample> rawSamples, QuestTrialMetadata metadata, out QuestWindowRecord record, out string rejectionReason) {
            record = null;
            rejectionReason = ValidateMetadata(metadata);

            if (rejectionReason != null) {
                return false;
            }

            if (rawSamples == null || rawSamples.Count < 2) {
                rejectionReason = "the trial contains fewer than two raw samples";
                return false;
            }

            // this rejects bad timing before interpolation
            for (int index = 1; index < rawSamples.Count; index++) {
                long gap = rawSamples[index].capture_time_ns - rawSamples[index - 1].capture_time_ns;

                if (gap <= 0) {
                    rejectionReason = "raw timestamps are not strictly increasing";
                    return false;
                }

                if (gap > MaximumTimestampGapNs) {
                    rejectionReason = "a raw timestamp gap exceeds 50 ms";
                    return false;
                }
            }

            long windowStartNs = rawSamples[0].capture_time_ns;
            long finalTargetNs = TargetTimeNs(windowStartNs, TargetSampleCount - 1);

            if (rawSamples[rawSamples.Count - 1].capture_time_ns < finalTargetNs) {
                rejectionReason = "raw samples do not cover the final 60 Hz target time";
                return false;
            }

            QuestWindowRecord candidate = new QuestWindowRecord {
                window_id = metadata.trial_id + "-window-000",
                source_trial_id = metadata.trial_id,
                device_id = metadata.device_id,
                session_id = metadata.session_id,
                trial_id = metadata.trial_id,
                split = metadata.split,
                sequence_number = metadata.sequence_number,
                label = metadata.label,
                window_start_ns = windowStartNs,
                window_end_ns = windowStartNs + WindowDurationNs,
            };

            int upperIndex = 1;
            int validSampleCount = 0;
            Quaternion previousOrientation = Quaternion.identity;

            // this builds the fixed 60 hz output grid
            for (int sampleIndex = 0; sampleIndex < TargetSampleCount; sampleIndex++) {
                long targetTimeNs = TargetTimeNs(windowStartNs, sampleIndex);

                while (
                    upperIndex < rawSamples.Count - 1 &&
                    rawSamples[upperIndex].capture_time_ns < targetTimeNs
                ) {
                    upperIndex++;
                }

                RawHeadPoseSample lower = rawSamples[upperIndex - 1];
                RawHeadPoseSample upper = rawSamples[upperIndex];
                long intervalNs = upper.capture_time_ns - lower.capture_time_ns;
                float amount = intervalNs == 0
                    ? 0.0f
                    : (float)((targetTimeNs - lower.capture_time_ns) / (double)intervalNs);

                amount = Mathf.Clamp01(amount);
                Vector3 position = Vector3.Lerp(lower.position_m, upper.position_m, amount);
                Quaternion lowerOrientation = Normalize(lower.orientation_xyzw);
                Quaternion upperOrientation = Normalize(upper.orientation_xyzw);

                if (Quaternion.Dot(lowerOrientation, upperOrientation) < 0.0f) {
                    upperOrientation = Negate(upperOrientation);
                }

                Quaternion orientation = Normalize(Quaternion.Slerp(lowerOrientation, upperOrientation, amount));

                if (sampleIndex > 0 && Quaternion.Dot(previousOrientation, orientation) < 0.0f) {
                    orientation = Negate(orientation);
                }

                bool trackingValid = lower.tracking_valid && upper.tracking_valid;

                if (trackingValid) {
                    validSampleCount++;
                }

                candidate.samples.Add(new QuestWindowSample {
                    sample_index = sampleIndex,
                    capture_time_ns = targetTimeNs,
                    position_m = new[] { position.x, position.y, position.z },
                    orientation_xyzw = new[] {
                        orientation.x,
                        orientation.y,
                        orientation.z,
                        orientation.w,
                    },
                    tracking_valid = trackingValid,
                });

                previousOrientation = orientation;
            }

            float validFraction = validSampleCount / (float)TargetSampleCount;

            if (validFraction < MinimumTrackingValidFraction) {
                rejectionReason = "fewer than 95 percent of resampled poses have valid tracking";
                return false;
            }

            record = candidate;
            return true;
        }

        private static long TargetTimeNs(long windowStartNs, int sampleIndex) {
            double offset = sampleIndex * 1_000_000_000.0 / TargetSampleRateHz;
            return windowStartNs + (long)Math.Round(offset, MidpointRounding.AwayFromZero);
        }

        private static string ValidateMetadata(QuestTrialMetadata metadata) {
            if (metadata == null) {
                return "trial metadata is missing";
            }

            if (
                string.IsNullOrWhiteSpace(metadata.device_id) ||
                string.IsNullOrWhiteSpace(metadata.session_id) ||
                string.IsNullOrWhiteSpace(metadata.trial_id)
            ) {
                return "device, session, and trial ids are required";
            }

            if (!Splits.Contains(metadata.split)) {
                return "split must be train, validation, or test";
            }

            if (!Labels.Contains(metadata.label)) {
                return "label is not one of the five configured motion classes";
            }

            if (metadata.sequence_number < 0) {
                return "sequence number cannot be negative";
            }

            return null;
        }

        private static Quaternion Normalize(Quaternion value) {
            float magnitude = Mathf.Sqrt(
                value.x * value.x +
                value.y * value.y +
                value.z * value.z +
                value.w * value.w
            );

            if (magnitude < 0.000001f) {
                return Quaternion.identity;
            }

            return new Quaternion(
                value.x / magnitude,
                value.y / magnitude,
                value.z / magnitude,
                value.w / magnitude
            );
        }

        private static Quaternion Negate(Quaternion value) {
            return new Quaternion(-value.x, -value.y, -value.z, -value.w);
        }
    }
}
