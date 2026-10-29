/*
this file runs the prompt, capture, and rest phases for the five head-motion labels
recording stays disabled until the authorized-recording box is explicitly enabled
*/

using System.Collections;
using System.Collections.Generic;
using System.IO;
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
        [SerializeField] private string participantCode = "";
        [SerializeField] private string visitCode = "";
        [SerializeField] private string processingVersion = "";
        [SerializeField] private int blockCount = 1;
        [SerializeField] private int maximumScheduledTrials = 75;
        [SerializeField] private float maximumSessionSeconds = 1800.0f;
        [SerializeField] private int trialsPerClass = 1;
        [SerializeField] private int randomSeed = 2026;
        [SerializeField] private float promptSeconds = 1.0f;
        [SerializeField] private float actionSeconds = 2.0f;
        [SerializeField] private float restSeconds = 1.0f;

        public bool RecordingEnabled => recordingAuthorized;
        public bool SessionRunning => sessionRoutine != null || ledger != null;
        public string CurrentPrompt { get; private set; } = "Recording off";
        public event System.Action<string> PromptChanged;

        public void SetRecordingEnabled(bool enabled) {
            if (!enabled) StopWithReason("recording_disarmed");
            recordingAuthorized = enabled;
        }

        public void ConfigureVisit(string participant, string visit, string device,
            string session, string version, string dataSplit) {
            if (SessionRunning) throw new System.InvalidOperationException("Stop the current visit before changing identifiers.");
            if (dataSplit != "train" && dataSplit != "validation" && dataSplit != "test")
                throw new System.ArgumentException("Use train, validation or test as the split.");
            QuestTrialLedger.BuildPlan(participant, visit, device, session, version,
                blockCount, trialsPerClass, randomSeed, maximumScheduledTrials);
            participantCode = participant; visitCode = visit; deviceId = device;
            sessionId = session; processingVersion = version; split = dataSplit;
        }

        private Coroutine sessionRoutine;
        private QuestTrialLedger ledger;
        private SourceQualityWriter sourceQuality;
        private bool capturePending;
        private LedgerPlan plan;
        private string activeTrialId = "";
        private string endReason = "schedule_finished";
        private bool skipRequested;
        private bool continueRequested;
        private long sessionStart;

        private void OnDisable() { StopWithReason("component_disabled"); }
        private void OnApplicationQuit() { StopWithReason("application_quit"); }
        private void OnApplicationPause(bool paused) { if (paused) StopWithReason("application_paused"); }

        private void Start() {
            if (startOnPlay) {
                StartTrialSession();
            }
        }

        public void StartTrialSession() {
            if (sessionRoutine != null || ledger != null) {
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

            try {
                if (actionSeconds != 2.0f || promptSeconds <= 0 || restSeconds < 0 ||
                    !IsFinite(promptSeconds) || !IsFinite(restSeconds) ||
                    !IsFinite(maximumSessionSeconds) || maximumSessionSeconds <= 0)
                    throw new System.ArgumentException("Use a two-second action and finite, valid timing limits.");
                plan = QuestTrialLedger.BuildPlan(participantCode, visitCode, deviceId, sessionId,
                    processingVersion, blockCount, trialsPerClass, randomSeed, maximumScheduledTrials);
                windowWriter.PrepareVisit(visitCode);
                plan.window_file_name = Path.GetFileName(windowWriter.OutputPath);
                string path = Path.Combine(Path.GetDirectoryName(windowWriter.OutputPath), visitCode + "-trials.jsonl");
                string qualityPath = Path.Combine(Path.GetDirectoryName(windowWriter.OutputPath), visitCode + "-source-quality.jsonl");
                if (File.Exists(path) || File.Exists(qualityPath))
                    throw new IOException("This visit already has evidence files; preserve them and use a new visit code.");
                ledger = QuestTrialLedger.Create(path, plan, () => headPoseCapture.ElapsedNanoseconds);
                sourceQuality = SourceQualityWriter.Create(qualityPath, Path.GetFileName(path), plan,
                    () => headPoseCapture.ElapsedNanoseconds);
                capturePending = false;
                sessionStart = headPoseCapture.ElapsedNanoseconds;
                endReason = "schedule_finished";
                sessionRoutine = StartCoroutine(RunSession());
            } catch (System.Exception error) {
                endReason = "setup_failed";
                FinishVisit();
                Debug.LogError("Logger setup refused: " + error.Message);
            }
        }

        public void StopTrialSession() {
            StopWithReason("operator_stop");
        }

        private void StopWithReason(string reason) {
            if (sessionRoutine == null && ledger == null) return;
            endReason = reason;
            if (sessionRoutine != null) {
                StopCoroutine(sessionRoutine);
                sessionRoutine = null;
            }

            FinishVisit();
            Debug.Log("Quest logger session stopped");
        }

        private IEnumerator RunSession() {
            try {
                int currentBlock = plan.trials[0].block_index;
                foreach (LedgerTrial trial in plan.trials) {
                    if (trial.block_index != currentBlock) {
                        activeTrialId = "";
                        continueRequested = false;
                        ShowPrompt("break: continue when comfortable");
                        while (!Expired && !continueRequested) yield return null;
                        currentBlock = trial.block_index;
                    }
                    if (Expired) { endReason = "session_time_limit"; break; }
                    activeTrialId = trial.trial_id;
                    skipRequested = false;
                    if (!TryRecord("prompted")) yield break;
                    ShowPrompt("prepare: " + trial.prompted_task);
                    long start = headPoseCapture.ElapsedNanoseconds;
                    while (!Expired && !skipRequested && headPoseCapture.ElapsedNanoseconds - start < promptSeconds * 1_000_000_000.0)
                        yield return null;
                    if (Expired) { endReason = "session_time_limit"; break; }
                    if (skipRequested) {
                        if (!TryRecord("skipped", "participant_skip")) yield break;
                        continue;
                    }
                    ShowPrompt("record: " + trial.prompted_task);
                    // Persist intent before capture; an unconfirmed intent remains uncertain.
                    if (!TryRecord("start_requested")) yield break;
                    bool began = false;
                    try { headPoseCapture.BeginCapture(); capturePending = true; began = true; }
                    catch (System.Exception error) { Debug.LogError("Capture start failed: " + error.Message); }
                    if (!began) { endReason = "capture_start_failed"; yield break; }
                    if (!TryRecord("recording_started")) yield break;
                    start = headPoseCapture.ElapsedNanoseconds;
                    while (!Expired && !skipRequested && headPoseCapture.ElapsedNanoseconds - start < actionSeconds * 1_000_000_000.0)
                        yield return null;
                    List<RawHeadPoseSample> raw = headPoseCapture.StopCapture();
                    capturePending = false;
                    if (Expired || skipRequested) {
                        string reason = Expired ? "session_time_limit" : "participant_skip_during_recording";
                        bool savedQuality = TrySaveSource("stopped", reason, raw);
                        if (!TryRecord("stopped", reason) || !savedQuality) yield break;
                        if (Expired) { endReason = "session_time_limit"; break; }
                    } else {
                        bool savedQuality = TrySaveSource("completed", "capture_completed", raw);
                        if (!TryRecord("completed", rawSampleCount: raw.Count)) yield break;
                        if (!savedQuality) {
                            TryRecord("processing_failed", "source_quality_write_failed");
                            yield break;
                        }
                        if (!ProcessAndSave(trial, raw)) yield break;
                    }
                    ShowPrompt("rest");
                    start = headPoseCapture.ElapsedNanoseconds;
                    while (!Expired && headPoseCapture.ElapsedNanoseconds - start < restSeconds * 1_000_000_000.0)
                        yield return null;
                }
                if (Expired) endReason = "session_time_limit";
                ShowPrompt("session ended");
            } finally { FinishVisit(); }
        }

        public void SkipCurrentTrial() { if (!string.IsNullOrEmpty(activeTrialId)) skipRequested = true; }
        public void ContinueAfterBreak() { continueRequested = true; }

        public void LogExecutionNote(string reasonCode) {
            if (ledger == null || string.IsNullOrEmpty(activeTrialId)) return;
            try { ledger.Record(activeTrialId, "execution_note", reasonCode); }
            catch (System.Exception error) {
                Debug.LogWarning("Execution note refused: " + error.Message);
                if (ledger != null && ledger.Faulted) StopWithReason("ledger_unavailable");
            }
        }

        private bool Expired => headPoseCapture.ElapsedNanoseconds - sessionStart >= maximumSessionSeconds * 1_000_000_000.0;
        private static bool IsFinite(float value) { return !float.IsNaN(value) && !float.IsInfinity(value); }

        private bool ProcessAndSave(LedgerTrial trial, List<RawHeadPoseSample> raw) {
            QuestTrialMetadata metadata = new QuestTrialMetadata {
                device_id = deviceId, session_id = sessionId, trial_id = trial.trial_id,
                split = split, label = trial.prompted_task, sequence_number = trial.trial_index
            };
            try {
                if (QuestWindowProcessor.TryCreateWindow(raw, metadata, out QuestWindowRecord record, out string reason))
                    return TryRecord("accepted", receipt: windowWriter.WriteWindowWithReceipt(record));
                return TryRecord("rejected", RejectionCode(reason));
            } catch (System.Exception error) {
                endReason = "processing_or_window_write_failed";
                if (ledger != null && !ledger.Faulted) TryRecord("processing_failed", endReason);
                Debug.LogError("Processing stopped: " + error.Message);
                return false;
            }
        }

        private bool TryRecord(string type, string reason = "", int rawSampleCount = -1, WindowWriteReceipt receipt = null) {
            try { ledger.Record(activeTrialId, type, reason, rawSampleCount, receipt); return true; }
            catch (System.Exception error) {
                endReason = "ledger_unavailable";
                Debug.LogError("Ledger unavailable; recording stops: " + error.Message);
                return false;
            }
        }

        private void FinishVisit() {
            if (headPoseCapture != null && (capturePending || headPoseCapture.CaptureActive)) {
                List<RawHeadPoseSample> raw = headPoseCapture.StopCapture();
                capturePending = false;
                if (sourceQuality != null && !sourceQuality.Faulted && !string.IsNullOrEmpty(activeTrialId))
                    TrySaveSource("stopped", endReason, raw);
            }
            if (ledger != null && sourceQuality != null && !sourceQuality.Faulted &&
                !string.IsNullOrEmpty(activeTrialId) && !sourceQuality.HasTrial(activeTrialId) &&
                ledger.Stage(activeTrialId) == "start_requested")
                TrySaveSource("unconfirmed", "capture_start_unconfirmed", null);
            QuestTrialLedger finishing = ledger;
            SourceQualityWriter finishingQuality = sourceQuality;
            ledger = null;
            sourceQuality = null;
            sessionRoutine = null;
            activeTrialId = "";
            if (finishing == null) { if (finishingQuality != null) finishingQuality.Dispose(); return; }
            try { if (!finishing.Faulted && !finishing.Closed) finishing.EndVisit(endReason); }
            catch (System.Exception error) { Debug.LogError("Visit remains incomplete: " + error.Message); }
            finally { finishing.Dispose(); if (finishingQuality != null) finishingQuality.Dispose(); }
        }

        private bool TrySaveSource(string stage, string reason, List<RawHeadPoseSample> raw) {
            try {
                if (sourceQuality == null) throw new IOException("Source-quality writer was not created.");
                sourceQuality.Write(activeTrialId, stage, reason, raw);
                return true;
            } catch (System.Exception error) {
                endReason = "source_quality_write_failed";
                Debug.LogError("Source-quality evidence unavailable; recording stops: " + error.Message);
                return false;
            }
        }

        private static string RejectionCode(string reason) {
            switch (reason) {
                case "the trial contains fewer than two raw samples": return "too_few_source_samples";
                case "raw timestamps are not strictly increasing": return "source_timestamp_order";
                case "a raw timestamp gap exceeds 50 ms": return "source_gap_over_limit";
                case "raw samples do not cover the final 60 Hz target time": return "source_time_coverage";
                case "a raw pose contains a non-finite position or orientation": return "nonfinite_source_pose";
                case "a raw pose has a missing or zero orientation": return "invalid_source_orientation";
                case "fewer than 95 percent of resampled poses have valid tracking": return "tracking_coverage";
                default: return "window_processor_refusal";
            }
        }

        private void ShowPrompt(string message) {
            CurrentPrompt = message;
            PromptChanged?.Invoke(message);
            if (promptText != null) {
                promptText.text = message;
            }

            Debug.Log(message);
        }
    }
}
