using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEngine;

namespace PufSnn.QuestLogger {
    [Serializable] public sealed class AcceptedSourceVisitHeader {
        public string record_type = "accepted_source_plan";
        public string schema_version = "quest-accepted-source-visit-v2";
        public string purpose = "development_only";
        public string planned_acquisition_mode = "pc_hosted_quest_link";
        public string raw_retention = "accepted_source_development_only";
        public string participant_code, visit_code, device_id, session_id, processing_version;
        public string ledger_file_name, window_file_name, quality_file_name, source_directory_name;
    }

    [Serializable] public sealed class AcceptedSourceReceipt {
        public string record_type = "accepted_source";
        public string trial_id, file_name, file_sha256, window_id, window_line_sha256;
        public int byte_length;
    }

    [Serializable] public sealed class AcceptedSourceVisitEnd {
        public string record_type = "accepted_source_closed";
        public int accepted_source_count;
    }

    public interface IAcceptedSourceFileStore {
        void WriteNew(string fileName, byte[] bytes);
    }

    public sealed class AcceptedSourceFileStore : IAcceptedSourceFileStore {
        private readonly string directory;
        public AcceptedSourceFileStore(string directory) { this.directory = directory; }
        public void WriteNew(string fileName, byte[] bytes) {
            if (string.IsNullOrEmpty(fileName) || fileName != Path.GetFileName(fileName) ||
                fileName.IndexOfAny(new[] {'/', '\\', ':'}) >= 0 || fileName == "." || fileName == "..")
                throw new ArgumentException("Use a local source filename.");
            using (var file = new FileStream(Path.Combine(directory, fileName), FileMode.CreateNew, FileAccess.Write, FileShare.Read)) {
                file.Write(bytes, 0, bytes.Length);
                file.Flush(true);
            }
        }
    }

    // Development-only integration. No claim of study approval or completed device validation.
    // Source bytes are written only AFTER the accepted ledger entry has been flushed.
    public sealed class AcceptedSourceVisit : IDisposable {
        public const string Policy = "accepted_source_development_only";
        private readonly LedgerPlan plan;
        private readonly QuestTrialLedger ledger;
        private readonly ITrialLedgerStore manifest;
        private readonly IAcceptedSourceFileStore files;
        private readonly HashSet<string> saved = new HashSet<string>();
        private bool closed, disposed;
        public bool Faulted { get; private set; }

        public static bool ValidPolicy(string schema, string policy) =>
            (schema == "quest-trial-ledger-v1" && policy == "not_saved") ||
            (schema == "quest-trial-ledger-v2" && policy == Policy);

        public static void DeclareDevelopmentPolicy(LedgerPlan plan) {
            plan.schema_version = "quest-trial-ledger-v2";
            plan.raw_retention = Policy;
            QuestTrialLedger.ValidatePlan(plan);
        }

        public static void Preflight(string directory, LedgerPlan plan) {
            // Refuse all known visit evidence, even when retention is switched off.
            foreach (string path in new[] {Path.Combine(directory, plan.visit_code + "-accepted-source.jsonl"),
                Path.Combine(directory, plan.visit_code + "-accepted-source")})
                if (File.Exists(path) || Directory.Exists(path))
                    throw new IOException("Source evidence already exists; preserve it and use a new visit code.");
        }

        public static AcceptedSourceVisit Create(string directory, string ledgerName, LedgerPlan plan, QuestTrialLedger ledger) {
            QuestTrialLedger.ValidatePlan(plan);
            if (plan.schema_version != "quest-trial-ledger-v2") throw new ArgumentException("Declare source retention before creating any visit files.");
            Preflight(directory, plan);
            string sourceDirectory = Path.Combine(directory, plan.visit_code + "-accepted-source");
            Directory.CreateDirectory(sourceDirectory);
            return new AcceptedSourceVisit(new FileTrialLedgerStore(Path.Combine(directory, plan.visit_code + "-accepted-source.jsonl")),
                new AcceptedSourceFileStore(sourceDirectory), ledgerName, plan, ledger);
        }

        public AcceptedSourceVisit(ITrialLedgerStore manifest, IAcceptedSourceFileStore files,
            string ledgerName, LedgerPlan plan, QuestTrialLedger ledger) {
            this.manifest = manifest ?? throw new ArgumentNullException(nameof(manifest));
            try {
                QuestTrialLedger.ValidatePlan(plan);
                if (plan.schema_version != "quest-trial-ledger-v2" || ledger == null || ledger.Faulted || ledger.Closed || !ledger.MatchesPlan(plan))
                    throw new ArgumentException("An open v2 ledger is required.");
                if (string.IsNullOrWhiteSpace(ledgerName) || ledgerName != Path.GetFileName(ledgerName) || ledgerName.IndexOfAny(new[] {'/', '\\', ':'}) >= 0)
                    throw new ArgumentException("Use a local ledger filename.");
                this.plan = JsonUtility.FromJson<LedgerPlan>(JsonUtility.ToJson(plan));
                this.ledger = ledger;
                this.files = files ?? throw new ArgumentNullException(nameof(files));
                manifest.Append(JsonUtility.ToJson(new AcceptedSourceVisitHeader {
                    participant_code = plan.participant_code, visit_code = plan.visit_code,
                    device_id = plan.device_id, session_id = plan.session_id, processing_version = plan.processing_version,
                    ledger_file_name = ledgerName, window_file_name = plan.window_file_name,
                    quality_file_name = plan.visit_code + "-source-quality.jsonl",
                    source_directory_name = plan.visit_code + "-accepted-source"
                }));
            } catch { Faulted = true; manifest.Dispose(); throw; }
        }

        public void Accept(IReadOnlyList<RawHeadPoseSample> raw, QuestTrialMetadata metadata,
            QuestWindowRecord expected, Func<QuestWindowRecord, WindowWriteReceipt> writeWindow) {
            if (disposed || closed || Faulted) throw new InvalidOperationException("Source visit is unavailable.");
            try {
                if (metadata == null || writeWindow == null) throw new ArgumentException("Missing trial or window writer.");
                LedgerTrial trial = plan.trials.Find(t => t.trial_id == metadata.trial_id);
                if (trial == null || metadata.device_id != plan.device_id || metadata.session_id != plan.session_id ||
                    metadata.label != trial.prompted_task || metadata.sequence_number != trial.trial_index ||
                    saved.Contains(trial.trial_id) || ledger.Stage(trial.trial_id) != "completed")
                    throw new InvalidDataException("Source identity does not match the completed planned trial.");
                byte[] bytes = new UTF8Encoding(false, true).GetBytes(
                    AcceptedSourceCandidate.Serialize("accepted", raw, metadata, plan.processing_version, expected, true) + "\n");
                WindowWriteReceipt window = writeWindow(expected);
                if (window == null || window.file_name != plan.window_file_name || window.window_id != expected.window_id)
                    throw new InvalidDataException("Window writer returned a mismatched receipt.");
                ledger.Record(trial.trial_id, "accepted", receipt: window);
                string name = trial.trial_id + ".json";
                files.WriteNew(name, bytes);
                string hash;
                using (SHA256 sha = SHA256.Create())
                    hash = BitConverter.ToString(sha.ComputeHash(bytes)).Replace("-", "").ToLowerInvariant();
                manifest.Append(JsonUtility.ToJson(new AcceptedSourceReceipt {
                    trial_id = trial.trial_id, file_name = name, byte_length = bytes.Length, file_sha256 = hash,
                    window_id = window.window_id, window_line_sha256 = window.line_sha256
                }));
                saved.Add(trial.trial_id);
            } catch { Faulted = true; throw; }
        }

        public void Close() {
            if (disposed || closed || Faulted) throw new InvalidOperationException("Source visit cannot close.");
            try {
                if (ledger.Faulted || !ledger.Closed || !saved.SetEquals(plan.trials.Where(t => ledger.Stage(t.trial_id) == "accepted").Select(t => t.trial_id)))
                    throw new InvalidDataException("A complete ledger and matching source receipts are required.");
                manifest.Append(JsonUtility.ToJson(new AcceptedSourceVisitEnd {accepted_source_count = saved.Count}));
                closed = true;
            } catch { Faulted = true; throw; }
        }

        public void Dispose() {
            if (disposed) return;
            disposed = true;
            manifest.Dispose(); // Never invent completion during cleanup.
        }
    }
}
