/*
this file tests the logger's fixed-grid output and its main data-quality rejection rules
the tests use artificial raw poses so they do not require a connected headset
*/

using System;
using System.Collections.Generic;
using System.IO;
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

                if (index > 0)
                    Assert.Greater(sample.capture_time_ns, record.samples[index - 1].capture_time_ns);

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

        [Test]
        public void CreateWindowAcceptsExactly95PercentTracking() {
            List<RawHeadPoseSample> rawSamples = BuildRawSamplesAt60Hz();

            // this leaves exactly 114 out of 120 output samples valid
            for (int index = 114; index < 120; index++) {
                rawSamples[index].tracking_valid = false;
            }

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out QuestWindowRecord record, out string rejectionReason);

            Assert.IsTrue(accepted, rejectionReason);
            Assert.AreEqual(114, record.samples.FindAll(sample => sample.tracking_valid).Count);
        }

        [Test]
        public void CreateWindowNormalizesNonUnitQuaternionInput() {
            List<RawHeadPoseSample> rawSamples = BuildRawSamples();

            foreach (RawHeadPoseSample sample in rawSamples) {
                Quaternion value = sample.orientation_xyzw;
                sample.orientation_xyzw = new Quaternion(value.x * 3.0f, value.y * 3.0f, value.z * 3.0f, value.w * 3.0f);
            }

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out QuestWindowRecord record, out string rejectionReason);

            Assert.IsTrue(accepted, rejectionReason);

            foreach (QuestWindowSample sample in record.samples) {
                float[] value = sample.orientation_xyzw;
                float norm = Mathf.Sqrt(
                    value[0] * value[0] +
                    value[1] * value[1] +
                    value[2] * value[2] +
                    value[3] * value[3]
                );
                Assert.That(norm, Is.EqualTo(1.0f).Within(0.0001f));
            }
        }

        [Test]
        public void CreateWindowMakesEquivalentQuaternionSignsContinuous() {
            List<RawHeadPoseSample> rawSamples = BuildRawSamples();

            for (int index = 1; index < rawSamples.Count; index += 2) {
                Quaternion value = rawSamples[index].orientation_xyzw;
                rawSamples[index].orientation_xyzw = new Quaternion(-value.x, -value.y, -value.z, -value.w);
            }

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out QuestWindowRecord record, out string rejectionReason);

            Assert.IsTrue(accepted, rejectionReason);

            for (int index = 1; index < record.samples.Count; index++) {
                float[] previous = record.samples[index - 1].orientation_xyzw;
                float[] current = record.samples[index].orientation_xyzw;
                float dot =
                    previous[0] * current[0] +
                    previous[1] * current[1] +
                    previous[2] * current[2] +
                    previous[3] * current[3];
                Assert.GreaterOrEqual(dot, 0.0f);
            }
        }

        [Test]
        public void CreateWindowRejectsMissingOrZeroOrientation() {
            List<RawHeadPoseSample> rawSamples = BuildRawSamples();
            rawSamples[25].orientation_xyzw = new Quaternion(0.0f, 0.0f, 0.0f, 0.0f);

            bool accepted = QuestWindowProcessor.TryCreateWindow(rawSamples, BuildMetadata(), out _, out string rejectionReason);

            Assert.IsFalse(accepted);
            StringAssert.Contains("missing or zero orientation", rejectionReason);
        }

        [Test]
        public void WriterRejectsMalformedJsonlLine() {
            Assert.Throws<InvalidDataException>(() => QuestWindowWriter.DeserializeWindow("{ definitely-not-valid-json }"));
        }

        [Test]
        public void ArtificialStreamPassesQueueInterpolationJsonlAndReload() {
            RawPoseBuffer buffer = new RawPoseBuffer();

            foreach (RawHeadPoseSample sample in BuildRawSamples()) {
                buffer.Enqueue(sample);
            }

            List<RawHeadPoseSample> queuedSamples = buffer.Drain();
            bool accepted = QuestWindowProcessor.TryCreateWindow(queuedSamples, BuildMetadata(), out QuestWindowRecord expected, out string rejectionReason);
            Assert.IsTrue(accepted, rejectionReason);

            string outputPath = Path.Combine(Path.GetTempPath(), "puf-snn-logger-test-" + Guid.NewGuid().ToString("N") + ".jsonl");

            try {
                QuestWindowWriter.AppendWindow(outputPath, expected);
                string[] lines = File.ReadAllLines(outputPath);
                Assert.AreEqual(1, lines.Length);

                QuestWindowRecord actual = QuestWindowWriter.DeserializeWindow(lines[0]);
                Assert.AreEqual("0.2", actual.schema_version);
                Assert.AreEqual(expected.window_id, actual.window_id);
                Assert.AreEqual(expected.source_trial_id, actual.source_trial_id);
                Assert.AreEqual(expected.device_id, actual.device_id);
                Assert.AreEqual(expected.session_id, actual.session_id);
                Assert.AreEqual(expected.trial_id, actual.trial_id);
                Assert.AreEqual(expected.split, actual.split);
                Assert.AreEqual(expected.sequence_number, actual.sequence_number);
                Assert.AreEqual(expected.label, actual.label);
                Assert.AreEqual("unity_device_origin", actual.coordinate_frame);
                Assert.AreEqual(60, actual.target_sample_rate_hz);
                Assert.AreEqual(expected.window_start_ns, actual.window_start_ns);
                Assert.AreEqual(expected.window_end_ns, actual.window_end_ns);
                Assert.AreEqual(120, actual.samples.Count);

                for (int index = 0; index < actual.samples.Count; index++) {
                    Assert.AreEqual(index, actual.samples[index].sample_index);
                    Assert.AreEqual(expected.samples[index].capture_time_ns, actual.samples[index].capture_time_ns);
                    CollectionAssert.AreEqual(expected.samples[index].position_m, actual.samples[index].position_m);
                    CollectionAssert.AreEqual(expected.samples[index].orientation_xyzw, actual.samples[index].orientation_xyzw);
                    Assert.AreEqual(expected.samples[index].tracking_valid, actual.samples[index].tracking_valid);
                }
            } finally {
                if (File.Exists(outputPath))
                    File.Delete(outputPath);
            }
        }

        private static List<RawHeadPoseSample> BuildRawSamples() {
            const long startTimeNs = 1_000_000_000;
            const int rawRateHz = 90;
            List<RawHeadPoseSample> samples = new List<RawHeadPoseSample>();

            for (int index = 0; index <= 180; index++) {
                long offsetNs = (long)Math.Round(index * 1_000_000_000.0 / rawRateHz, MidpointRounding.AwayFromZero);

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

        private static List<RawHeadPoseSample> BuildRawSamplesAt60Hz() {
            const long startTimeNs = 1_000_000_000;
            const int rawRateHz = 60;
            List<RawHeadPoseSample> samples = new List<RawHeadPoseSample>();

            for (int index = 0; index < 120; index++) {
                long offsetNs = (long)Math.Round(index * 1_000_000_000.0 / rawRateHz, MidpointRounding.AwayFromZero);
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
