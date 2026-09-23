// Wire 2.0 only. No decimal conversion, legacy redefinition, or session verifier.
using System;
using System.IO;
using System.Numerics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.RegularExpressions;

namespace PufSnn.QuestLogger {
    public sealed class BinaryWindowSample {
        public int sample_index;
        public long capture_time_ns;
        public float[] position_m;
        public float[] orientation_xyzw;
        public bool tracking_valid;
    }

    public sealed class BinaryWindow {
        public string device_id;
        public byte[] session_id;
        public ulong sequence_number;
        public string window_id;
        public long capture_start_ns;
        public long capture_end_ns;
        public BinaryWindowSample[] samples;
    }

    public static class BinaryWindowMessageWriter {
        [StructLayout(LayoutKind.Explicit)]
        private struct FloatWord {
            [FieldOffset(0)] public float Value;
            [FieldOffset(0)] public uint Word;
        }

        // Bit-copy only: no arithmetic that could flush subnormal values.
        public static uint FloatBits(float value) { return new FloatWord { Value = value }.Word; }
        public static float FromBits(uint word) { return new FloatWord { Word = word }.Value; }

        public static byte[] EncodeFloat(float value) {
            uint word = FloatBits(value);
            if ((word & 0x7f800000U) == 0x7f800000U) throw new InvalidDataException("invalid_payload_schema");
            if (word == 0x80000000U) word = 0;
            return new byte[] { (byte)(word >> 24), (byte)(word >> 16), (byte)(word >> 8), (byte)word };
        }

        public static float ParseFloat(byte[] bytes) {
            if (bytes == null || bytes.Length != 4) throw new InvalidDataException("invalid_payload_schema");
            uint word = ((uint)bytes[0] << 24) | ((uint)bytes[1] << 16) | ((uint)bytes[2] << 8) | bytes[3];
            if (word == 0x80000000U || (word & 0x7f800000U) == 0x7f800000U)
                throw new InvalidDataException("invalid_payload_schema");
            return FromBits(word);
        }

        private static void UInt(Stream output, ulong value, int width) {
            if (width < 8 && value >= (1UL << (width * 8))) throw new InvalidDataException("integer overflow");
            for (int shift = (width - 1) * 8; shift >= 0; shift -= 8) output.WriteByte((byte)(value >> shift));
        }

        private static void Bytes(Stream output, byte[] bytes) { output.Write(bytes, 0, bytes.Length); }
        private static void Id(Stream output, string value) {
            if (value == null || !Regex.IsMatch(value, @"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\z"))
                throw new InvalidDataException("malformed_message");
            byte[] bytes = Encoding.ASCII.GetBytes(value);
            UInt(output, (ulong)bytes.Length, 2); Bytes(output, bytes);
        }

        // All finite binary32 values as integers on a common 2^-149 grid.
        private static BigInteger Scaled(float value) {
            uint word = FloatBits(value);
            if ((word & 0x7f800000U) == 0x7f800000U) throw new InvalidDataException("invalid_payload_schema");
            int exponent = (int)((word >> 23) & 255);
            uint mantissa = word & 0x7fffff;
            if (exponent != 0) mantissa |= 0x800000;
            BigInteger result = new BigInteger(mantissa) << (exponent == 0 ? 0 : exponent - 1);
            return (word >> 31) == 0 ? result : -result;
        }

        public static byte[] BuildCanonicalProtectedBytes(BinaryWindow window) {
            if (window == null || window.session_id == null || window.session_id.Length != 16
                || window.capture_start_ns < 0 || window.capture_end_ns <= 0)
                throw new InvalidDataException("malformed_message");
            if (window.samples == null || window.samples.Length != 120)
                throw new InvalidDataException("invalid_payload_schema");
            if (window.capture_end_ns <= window.capture_start_ns
                || Math.Abs(window.capture_end_ns - window.capture_start_ns - 2000000000L) > 120)
                throw new InvalidDataException("data_quality_failure");
            int count = 0;
            long previousTime = -1;
            BigInteger[] previous = null;
            BigInteger unit = BigInteger.One << 149;
            using (MemoryStream payload = new MemoryStream()) {
                UInt(payload, 1, 1); UInt(payload, 60, 2);
                for (int i = 0; i < 120; i++) {
                    BinaryWindowSample sample = window.samples[i];
                    if (sample == null || sample.sample_index != i || sample.capture_time_ns < 0
                        || sample.position_m == null || sample.position_m.Length != 3
                        || sample.orientation_xyzw == null || sample.orientation_xyzw.Length != 4)
                        throw new InvalidDataException("invalid_payload_schema");
                    long time = sample.capture_time_ns;
                    if (time < window.capture_start_ns || time >= window.capture_end_ns
                        || (i > 0 && (time <= previousTime || time - previousTime > 50000000)))
                        throw new InvalidDataException("data_quality_failure");
                    BigInteger[] q = new BigInteger[4];
                    BigInteger norm = BigInteger.Zero, dot = BigInteger.Zero;
                    for (int j = 0; j < 4; j++) {
                        q[j] = Scaled(sample.orientation_xyzw[j]);
                        if (BigInteger.Abs(q[j]) * 1000000 > unit * 1000001)
                            throw new InvalidDataException("data_quality_failure");
                        norm += q[j] * q[j];
                        if (previous != null) dot += q[j] * previous[j];
                    }
                    if (norm * 100000000 < unit * unit * 99980001
                        || norm * 100000000 > unit * unit * 100020001
                        || (previous != null && dot.Sign < 0)) throw new InvalidDataException("data_quality_failure");
                    UInt(payload, (ulong)i, 2); UInt(payload, (ulong)time, 8);
                    foreach (float value in sample.position_m) Bytes(payload, EncodeFloat(value));
                    foreach (float value in sample.orientation_xyzw) Bytes(payload, EncodeFloat(value));
                    UInt(payload, sample.tracking_valid ? 1UL : 0UL, 1);
                    if (sample.tracking_valid) count++;
                    previous = q; previousTime = time;
                }
                if (count < 114) throw new InvalidDataException("data_quality_failure");
                int numerator = count * 1000000, ppm = numerator / 120, remainder = numerator % 120;
                if (remainder > 60 || (remainder == 60 && ppm % 2 == 1)) ppm++;
                using (MemoryStream output = new MemoryStream()) {
                    Bytes(output, Encoding.ASCII.GetBytes("P3AW"));
                    UInt(output, 2, 2); UInt(output, 0, 2); UInt(output, 2, 2); UInt(output, 0, 2);
                    UInt(output, 1, 2); UInt(output, 0, 2);
                    UInt(output, 1, 1); UInt(output, 1, 1); UInt(output, 32, 1);
                    Id(output, window.device_id); Bytes(output, window.session_id); UInt(output, window.sequence_number, 8);
                    Id(output, window.window_id);
                    UInt(output, (ulong)window.capture_start_ns, 8); UInt(output, (ulong)window.capture_end_ns, 8);
                    UInt(output, 1, 1); UInt(output, 120, 2); UInt(output, (ulong)count, 2); UInt(output, (ulong)ppm, 4);
                    UInt(output, 4683, 4); Bytes(output, payload.ToArray());
                    return output.ToArray();
                }
            }
        }
    }
}
