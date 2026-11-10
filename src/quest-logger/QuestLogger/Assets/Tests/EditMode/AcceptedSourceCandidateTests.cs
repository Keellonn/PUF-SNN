using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.XR;

namespace PufSnn.QuestLogger.Tests {
    public sealed class AcceptedSourceCandidateTests {
        private string root;
        [SetUp] public void Setup() {
            root = Path.Combine(Path.GetTempPath(), "puf-snn-accepted-source-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(root);
        }
        [TearDown] public void Cleanup() {
            string prefix = Path.Combine(Path.GetFullPath(Path.GetTempPath()), "puf-snn-accepted-source-");
            Assert.True(Path.GetFullPath(root).StartsWith(prefix, StringComparison.OrdinalIgnoreCase));
            Directory.Delete(root, true);
        }
        private static QuestTrialMetadata Metadata() => new QuestTrialMetadata {
            device_id = "synthetic-device", session_id = "synthetic-session", trial_id = "synthetic-trial",
            split = "validation", label = "nod", sequence_number = 0
        };
        private static List<RawHeadPoseSample> Source(int seed = 20261103) {
            var random = new System.Random(seed);
            return Enumerable.Range(0, 181).Select(i => new RawHeadPoseSample {
                capture_time_ns = (long)Math.Round(i * 1_000_000_000.0 / 90) + (i == 0 || i == 180 ? 0 : random.Next(-100000, 100001)),
                position_m = new Vector3((float)random.NextDouble(), (float)random.NextDouble(), (float)random.NextDouble()),
                orientation_xyzw = Quaternion.Euler(i * 0.03f, i * 0.01f, 0), tracking_valid = i != 40,
                tracking_flag_available = i != 30, tracking_state_available = i != 31,
                tracking_state = InputTrackingState.Position | InputTrackingState.Rotation
            }).ToList();
        }
        private static QuestWindowRecord Window(List<RawHeadPoseSample> raw) {
            Assert.True(QuestWindowProcessor.TryCreateWindow(raw, Metadata(), out var window, out var reason), reason);
            return window;
        }
        [Test] public void SavedSourceReproducesWindowAndSummaryForTwentySyntheticSeeds() {
            for (int seed = 0; seed < 20; seed++) {
                var raw = Source(seed); var expected = Window(raw);
                string json = AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", expected);
                var replay = AcceptedSourceCandidate.Replay(json, out var metrics);
                Assert.AreEqual(QuestWindowWriter.SerializeWindow(expected), QuestWindowWriter.SerializeWindow(replay));
                Assert.AreEqual(JsonUtility.ToJson(SourceQualityMetrics.Measure(raw)), JsonUtility.ToJson(metrics));
                var restored = JsonUtility.FromJson<AcceptedSourceRecord>(json);
                Assert.AreEqual(AcceptedSourceCandidate.Bits(raw[20].position_m.x), restored.samples[20].position_m_float32_bits[0]);
            }
        }
        [Test] public void AllRetainedFieldsAndProcessedFloatBitsMatchAcrossTwentySeeds() {
            for (int seed = 0; seed < 20; seed++) {
                var raw = Source(seed); var expected = Window(raw);
                string json = AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", expected);
                var saved = JsonUtility.FromJson<AcceptedSourceRecord>(json);
                var replay = AcceptedSourceCandidate.Replay(json, out var metrics);
                Assert.AreEqual(raw.Count, saved.samples.Count);
                for (int i = 0; i < raw.Count; i++) {
                    var before = raw[i]; var after = saved.samples[i];
                    Assert.AreEqual(before.capture_time_ns, after.capture_time_ns);
                    CollectionAssert.AreEqual(new[] { AcceptedSourceCandidate.Bits(before.position_m.x), AcceptedSourceCandidate.Bits(before.position_m.y), AcceptedSourceCandidate.Bits(before.position_m.z) }, after.position_m_float32_bits);
                    CollectionAssert.AreEqual(new[] { AcceptedSourceCandidate.Bits(before.orientation_xyzw.x), AcceptedSourceCandidate.Bits(before.orientation_xyzw.y), AcceptedSourceCandidate.Bits(before.orientation_xyzw.z), AcceptedSourceCandidate.Bits(before.orientation_xyzw.w) }, after.orientation_xyzw_float32_bits);
                    Assert.AreEqual(before.tracking_valid, after.tracking_valid);
                    Assert.AreEqual((int)before.tracking_state, after.tracking_state);
                    Assert.AreEqual(before.tracking_flag_available, after.tracking_flag_available);
                    Assert.AreEqual(before.tracking_state_available, after.tracking_state_available);
                }
                Assert.AreEqual(expected.samples.Count, replay.samples.Count);
                for (int i = 0; i < expected.samples.Count; i++) {
                    var a = expected.samples[i]; var b = replay.samples[i];
                    Assert.AreEqual(a.sample_index, b.sample_index); Assert.AreEqual(a.capture_time_ns, b.capture_time_ns);
                    Assert.AreEqual(a.tracking_valid, b.tracking_valid);
                    CollectionAssert.AreEqual(a.position_m.Select(AcceptedSourceCandidate.Bits).ToArray(), b.position_m.Select(AcceptedSourceCandidate.Bits).ToArray());
                    CollectionAssert.AreEqual(a.orientation_xyzw.Select(AcceptedSourceCandidate.Bits).ToArray(), b.orientation_xyzw.Select(AcceptedSourceCandidate.Bits).ToArray());
                }
                var originalMetrics = SourceQualityMetrics.Measure(raw);
                foreach (var field in typeof(SourceQualityMetrics).GetFields()) {
                    if (field.FieldType == typeof(double))
                        Assert.AreEqual(BitConverter.DoubleToInt64Bits((double)field.GetValue(originalMetrics)), BitConverter.DoubleToInt64Bits((double)field.GetValue(metrics)), field.Name);
                    else Assert.AreEqual(field.GetValue(originalMetrics), field.GetValue(metrics), field.Name);
                }
                Assert.AreEqual(QuestWindowWriter.SerializeWindow(expected), QuestWindowWriter.SerializeWindow(replay));
            }
        }

        [TestCase("rejected")] [TestCase("stopped")] [TestCase("processing_failed")]
        public void RefusedOutcomesCreateNoMotionFile(string outcome) {
            string path = Path.Combine(root, "source.json"); var raw = Source();
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.ExportNew(path, outcome, raw, Metadata(), "synthetic-v1", Window(raw)));
            Assert.False(File.Exists(path));
        }
        [Test] public void QualityRefusalCannotBeExportedAsAccepted() {
            var raw = Source(); var expected = Window(raw); raw.RemoveRange(20, 10);
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", expected));
        }
        [Test] public void ChangedProcessedWindowDoesNotPassSourceLinkCheck() {
            var raw = Source(); var expected = Window(raw); expected.samples[0].position_m[0] += 1;
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", expected));
        }
        [Test] public void ExistingSourceFileIsNeverOverwritten() {
            var raw = Source(); string path = Path.Combine(root, "source.json");
            AcceptedSourceCandidate.ExportNew(path, "accepted", raw, Metadata(), "synthetic-v1", Window(raw));
            byte[] before = File.ReadAllBytes(path);
            Assert.Throws<IOException>(() => AcceptedSourceCandidate.ExportNew(path, "accepted", raw, Metadata(), "synthetic-v1", Window(raw)));
            CollectionAssert.AreEqual(before, File.ReadAllBytes(path));
        }
        [Test] public void NonfinitePoseAndInvalidTrackingBitsAreRefused() {
            var raw = Source(); var expected = Window(raw);
            raw[5].position_m = new Vector3(float.NaN, 0, 0);
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", expected));
            raw = Source(); raw[5].tracking_state = (InputTrackingState)128;
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", expected));
        }
        [Test] public void EditedRecordWithBadTimestampOrEncodingCannotReplay() {
            var raw = Source(); string json = AcceptedSourceCandidate.Serialize("accepted", raw, Metadata(), "synthetic-v1", Window(raw));
            var record = JsonUtility.FromJson<AcceptedSourceRecord>(json); record.samples[2].capture_time_ns = record.samples[1].capture_time_ns;
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.Replay(JsonUtility.ToJson(record), out _));
            record = JsonUtility.FromJson<AcceptedSourceRecord>(json); record.numeric_encoding = "decimal";
            Assert.Throws<InvalidDataException>(() => AcceptedSourceCandidate.Replay(JsonUtility.ToJson(record), out _));
        }
        [Test] public void FloatBitsPreserveSignedZeroAndSmallValues() {
            foreach (int bits in new[] {0, int.MinValue, 1, -1082130432, 0x3f800001, 0x00800000})
                Assert.AreEqual(bits, AcceptedSourceCandidate.Bits(AcceptedSourceCandidate.FromBits(bits)));
        }
        [Test] public void ExportNativeSyntheticReplayFixture() {
            var raw = Source(); var window = Window(raw);
            string[] args = Environment.GetCommandLineArgs(); int index = Array.IndexOf(args, "-pufAcceptedSourceFixtureRoot");
            if (index < 0 || index + 1 >= args.Length) return;
            string target = args[index + 1]; Directory.CreateDirectory(target);
            AcceptedSourceCandidate.ExportNew(Path.Combine(target, "accepted-source.json"), "accepted", raw, Metadata(), "synthetic-source-candidate-20261103", window);
            QuestWindowWriter.AppendWindowWithReceipt(Path.Combine(target, "windows.jsonl"), window);
            File.WriteAllText(Path.Combine(target, "source-metrics.json"), JsonUtility.ToJson(SourceQualityMetrics.Measure(raw)) + "\n", new System.Text.UTF8Encoding(false));
        }
    }
}
