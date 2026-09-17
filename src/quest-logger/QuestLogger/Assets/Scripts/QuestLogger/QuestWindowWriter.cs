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

        public string OutputPath => Path.Combine(
            Application.persistentDataPath,
            outputFolderName,
            outputFileName
        );

        public void WriteWindow(QuestWindowRecord record) {
            // this writes only after the complete window is accepted
            if (record == null) {
                throw new System.ArgumentNullException(nameof(record));
            }

            string directory = Path.GetDirectoryName(OutputPath);

            if (!string.IsNullOrEmpty(directory)) {
                Directory.CreateDirectory(directory);
            }

            string json = JsonUtility.ToJson(record, false);

            using (StreamWriter writer = new StreamWriter(OutputPath, true, new UTF8Encoding(false))) {
                writer.WriteLine(json);
            }

            Debug.Log("saved Quest window to " + OutputPath);
        }
    }
}
