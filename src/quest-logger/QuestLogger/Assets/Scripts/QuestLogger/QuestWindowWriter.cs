/*
this file writes accepted Quest windows as one compact JSON object per line
the output stays in Unity's persistent data folder so Android can save it safely
*/

using System.IO;
using System.Text;
using UnityEngine;

namespace PufSnn.QuestLogger {
    public sealed class QuestWindowWriter : MonoBehaviour {
        [SerializeField] private string outputFolderName = "puf-snn";
        [SerializeField] private string outputFileName = "quest-windows.jsonl";

        public string OutputPath => Path.Combine(Application.persistentDataPath, outputFolderName, outputFileName);

        public void WriteWindow(QuestWindowRecord record) {
            AppendWindow(OutputPath, record);
            Debug.Log("saved Quest window to " + OutputPath);
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
            if (string.IsNullOrWhiteSpace(outputPath))
                throw new System.ArgumentException("an output path is required", nameof(outputPath));

            string directory = Path.GetDirectoryName(outputPath);

            if (!string.IsNullOrEmpty(directory))
                Directory.CreateDirectory(directory);

            string json = SerializeWindow(record);

            using (StreamWriter writer = new StreamWriter(outputPath, true, new UTF8Encoding(false))) {
                writer.WriteLine(json);
            }
        }
    }
}
