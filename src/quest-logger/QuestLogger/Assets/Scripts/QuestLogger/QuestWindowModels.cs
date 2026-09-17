/*
this file defines the captured Unity samples and the final Quest window JSON fields
the exported classes match schemas/quest-window.schema.json
*/

using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;

namespace PufSnn.QuestLogger {
    [Serializable]
    public sealed class RawHeadPoseSample {
        public long capture_time_ns;
        public Vector3 position_m;
        public Quaternion orientation_xyzw;
        public bool tracking_valid;
        public InputTrackingState tracking_state;
    }

    [Serializable]
    public sealed class QuestWindowSample {
        public int sample_index;
        public long capture_time_ns;
        public float[] position_m;
        public float[] orientation_xyzw;
        public bool tracking_valid;
    }

    [Serializable]
    public sealed class QuestWindowRecord {
        public string schema_version = "0.2";
        public string window_id;
        public string source_trial_id;
        public string device_id;
        public string session_id;
        public string trial_id;
        public string split;
        public int sequence_number;
        public string label;
        public string coordinate_frame = "unity_device_origin";
        public int target_sample_rate_hz = 60;
        public long window_start_ns;
        public long window_end_ns;
        public List<QuestWindowSample> samples = new List<QuestWindowSample>();
    }

    public sealed class QuestTrialMetadata {
        public string device_id;
        public string session_id;
        public string trial_id;
        public string split;
        public string label;
        public int sequence_number;
    }
}
