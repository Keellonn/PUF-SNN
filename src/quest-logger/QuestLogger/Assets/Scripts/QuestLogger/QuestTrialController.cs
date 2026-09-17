/*
this file runs the prompt, capture, and rest phases for the five head-motion labels
recording stays disabled until the authorized-recording box is explicitly enabled
*/

using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace PufSnn.QuestLogger {
    public sealed class QuestTrialController : MonoBehaviour {
        [SerializeField] private HeadPoseCapture headPoseCapture;
        [SerializeField] private QuestWindowWriter windowWriter;
        [SerializeField] private TextMesh promptText;
        [SerializeField] private bool recordingAuthorized;
        [SerializeField] private bool startOnPlay;
        [SerializeField] private string deviceId = "quest-02";
        [SerializeField] private string sessionId = "quest-02-session-01";
        [SerializeField] private string split = "train";
        [SerializeField] private int trialsPerClass = 1;
        [SerializeField] private int randomSeed = 2026;
        [SerializeField] private float promptSeconds = 1.0f;
        [SerializeField] private float actionSeconds = 2.0f;
        [SerializeField] private float restSeconds = 1.0f;

        private static readonly string[] Labels = {
            "nod",
            "shake",
            "look_left_return",
            "look_right_return",
            "still",
        };

        private Coroutine sessionRoutine;

        private void Start() {
            if (startOnPlay) {
                StartTrialSession();
            }
        }

        public void StartTrialSession() {
            if (sessionRoutine != null) {
                Debug.LogWarning("a Quest logger session is already running");
                return;
            }

            if (!recordingAuthorized) {
                Debug.LogWarning("recording is disabled until the approved-recording box is enabled");
                return;
            }

            if (headPoseCapture == null || windowWriter == null) {
                Debug.LogError("assign HeadPoseCapture and QuestWindowWriter before starting");
                return;
            }

            sessionRoutine = StartCoroutine(RunSession());
        }

        public void StopTrialSession() {
            if (sessionRoutine != null) {
                StopCoroutine(sessionRoutine);
                sessionRoutine = null;
            }

            if (headPoseCapture != null && headPoseCapture.CaptureActive) {
                headPoseCapture.StopCapture();
            }

            Debug.Log("Quest logger session stopped");
        }

        private IEnumerator RunSession() {
            // this runs every label through prompt, capture, and rest
            List<string> schedule = BuildSchedule();

            for (int sequenceNumber = 0; sequenceNumber < schedule.Count; sequenceNumber++) {
                string label = schedule[sequenceNumber];
                ShowPrompt("prepare: " + label);
                yield return new WaitForSecondsRealtime(promptSeconds);

                ShowPrompt("record: " + label);
                headPoseCapture.BeginCapture();
                yield return new WaitForSecondsRealtime(actionSeconds);
                List<RawHeadPoseSample> rawSamples = headPoseCapture.StopCapture();

                string trialId = string.Format("{0}-{1}-{2:D3}", sessionId, label, sequenceNumber);

                QuestTrialMetadata metadata = new QuestTrialMetadata {
                    device_id = deviceId,
                    session_id = sessionId,
                    trial_id = trialId,
                    split = split,
                    label = label,
                    sequence_number = sequenceNumber,
                };

                if (QuestWindowProcessor.TryCreateWindow(rawSamples, metadata, out QuestWindowRecord record, out string rejectionReason)) {
                    windowWriter.WriteWindow(record);
                } else {
                    Debug.LogWarning("rejected " + trialId + ": " + rejectionReason);
                }

                ShowPrompt("rest");
                yield return new WaitForSecondsRealtime(restSeconds);
            }

            sessionRoutine = null;
            ShowPrompt("session complete");
        }

        private List<string> BuildSchedule() {
            // this creates a repeatable shuffled label order
            List<string> schedule = new List<string>();

            for (int repetition = 0; repetition < trialsPerClass; repetition++) {
                schedule.AddRange(Labels);
            }

            System.Random random = new System.Random(randomSeed);

            for (int index = schedule.Count - 1; index > 0; index--) {
                int replacementIndex = random.Next(index + 1);
                string current = schedule[index];
                schedule[index] = schedule[replacementIndex];
                schedule[replacementIndex] = current;
            }

            return schedule;
        }

        private void ShowPrompt(string message) {
            if (promptText != null) {
                promptText.text = message;
            }

            Debug.Log(message);
        }
    }
}
