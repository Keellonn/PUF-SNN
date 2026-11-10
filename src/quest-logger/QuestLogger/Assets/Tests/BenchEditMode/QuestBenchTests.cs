using System;
using System.Collections;
using System.Reflection;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.InputSystem.XR;
using UnityEngine.UI;
using UnityEngine.TestTools;
using Unity.XR.CoreUtils;
using PufSnn.QuestLogger.Bench;
using PufSnn.QuestLogger.Bench.Editor;

namespace PufSnn.QuestLogger.Tests {
    public sealed class QuestBenchTests {
        [Test]
        public void SavedBenchSceneHasTrackedCameraAndAllControlsWithRecordingOff() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath,OpenSceneMode.Single);
            QuestBenchBuild.VerifyScene();
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            TrackedPoseDriver driver = c.viewCamera.GetComponent<TrackedPoseDriver>();
            Assert.AreEqual("<XRHMD>/centerEyePosition",driver.positionInput.action.bindings[0].path);
            Assert.AreEqual("<XRHMD>/centerEyeRotation",driver.rotationInput.action.bindings[0].path);
            Assert.IsFalse(driver.ignoreTrackingState);
            Assert.AreEqual(TrackedPoseDriver.UpdateType.UpdateAndBeforeRender,driver.updateType);
            Assert.AreEqual(XROrigin.TrackingOriginMode.Device,c.viewCamera.GetComponentInParent<XROrigin>().RequestedTrackingOriginMode);
        }

        [Test]
        public void InitializeDisarmsAndStartButtonCannotRecordUntilExplicitlyArmed() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath,OpenSceneMode.Single);
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            c.controller.SetRecordingEnabled(true);
            c.Initialize();
            Assert.IsFalse(c.controller.RecordingEnabled);
            Assert.IsFalse(c.startButton.interactable);
            c.StartVisit();
            Assert.IsFalse(c.controller.SessionRunning);
            Assert.IsTrue(c.VisitCode.StartsWith("bench-"));
            Assert.IsNotEmpty(c.prompt.text);
        }

        [Test]
        public void OperatorCanArmThenStopAndDisarmWithoutStartingCapture() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath,OpenSceneMode.Single);
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            c.Initialize(); c.armButton.onClick.Invoke();
            Assert.IsTrue(c.controller.RecordingEnabled); Assert.IsTrue(c.startButton.interactable);
            c.stopButton.onClick.Invoke();
            Assert.IsFalse(c.controller.RecordingEnabled); Assert.IsFalse(c.controller.SessionRunning);
        }

        [UnityTest]
        public IEnumerator PauseDisarmsAndDoesNotAutomaticallyResume() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath,OpenSceneMode.Single);
            yield return new EnterPlayMode();
            yield return null;
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            c.Initialize(); c.ToggleRecording();
            c.SendMessage("OnApplicationPause",true); c.SendMessage("OnApplicationPause",false);
            Assert.IsFalse(c.controller.RecordingEnabled); Assert.IsFalse(c.controller.SessionRunning);
            yield return new ExitPlayMode();
        }

        [UnityTest]
        public IEnumerator DisablingBenchControlsDisarmsRecording() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath,OpenSceneMode.Single);
            yield return new EnterPlayMode();
            yield return null;
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            c.Initialize(); c.ToggleRecording(); c.enabled = false;
            Assert.IsFalse(c.controller.RecordingEnabled);
            yield return new ExitPlayMode();
        }

        [Test]
        public void PromptIsVisibleAndContinueIsUnavailableOutsideABreak() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath,OpenSceneMode.Single);
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>(); c.Initialize();
            c.ReceivePrompt("record: look_left_return");
            StringAssert.Contains("RECORD: look left and return",c.prompt.text);
            Assert.IsFalse(c.continueButton.interactable);
        }

        [Test]
        public void VisitIdentifiersRejectTraversalAndInvalidSplit() {
            GameObject go = new GameObject("identifier check");
            try {
                QuestTrialController c = go.AddComponent<QuestTrialController>();
                Assert.Throws<ArgumentException>(() => c.ConfigureVisit("bench","../escape","device","session","version","validation"));
                Assert.Throws<ArgumentException>(() => c.ConfigureVisit("bench","visit","device","session","version","anything"));
                c.ConfigureVisit("bench","visit","device","session","version","validation");
            } finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        [Test]
        public void LosingFocusDisarmsAndReturningFocusDoesNotRearm() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath, OpenSceneMode.Single);
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            c.Initialize(); c.ToggleRecording();
            MethodInfo focus = typeof(QuestBenchControls).GetMethod("OnApplicationFocus", BindingFlags.NonPublic | BindingFlags.Instance);
            focus.Invoke(c, new object[] {false});
            focus.Invoke(c, new object[] {true});
            Assert.IsFalse(c.controller.RecordingEnabled);
            Assert.IsFalse(c.controller.SessionRunning);
            Assert.IsFalse(c.startButton.interactable);
            StringAssert.Contains("Recording off", c.prompt.text);
        }

        private static string PrepareStaffFixture(QuestBenchControls c) {
            string root = System.IO.Path.Combine(System.IO.Path.GetTempPath(), "puf-snn-week11-" + Guid.NewGuid().ToString("N"));
            System.IO.Directory.CreateDirectory(root);
            QuestWindowWriter writer = c.controller.GetComponent<QuestWindowWriter>();
            typeof(QuestWindowWriter).GetField("outputFolderName", BindingFlags.NonPublic | BindingFlags.Instance).SetValue(writer, root);
            // Never sample a real headset in these synthetic control tests.
            c.controller.GetComponent<HeadPoseCapture>().enabled = false;
            return root;
        }

        private static void ExportStaffFixture(string root, string name) {
            string[] args = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, "-pufStaffControlsFixtureRoot");
            if (i < 0 || i + 1 >= args.Length) return;
            string target = System.IO.Path.Combine(args[i + 1], name);
            System.IO.Directory.CreateDirectory(target);
            foreach (string file in System.IO.Directory.GetFiles(root))
                System.IO.File.Copy(file, System.IO.Path.Combine(target, System.IO.Path.GetFileName(file)), false);
        }

        private static void DeleteStaffFixture(string root) {
            string prefix = System.IO.Path.Combine(System.IO.Path.GetFullPath(System.IO.Path.GetTempPath()), "puf-snn-week11-");
            Assert.IsTrue(System.IO.Path.GetFullPath(root).StartsWith(prefix, StringComparison.OrdinalIgnoreCase));
            System.IO.Directory.Delete(root, true);
        }

        [UnityTest]
        public IEnumerator DesktopButtonsStartSkipAndStopAnActiveVisitWithoutPoseCapture() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath, OpenSceneMode.Single);
            yield return new EnterPlayMode(); yield return null;
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            string root = PrepareStaffFixture(c);
            try {
                c.Initialize(); c.armButton.onClick.Invoke(); c.startButton.onClick.Invoke();
                Assert.IsTrue(c.controller.SessionRunning);
                c.skipButton.onClick.Invoke(); yield return null;
                c.stopButton.onClick.Invoke();
                Assert.IsFalse(c.controller.SessionRunning); Assert.IsFalse(c.controller.RecordingEnabled);
                Assert.IsFalse(c.controller.GetComponent<HeadPoseCapture>().CaptureActive);
                string ledger = System.IO.File.ReadAllText(System.IO.Directory.GetFiles(root, "*-trials.jsonl")[0]);
                StringAssert.Contains("\"event_type\":\"skipped\"", ledger);
                StringAssert.Contains("\"event_type\":\"visit_closed\"", ledger);
                Assert.AreEqual(0, System.IO.Directory.GetFiles(root, "*-windows.jsonl").Length);
                Assert.IsFalse(c.controller.RetainsAcceptedSource);
                ExportStaffFixture(root, "desktop-stop");
            } finally { c.StopAndDisarm(); DeleteStaffFixture(root); }
            yield return new ExitPlayMode();
        }

        [UnityTest]
        public IEnumerator FocusLossStopsActiveCaptureRecordsReasonAndDoesNotResume() {
            EditorSceneManager.OpenScene(QuestBenchBuild.ScenePath, OpenSceneMode.Single);
            yield return new EnterPlayMode(); yield return null;
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            string root = PrepareStaffFixture(c);
            try {
                c.Initialize(); c.ToggleRecording(); c.StartVisit();
                float deadline = Time.realtimeSinceStartup + 4;
                while (!c.controller.CurrentPrompt.StartsWith("record:", StringComparison.Ordinal) && Time.realtimeSinceStartup < deadline)
                    yield return null;
                Assert.IsTrue(c.controller.GetComponent<HeadPoseCapture>().CaptureActive);
                c.SendMessage("OnApplicationFocus", false); c.SendMessage("OnApplicationFocus", true);
                Assert.IsFalse(c.controller.SessionRunning); Assert.IsFalse(c.controller.RecordingEnabled);
                Assert.IsFalse(c.controller.GetComponent<HeadPoseCapture>().CaptureActive);
                string ledger = System.IO.File.ReadAllText(System.IO.Directory.GetFiles(root, "*-trials.jsonl")[0]);
                StringAssert.Contains("application_focus_lost", ledger);
                StringAssert.Contains("\"event_type\":\"stopped\"", ledger);
                Assert.AreEqual(0, System.IO.Directory.GetFiles(root, "*-windows.jsonl").Length);
                ExportStaffFixture(root, "focus-stop");
            } finally { c.StopAndDisarm(); DeleteStaffFixture(root); }
            yield return new ExitPlayMode();
        }

        [Test]
        public void HeldTriggerOnConnectionDoesNotClickUntilReleased() {
            QuestBenchControls.EdgeLatch latch = new QuestBenchControls.EdgeLatch();
            Assert.IsFalse(latch.Pressed(true,true)); Assert.IsFalse(latch.Pressed(true,true));
            Assert.IsFalse(latch.Pressed(true,false)); Assert.IsTrue(latch.Pressed(true,true));
            Assert.IsFalse(latch.Pressed(true,true));
        }

        [Test]
        public void TrackingLossRequiresAReleaseBeforeAnotherClick() {
            QuestBenchControls.EdgeLatch latch = new QuestBenchControls.EdgeLatch();
            latch.Pressed(true,false); Assert.IsTrue(latch.Pressed(true,true));
            Assert.IsFalse(latch.Pressed(false,false)); Assert.IsFalse(latch.Pressed(true,true));
            latch.Pressed(true,false); Assert.IsTrue(latch.Pressed(true,true));
        }

        [Test]
        public void ControllerRayHitsRotatedButtonButRejectsMissesAndBehindRay() {
            GameObject go = new GameObject("ray rectangle",typeof(RectTransform));
            try {
                RectTransform rect = (RectTransform)go.transform; rect.sizeDelta = new Vector2(2,2);
                rect.position = new Vector3(0,0,2); rect.rotation = Quaternion.Euler(0,25,0);
                Assert.IsTrue(QuestBenchControls.RayInsideRect(new Ray(Vector3.zero,Vector3.forward),rect,out _));
                Assert.IsFalse(QuestBenchControls.RayInsideRect(new Ray(new Vector3(8,0,0),Vector3.forward),rect,out _));
                Assert.IsFalse(QuestBenchControls.RayInsideRect(new Ray(Vector3.zero,Vector3.back),rect,out _));
                Assert.IsFalse(QuestBenchControls.RayInsideRect(new Ray(new Vector3(float.NaN,0,0),Vector3.forward),rect,out _));
            } finally { UnityEngine.Object.DestroyImmediate(go); }
        }
    }
}
