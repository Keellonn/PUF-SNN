/*
this file captures the newest Unity XR head pose once per rendered frame
the render callback only queues samples so file writing and resampling happen later
*/

using System.Collections.Generic;
using System.Diagnostics;
using UnityEngine;
using UnityEngine.XR;

namespace PufSnn.QuestLogger {
    public sealed class HeadPoseCapture : MonoBehaviour {
        private readonly RawPoseBuffer sampleBuffer = new RawPoseBuffer();
        private readonly Stopwatch clock = new Stopwatch();
        private InputDevice headDevice;
        private bool captureActive;
        private int lastCapturedFrame = -1;

        public bool CaptureActive => captureActive;

        private void Awake() {
            clock.Start();
        }

        private void OnEnable() {
            Application.onBeforeRender += CaptureBeforeRender;
        }

        private void OnDisable() {
            Application.onBeforeRender -= CaptureBeforeRender;
            captureActive = false;
        }

        public void BeginCapture() {
            // this clears old samples before a new trial
            sampleBuffer.Clear();

            lastCapturedFrame = -1;
            captureActive = true;
        }

        public List<RawHeadPoseSample> StopCapture() {
            captureActive = false;
            return sampleBuffer.Drain();
        }

        private void CaptureBeforeRender() {
            // this callback only reads and queues the newest pose
            if (!captureActive || Time.frameCount == lastCapturedFrame)
                return;

            lastCapturedFrame = Time.frameCount;

            if (!headDevice.isValid)
                headDevice = InputDevices.GetDeviceAtXRNode(XRNode.Head);

            bool positionRead = headDevice.TryGetFeatureValue(CommonUsages.devicePosition, out Vector3 position);
            bool rotationRead = headDevice.TryGetFeatureValue(CommonUsages.deviceRotation, out Quaternion rotation);
            bool trackedRead = headDevice.TryGetFeatureValue(CommonUsages.isTracked, out bool isTracked);
            bool stateRead = headDevice.TryGetFeatureValue(CommonUsages.trackingState, out InputTrackingState trackingState);

            bool trackingValid = headDevice.isValid && positionRead && rotationRead;

            if (trackedRead)
                trackingValid = trackingValid && isTracked;

            if (stateRead) {
                InputTrackingState required = InputTrackingState.Position | InputTrackingState.Rotation;
                trackingValid = trackingValid && (trackingState & required) == required;
            }

            float rotationSquaredMagnitude =
                rotation.x * rotation.x +
                rotation.y * rotation.y +
                rotation.z * rotation.z +
                rotation.w * rotation.w;

            if (!rotationRead || rotationSquaredMagnitude < 0.000001f)
                rotation = Quaternion.identity;
            else
                rotation = Normalize(rotation);

            long captureTimeNs = (long)(clock.ElapsedTicks * (1_000_000_000.0 / Stopwatch.Frequency));

            sampleBuffer.Enqueue(new RawHeadPoseSample {
                capture_time_ns = captureTimeNs,
                position_m = positionRead ? position : Vector3.zero,
                orientation_xyzw = rotation,
                tracking_valid = trackingValid,
                tracking_state = stateRead ? trackingState : InputTrackingState.None,
            });
        }

        private static Quaternion Normalize(Quaternion value) {
            float magnitude = Mathf.Sqrt(
                value.x * value.x +
                value.y * value.y +
                value.z * value.z +
                value.w * value.w
            );

            return new Quaternion(value.x / magnitude, value.y / magnitude, value.z / magnitude, value.w / magnitude);
        }
    }
}
