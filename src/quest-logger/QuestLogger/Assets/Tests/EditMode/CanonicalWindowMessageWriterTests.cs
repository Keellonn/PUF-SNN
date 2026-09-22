/*
this file checks that Unity creates the same canonical protected-message bytes as Python
the expected hash comes from the public test-only shared golden vector
*/

using System;
using System.Collections.Generic;
using System.IO;
using NUnit.Framework;

namespace PufSnn.QuestLogger.Tests {
    public sealed class CanonicalWindowMessageWriterTests {
        private const string ExpectedSha256 = "87c89fca1426ed031788192fbcee551e91036f5d72301da4a7d5137f63bfdf2d";

        [Test]
        public void CanonicalWriterMatchesPythonGoldenSha256() {
            QuestWindowRecord record = BuildGoldenWindow();

            byte[] canonicalBytes = CanonicalWindowMessageWriter.BuildCanonicalProtectedBytes(record);
            string sha256 = CanonicalWindowMessageWriter.CalculateCanonicalSha256(record);

            Assert.AreEqual(24_308, canonicalBytes.Length);
            Assert.AreEqual(ExpectedSha256, sha256);
        }

        [Test]
        public void CanonicalWriterAccepts114TrackingSamplesAndRejects113() {
            QuestWindowRecord accepted = BuildGoldenWindow();

            for (int index = 0; index < 6; index++) {
                accepted.samples[index].tracking_valid = false;
            }

            Assert.DoesNotThrow(() => CanonicalWindowMessageWriter.BuildCanonicalProtectedBytes(accepted));

            accepted.samples[6].tracking_valid = false;

            Assert.Throws<InvalidDataException>(() => CanonicalWindowMessageWriter.BuildCanonicalProtectedBytes(accepted));
        }

        [Test]
        public void CanonicalWriterRejectsNonfiniteMotionValues() {
            QuestWindowRecord record = BuildGoldenWindow();
            record.samples[0].position_m[0] = float.NaN;

            Assert.Throws<InvalidDataException>(() => CanonicalWindowMessageWriter.BuildCanonicalProtectedBytes(record));
        }

        [Test]
        public void ChangingProtectedMotionChangesCanonicalHash() {
            QuestWindowRecord original = BuildGoldenWindow();
            QuestWindowRecord altered = BuildGoldenWindow();
            altered.samples[0].position_m[0] = 0.1250001f;

            string originalHash = CanonicalWindowMessageWriter.CalculateCanonicalSha256(original);
            string alteredHash = CanonicalWindowMessageWriter.CalculateCanonicalSha256(altered);

            Assert.AreNotEqual(originalHash, alteredHash);
        }

        private static QuestWindowRecord BuildGoldenWindow() {
            const long startTimeNs = 1_000_000_000;
            QuestWindowRecord record = new QuestWindowRecord {
                schema_version = "0.2",
                window_id = "quest-02-session-01-nod-000-window-000",
                device_id = "quest-02",
                session_id = "quest-02-session-01",
                sequence_number = 0,
                coordinate_frame = "unity_device_origin",
                target_sample_rate_hz = 60,
                window_start_ns = startTimeNs,
                window_end_ns = 3_000_000_000,
                samples = new List<QuestWindowSample>(),
            };

            for (int sampleIndex = 0; sampleIndex < 120; sampleIndex++) {
                float[] position = { 0.0f, 0.0f, 0.0f };

                if (sampleIndex == 0)
                    position = new[] { 0.125f, -0.25f, 0.0f };

                record.samples.Add(
                    new QuestWindowSample {
                        sample_index = sampleIndex,
                        capture_time_ns = startTimeNs + sampleIndex * 16_666_667L,
                        position_m = position,
                        orientation_xyzw = new[] { 0.0f, 0.0f, 0.0f, 1.0f },
                        tracking_valid = true,
                    }
                );
            }

            return record;
        }
    }
}
