/*
this file writes accepted Quest windows as one compact JSON object per line
the output stays in Unity's persistent data folder so Android can save it safely
*/

using System.IO;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace PufSnn.QuestLogger {
    [System.Serializable]
    public sealed class WindowWriteReceipt {
        public string file_name;
        public string window_id;
        public string line_sha256;
        public long file_offset;
        public int line_length;
    }

    public sealed class QuestWindowWriter : MonoBehaviour {
        [SerializeField] private string outputFolderName = "puf-snn";
        [SerializeField] private string outputFileName = "quest-windows.jsonl";

        public string OutputPath => Path.Combine(Application.persistentDataPath, outputFolderName, outputFileName);

        public void PrepareVisit(string visitCode) {
            if (string.IsNullOrWhiteSpace(visitCode) || !System.Text.RegularExpressions.Regex.IsMatch(visitCode, @"\A[A-Za-z0-9][A-Za-z0-9_-]{0,127}\z"))
                throw new System.ArgumentException("Use a coded visit identifier.");
            outputFileName = visitCode + "-windows.jsonl";
            if (File.Exists(OutputPath)) throw new IOException("This visit's window file already exists; preserve it and use a new visit code.");
        }

        public void WriteWindow(QuestWindowRecord record) {
            AppendWindow(OutputPath, record);
            Debug.Log("saved Quest window to " + OutputPath);
        }

        public WindowWriteReceipt WriteWindowWithReceipt(QuestWindowRecord record) {
            return AppendWindowWithReceipt(OutputPath, record);
        }

        public static string SerializeWindow(QuestWindowRecord record) {
            if (record == null)
                throw new System.ArgumentNullException(nameof(record));

            return JsonUtility.ToJson(record, false);
        }

        public static QuestWindowRecord DeserializeWindow(string json) {
            if (string.IsNullOrWhiteSpace(json))
                throw new InvalidDataException("the JSONL line is empty");

            QuestWindowRecord record;

            try {
                record = JsonUtility.FromJson<QuestWindowRecord>(json);
            } catch (System.Exception error) {
                throw new InvalidDataException("the JSONL line is malformed", error);
            }

            if (
                record == null ||
                string.IsNullOrWhiteSpace(record.window_id) ||
                string.IsNullOrWhiteSpace(record.device_id) ||
                string.IsNullOrWhiteSpace(record.session_id) ||
                string.IsNullOrWhiteSpace(record.trial_id) ||
                string.IsNullOrWhiteSpace(record.label) ||
                record.samples == null ||
                record.samples.Count != QuestWindowProcessor.TargetSampleCount
            )
                throw new InvalidDataException("the JSONL line is missing required window fields");

            return record;
        }

        public static void AppendWindow(string outputPath, QuestWindowRecord record) {
            AppendWindowWithReceipt(outputPath, record);
        }

        public static WindowWriteReceipt AppendWindowWithReceipt(string outputPath, QuestWindowRecord record) {
            if (string.IsNullOrWhiteSpace(outputPath))
                throw new System.ArgumentException("an output path is required", nameof(outputPath));

            string directory = Path.GetDirectoryName(outputPath);

            if (!string.IsNullOrEmpty(directory))
                Directory.CreateDirectory(directory);

            string json = SerializeWindow(record);

            byte[] bytes = new UTF8Encoding(false, true).GetBytes(json + "\n");
            long offset;
            using (FileStream stream = new FileStream(outputPath, FileMode.OpenOrCreate, FileAccess.ReadWrite, FileShare.Read)) {
                if (stream.Length > 0) {
                    stream.Seek(-1, SeekOrigin.End);
                    if (stream.ReadByte() != '\n')
                        throw new InvalidDataException("The window file has an incomplete final line; preserve it and use a new file.");
                }
                offset = stream.Seek(0, SeekOrigin.End);
                stream.Write(bytes, 0, bytes.Length);
                stream.Flush(true);
            }
            string hash;
            using (SHA256 sha = SHA256.Create())
                hash = System.BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
            return new WindowWriteReceipt {
                file_name = Path.GetFileName(outputPath), window_id = record.window_id,
                line_sha256 = hash, file_offset = offset, line_length = bytes.Length
            };
        }
    }
}
