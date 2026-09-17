/*
this file tests the logger's fixed-grid output and its main data-quality rejection rules
the tests use artificial raw poses so they do not require a connected headset
*/

using System;
using System.Collections.Generic;
using NUnit.Framework;
using UnityEngine;

namespace PufSnn.QuestLogger.Tests {
    public sealed class QuestWindowProcessorTests {
        [Test]
        public void CreateWindowProduces120OrderedNormalizedSamples() {
            // this checks the normal accepted-window path
            List<RawHeadPoseSample> rawSamples = BuildRawSamples();

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out QuestWindowRecord record, out string rejectionReason);

            Assert.IsTrue(accepted, rejectionReason);
            Assert.AreEqual(120, record.samples.Count);
            Assert.AreEqual(record.window_start_ns + 2_000_000_000, record.window_end_ns);

            for (int index = 0; index < record.samples.Count; index++) {
                QuestWindowSample sample = record.samples[index];
                Assert.AreEqual(index, sample.sample_index);
                Assert.IsTrue(sample.tracking_valid);

                if (index > 0) {
                    Assert.Greater(
                        sample.capture_time_ns,
                        record.samples[index - 1].capture_time_ns
                    );
                }

                float[] quaternion = sample.orientation_xyzw;
                float norm = Mathf.Sqrt(
                    quaternion[0] * quaternion[0] +
                    quaternion[1] * quaternion[1] +
                    quaternion[2] * quaternion[2] +
                    quaternion[3] * quaternion[3]
                );

                Assert.That(norm, Is.EqualTo(1.0f).Within(0.0001f));

                if (index > 0) {
                    float[] previous = record.samples[index - 1].orientation_xyzw;
                    float dot =
                        quaternion[0] * previous[0] +
                        quaternion[1] * previous[1] +
                        quaternion[2] * previous[2] +
                        quaternion[3] * previous[3];

                    Assert.GreaterOrEqual(dot, 0.0f);
                }
            }
        }

        [Test]
        public void CreateWindowRejectsTimestampGapAbove50Milliseconds() {
            // this removes enough samples to create a gap above 50 ms
            List<RawHeadPoseSample> rawSamples = BuildRawSamples();
            rawSamples.RemoveRange(50, 4);

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out _, out string rejectionReason);

            Assert.IsFalse(accepted);
            StringAssert.Contains("50 ms", rejectionReason);
        }

        [Test]
        public void CreateWindowRejectsTrackingBelow95Percent() {
            // this marks enough poses invalid to fail the tracking limit
            List<RawHeadPoseSample> rawSamples = BuildRawSamples();

            for (int index = 0; index < rawSamples.Count; index += 5) {
                rawSamples[index].tracking_valid = false;
            }

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out _, out string rejectionReason);

            Assert.IsFalse(accepted);
            StringAssert.Contains("95 percent", rejectionReason);
        }

        private static List<RawHeadPoseSample> BuildRawSamples() {
            const long startTimeNs = 1_000_000_000;
            const int rawRateHz = 90;
            List<RawHeadPoseSample> samples = new List<RawHeadPoseSample>();

            for (int index = 0; index <= 180; index++) {
                long offsetNs = (long)Math.Round(
                    index * 1_000_000_000.0 / rawRateHz,
                    MidpointRounding.AwayFromZero
                );

                float timeSeconds = index / (float)rawRateHz;

                samples.Add(new RawHeadPoseSample {
                    capture_time_ns = startTimeNs + offsetNs,
                    position_m = new Vector3(0.01f * timeSeconds, 0.0f, 0.0f),
                    orientation_xyzw = Quaternion.Euler(0.0f, 20.0f * timeSeconds, 0.0f),
                    tracking_valid = true,
                });
            }

            return samples;
        }

        private static QuestTrialMetadata BuildMetadata() {
            return new QuestTrialMetadata {
                device_id = "quest-02",
                session_id = "quest-02-session-01",
                trial_id = "quest-02-session-01-nod-000",
                split = "train",
                label = "nod",
                sequence_number = 0,
            };
        }
    }
}
