using System;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.UI;
using UnityEngine.XR;
using XRInputDevice = UnityEngine.XR.InputDevice;
using CommonUsages = UnityEngine.XR.CommonUsages;

namespace PufSnn.QuestLogger.Bench {
    // Development controls. This switch records permission from the operator;
    // it does not grant institutional approval or establish staff identity.
    public sealed class QuestBenchControls : MonoBehaviour {
        public QuestTrialController controller;
        public Camera viewCamera;
        public Transform trackingSpace;
        public RectTransform panel;
        public Text prompt;
        public Text status;
        public Button armButton, startButton, skipButton, stopButton, continueButton;
        public string buildLabel = "week9-quest-bench-20261028";
        public string VisitCode { get; private set; }
        private Button[] buttons;
        private EdgeLatch selectLatch, skipLatch, stopLatch, continueLatch;
        private string lastPrompt = "Recording off";
        private bool sessionWasRunning;
        private float nextStatusUpdate;
        private LineRenderer rayLine;
        public Material pointerMaterial;

        public void Initialize() {
            if (controller == null) throw new InvalidOperationException("A trial controller is required.");
            controller.SetRecordingEnabled(false);
            buttons = new[] {armButton, startButton, skipButton, stopButton, continueButton};
            controller.PromptChanged -= ReceivePrompt;
            controller.PromptChanged += ReceivePrompt;
            armButton.onClick.RemoveAllListeners(); armButton.onClick.AddListener(ToggleRecording);
            startButton.onClick.RemoveAllListeners(); startButton.onClick.AddListener(StartVisit);
            skipButton.onClick.RemoveAllListeners(); skipButton.onClick.AddListener(controller.SkipCurrentTrial);
            stopButton.onClick.RemoveAllListeners(); stopButton.onClick.AddListener(StopAndDisarm);
            continueButton.onClick.RemoveAllListeners(); continueButton.onClick.AddListener(controller.ContinueAfterBreak);
            NewVisit();
            ReceivePrompt("Recording off. Arm only for a permitted bench or development test.");
            RefreshButtons();
        }

        private void Start() {
            Initialize();
            if (pointerMaterial != null) {
                rayLine = new GameObject("Right controller pointer").AddComponent<LineRenderer>();
                rayLine.transform.SetParent(transform, false);
                rayLine.sharedMaterial = pointerMaterial;
                rayLine.positionCount = 2; rayLine.startWidth = rayLine.endWidth = 0.004f;
                rayLine.startColor = rayLine.endColor = new Color(1f, 0.65f, 0.2f);
                rayLine.enabled = false;
            }
        }

        private void NewVisit() {
            VisitCode = "bench-" + DateTime.UtcNow.ToString("yyyyMMdd-HHmmss") + "-" + Guid.NewGuid().ToString("N").Substring(0,8);
            controller.ConfigureVisit("bench-fixture", VisitCode, "bench-quest", VisitCode,
                buildLabel, "validation");
        }

        public void ToggleRecording() {
            if (controller.SessionRunning) return;
            controller.SetRecordingEnabled(!controller.RecordingEnabled);
            ReceivePrompt(controller.RecordingEnabled ? "Armed. Start begins a new bench visit." : "Recording off");
            RefreshButtons();
        }

        public void StartVisit() {
            if (!controller.RecordingEnabled || controller.SessionRunning) return;
            NewVisit();
            controller.StartTrialSession();
            sessionWasRunning = controller.SessionRunning;
            if (!sessionWasRunning) StopAndDisarm();
            RefreshButtons();
        }

        public void StopAndDisarm() {
            if (controller == null) return;
            controller.StopTrialSession();
            controller.SetRecordingEnabled(false);
            ReceivePrompt("Stopped. Recording off.");
            RefreshButtons();
        }

        public void ReceivePrompt(string message) {
            lastPrompt = message ?? "";
            if (prompt != null) prompt.text = FriendlyPrompt(lastPrompt);
            RefreshButtons();
        }

        public static string FriendlyPrompt(string value) {
            return value.Replace("look_left_return", "look left and return")
                .Replace("look_right_return", "look right and return")
                .Replace("prepare:", "PREPARE:").Replace("record:", "RECORD:")
                .Replace("rest", "REST");
        }

        private void RefreshButtons() {
            if (controller == null || armButton == null) return;
            bool running = controller.SessionRunning;
            armButton.interactable = !running;
            Text label = armButton.GetComponentInChildren<Text>();
            if (label != null) label.text = controller.RecordingEnabled ? "Disarm recording" : "Arm permitted test";
            startButton.interactable = controller.RecordingEnabled && !running;
            skipButton.interactable = running;
            stopButton.interactable = controller.RecordingEnabled || running;
            continueButton.interactable = running && lastPrompt.StartsWith("break:", StringComparison.Ordinal);
        }

        private void Update() {
            if (controller == null) return;
            if (sessionWasRunning && !controller.SessionRunning) {
                controller.SetRecordingEnabled(false);
                ReceivePrompt("Visit ended. Recording off.");
            }
            sessionWasRunning = controller.SessionRunning;
            RefreshButtons();
            XRInputDevice right = InputDevices.GetDeviceAtXRNode(XRNode.RightHand);
            XRInputDevice left = InputDevices.GetDeviceAtXRNode(XRNode.LeftHand);
            bool rightValid = TrackedController(right), leftValid = TrackedController(left);
            bool selectAvailable = ReadButton(right, CommonUsages.triggerButton, out bool select);
            bool skipAvailable = ReadButton(left, CommonUsages.primaryButton, out bool skip);
            bool stopAvailable = ReadButton(left, CommonUsages.secondaryButton, out bool stop);
            bool nextAvailable = ReadButton(right, CommonUsages.primaryButton, out bool next);
            bool press = selectLatch.Pressed(rightValid && selectAvailable, select);
            // Digital stop/skip must still work when the controller pose is out of view.
            if (skipLatch.Pressed(skipAvailable, skip)) controller.SkipCurrentTrial();
            if (stopLatch.Pressed(stopAvailable, stop)) StopAndDisarm();
            if (continueLatch.Pressed(nextAvailable, next) && continueButton.interactable) controller.ContinueAfterBreak();
            Vector3 p = Vector3.zero; Quaternion q = Quaternion.identity;
            bool poseRead = right.TryGetFeatureValue(CommonUsages.devicePosition, out p)
                && right.TryGetFeatureValue(CommonUsages.deviceRotation, out q);
            if (rightValid && poseRead && trackingSpace != null) {
                Ray ray = new Ray(trackingSpace.TransformPoint(p), trackingSpace.rotation * (q * Vector3.forward));
                Button hit = HitButton(ray, out Vector3 point);
                if (rayLine != null) {
                    rayLine.enabled = true;
                    rayLine.SetPosition(0, ray.origin);
                    rayLine.SetPosition(1, hit != null ? point : ray.GetPoint(2f));
                }
                if (press && hit != null && hit.interactable) hit.onClick.Invoke();
            } else if (rayLine != null) rayLine.enabled = false;
            if (Keyboard.current != null && Keyboard.current.escapeKey.wasPressedThisFrame) StopAndDisarm();
            if (Time.unscaledTime >= nextStatusUpdate) {
                nextStatusUpdate = Time.unscaledTime + 0.25f;
                if (status != null) status.text = (controller.RecordingEnabled ? "RECORDING ARMED" : "RECORDING OFF")
                    + " | Head tracking: " + (TrackedController(InputDevices.GetDeviceAtXRNode(XRNode.Head)) ? "available" : "unavailable")
                    + "\nVisit: " + VisitCode + "\nDevelopment interface. Headset behavior still needs validation.";
            }
        }

        private Button HitButton(Ray ray, out Vector3 point) {
            foreach (Button button in buttons) {
                if (button != null && button.interactable && RayInsideRect(ray, (RectTransform)button.transform, out point)) return button;
            }
            point = default; return null;
        }

        public static bool RayInsideRect(Ray ray, RectTransform rect, out Vector3 point) {
            point = default;
            if (rect == null || !Finite(ray.origin) || !Finite(ray.direction) || ray.direction.sqrMagnitude < 0.000001f) return false;
            Plane plane = new Plane(rect.forward, rect.position);
            if (!plane.Raycast(ray, out float distance) || distance < 0 || distance > 8) return false;
            point = ray.GetPoint(distance);
            Vector3 local = rect.InverseTransformPoint(point);
            return rect.rect.Contains(new Vector2(local.x, local.y));
        }

        private static bool Finite(Vector3 v) => !float.IsNaN(v.x) && !float.IsNaN(v.y) && !float.IsNaN(v.z)
            && !float.IsInfinity(v.x) && !float.IsInfinity(v.y) && !float.IsInfinity(v.z);
        private static bool TrackedController(XRInputDevice d) => d.isValid
            && d.TryGetFeatureValue(CommonUsages.isTracked, out bool tracked) && tracked;
        private static bool ReadButton(XRInputDevice d, InputFeatureUsage<bool> usage, out bool value) {
            value = false;
            return d.isValid && d.TryGetFeatureValue(usage, out value);
        }
        private void OnApplicationPause(bool paused) { if (paused) StopAndDisarm(); }
        private void OnDisable() { StopAndDisarm(); if (controller != null) controller.PromptChanged -= ReceivePrompt; }

        // Require a released sample after (re)connection before treating a hold as a click.
        public struct EdgeLatch {
            private bool sawRelease, wasDown;
            public bool Pressed(bool available, bool down) {
                if (!available) { sawRelease = false; wasDown = false; return false; }
                if (!down) sawRelease = true;
                bool result = sawRelease && down && !wasDown;
                wasDown = down;
                return result;
            }
        }
    }
}
