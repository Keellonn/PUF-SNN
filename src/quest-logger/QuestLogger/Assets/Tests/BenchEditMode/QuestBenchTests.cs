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
