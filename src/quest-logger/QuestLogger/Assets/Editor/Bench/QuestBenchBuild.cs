using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.UI;
using UnityEngine.UI;
using Unity.XR.CoreUtils;
using UnityEngine.XR.OpenXR;
using PoseDriver = UnityEngine.InputSystem.XR.TrackedPoseDriver;

namespace PufSnn.QuestLogger.Bench.Editor {
    public static class QuestBenchBuild {
        public const string ScenePath = "Assets/Scenes/QuestLoggerBench.unity";
        public const string PackageId = "com.pufsnn.questlogger.bench";

        [MenuItem("PUF SNN/Prepare Quest bench scene")]
        public static void Prepare() {
            OpenXRSettings xr = OpenXRSettings.GetSettingsForBuildTargetGroup(BuildTargetGroup.Android);
            if (xr == null) throw new InvalidOperationException("Android OpenXR settings are missing.");
            // This pose logger uses no AR camera, scene mesh, anchors, eye or hand data.
            foreach (var feature in xr.GetFeatures()) {
                string type = feature.GetType().Name;
                feature.enabled = type == "MetaQuestFeature" || type == "OculusTouchControllerProfile"
                    || type == "MetaQuestTouchPlusControllerProfile";
                EditorUtility.SetDirty(feature);
            }
            xr.latencyOptimization = OpenXRSettings.LatencyOptimization.PrioritizeInputPolling;
            EditorUtility.SetDirty(xr);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            GameObject originObject = new GameObject("XR Origin");
            XROrigin origin = originObject.AddComponent<XROrigin>();
            GameObject offset = new GameObject("Camera Offset"); offset.transform.SetParent(originObject.transform, false);
            GameObject cameraObject = new GameObject("Main Camera"); cameraObject.tag = "MainCamera";
            cameraObject.transform.SetParent(offset.transform, false);
            Camera camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor; camera.backgroundColor = new Color(0.045f,0.055f,0.075f);
            camera.nearClipPlane = 0.05f; camera.farClipPlane = 40;
            cameraObject.AddComponent<AudioListener>();
            PoseDriver driver = cameraObject.AddComponent<PoseDriver>();
            driver.positionInput = new InputActionProperty(new InputAction("Head position", InputActionType.Value,
                "<XRHMD>/centerEyePosition", expectedControlType:"Vector3"));
            driver.rotationInput = new InputActionProperty(new InputAction("Head rotation", InputActionType.Value,
                "<XRHMD>/centerEyeRotation", expectedControlType:"Quaternion"));
            driver.trackingStateInput = new InputActionProperty(new InputAction("Head tracking state", InputActionType.Value,
                "<XRHMD>/trackingState", expectedControlType:"Integer"));
            driver.updateType = PoseDriver.UpdateType.UpdateAndBeforeRender;
            driver.ignoreTrackingState = false;
            origin.CameraFloorOffsetObject = offset; origin.Camera = camera;
            origin.RequestedTrackingOriginMode = XROrigin.TrackingOriginMode.Device;
            origin.CameraYOffset = 1.6f;
            offset.transform.localPosition = new Vector3(0,1.6f,0);

            GameObject logger = new GameObject("Logger");
            HeadPoseCapture capture = logger.AddComponent<HeadPoseCapture>();
            QuestWindowWriter writer = logger.AddComponent<QuestWindowWriter>();
            QuestTrialController controller = logger.AddComponent<QuestTrialController>();
            SerializedObject settings = new SerializedObject(controller);
            settings.FindProperty("headPoseCapture").objectReferenceValue = capture;
            settings.FindProperty("windowWriter").objectReferenceValue = writer;
            settings.FindProperty("recordingAuthorized").boolValue = false;
            settings.FindProperty("startOnPlay").boolValue = false;
            settings.FindProperty("participantCode").stringValue = "bench-fixture";
            settings.FindProperty("visitCode").stringValue = "bench-runtime-generated";
            settings.FindProperty("deviceId").stringValue = "bench-quest";
            settings.FindProperty("sessionId").stringValue = "bench-runtime-generated";
            settings.FindProperty("processingVersion").stringValue = "week9-quest-bench-20261028";
            settings.FindProperty("split").stringValue = "validation";
            settings.FindProperty("blockCount").intValue = 2;
            settings.FindProperty("trialsPerClass").intValue = 1;
            settings.FindProperty("maximumScheduledTrials").intValue = 10;
            settings.FindProperty("promptSeconds").floatValue = 1;
            settings.FindProperty("actionSeconds").floatValue = 2;
            settings.FindProperty("restSeconds").floatValue = 1;
            settings.ApplyModifiedPropertiesWithoutUndo();

            GameObject canvasObject = new GameObject("Bench panel", typeof(RectTransform), typeof(Canvas), typeof(GraphicRaycaster));
            RectTransform panel = (RectTransform)canvasObject.transform;
            panel.sizeDelta = new Vector2(900,650); panel.position = new Vector3(0,1.6f,1.8f); panel.localScale = Vector3.one * 0.002f;
            Canvas canvas = canvasObject.GetComponent<Canvas>(); canvas.renderMode = RenderMode.WorldSpace; canvas.worldCamera = camera;
            Image background = canvasObject.AddComponent<Image>(); background.color = new Color(0.07f,0.09f,0.12f);
            Label(panel,"Title","Quest Logger Bench", new Vector2(0,270),new Vector2(850,60),38);
            Label(panel,"Scope","Bench / development interface. No study collection approval is implied.",new Vector2(0,220),new Vector2(850,45),23);
            Text prompt = Label(panel,"Task prompt","Recording off",new Vector2(0,142),new Vector2(850,100),32);
            Text status = Label(panel,"Status","Recording off at startup",new Vector2(0,35),new Vector2(850,95),21);
            QuestBenchControls controls = logger.AddComponent<QuestBenchControls>();
            controls.controller = controller; controls.viewCamera = camera; controls.trackingSpace = offset.transform;
            controls.panel = panel; controls.prompt = prompt; controls.status = status;
            controls.armButton = ButtonAt(panel,"Arm permitted test",new Vector2(-215,-65));
            controls.startButton = ButtonAt(panel,"Start",new Vector2(215,-65));
            controls.skipButton = ButtonAt(panel,"Skip",new Vector2(-280,-150),250);
            controls.stopButton = ButtonAt(panel,"Stop",new Vector2(0,-150),250);
            controls.continueButton = ButtonAt(panel,"Continue",new Vector2(280,-150),250);
            Label(panel,"Controller guide","Right trigger: point and select   |   X: skip   |   Y: stop + disarm   |   A: continue\nMouse buttons and Escape also work in the Editor. Recording resets after pause or visit end.",
                new Vector2(0,-250),new Vector2(850,100),21);
            GameObject events = new GameObject("EventSystem", typeof(EventSystem), typeof(InputSystemUIInputModule));
            events.GetComponent<InputSystemUIInputModule>().AssignDefaultActions();
            string materialPath = "Assets/Settings/QuestBenchPointer.mat";
            Material material = AssetDatabase.LoadAssetAtPath<Material>(materialPath);
            if (material == null) {
                Shader shader = Shader.Find("Universal Render Pipeline/Unlit");
                if (shader == null) throw new InvalidOperationException("The URP unlit shader is unavailable.");
                material = new Material(shader); material.SetColor("_BaseColor",new Color(1,0.6f,0.1f));
                AssetDatabase.CreateAsset(material,materialPath);
            }
            controls.pointerMaterial = material;
            EditorSceneManager.SaveScene(EditorSceneManager.GetActiveScene(),ScenePath);
            EditorBuildSettings.scenes = new[] {new EditorBuildSettingsScene(ScenePath,true)};
            PlayerSettings.SetApplicationIdentifier(NamedBuildTarget.Android,PackageId);
            PlayerSettings.productName = "Quest Logger Bench";
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel32;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel32;
            AssetDatabase.SaveAssets();
            VerifyScene();
            Debug.Log("QUEST_BENCH_PREPARED " + ScenePath);
        }

        public static void VerifyScene() {
            QuestBenchControls c = UnityEngine.Object.FindFirstObjectByType<QuestBenchControls>();
            if (c == null || c.controller == null || c.panel == null || c.prompt == null || c.status == null)
                throw new InvalidOperationException("Bench scene references are incomplete.");
            if (c.controller.RecordingEnabled || c.controller.SessionRunning) throw new InvalidOperationException("The saved scene must be disarmed.");
            SerializedObject settings = new SerializedObject(c.controller);
            if (settings.FindProperty("startOnPlay").boolValue) throw new InvalidOperationException("Automatic capture is not allowed in this bench scene.");
            if (c.viewCamera.GetComponent<PoseDriver>() == null || c.viewCamera.GetComponentInParent<XROrigin>() == null)
                throw new InvalidOperationException("The XR camera is missing its tracked driver or origin.");
            if (c.panel.GetComponent<Canvas>().renderMode != RenderMode.WorldSpace) throw new InvalidOperationException("Use a world-space panel.");
            if (new[] {c.armButton,c.startButton,c.skipButton,c.stopButton,c.continueButton}.Any(x => x == null))
                throw new InvalidOperationException("A bench control is missing.");
        }

        public static void BuildAndroid() {
            Prepare();
            string output = Environment.GetEnvironmentVariable("PUF_SNN_BENCH_APK");
            if (string.IsNullOrEmpty(output) || !Path.IsPathRooted(output) || File.Exists(output))
                throw new InvalidOperationException("Set PUF_SNN_BENCH_APK to a new absolute APK path.");
            Directory.CreateDirectory(Path.GetDirectoryName(output));
            BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions {
                scenes = new[] {ScenePath}, locationPathName = output, target = BuildTarget.Android,
                options = BuildOptions.Development
            });
            string receipt = output + ".build.json";
            File.WriteAllText(receipt, JsonUtility.ToJson(new BuildReceipt {
                result = report.summary.result.ToString(), seconds = report.summary.totalTime.TotalSeconds,
                bytes = report.summary.totalSize, errors = report.summary.totalErrors,
                warnings = report.summary.totalWarnings, unity = Application.unityVersion,
                package = PackageId, scene = ScenePath,
                device_install_or_capture_tested = false
            },true));
            if (report.summary.result != BuildResult.Succeeded) throw new InvalidOperationException("Android build failed; inspect the private build log.");
        }

        [Serializable] private sealed class BuildReceipt {
            public string result, unity, package, scene;
            public double seconds; public ulong bytes; public int errors,warnings;
            public bool device_install_or_capture_tested;
        }

        private static RectTransform Element(Transform parent,string name,Vector2 at,Vector2 size) {
            RectTransform r = new GameObject(name,typeof(RectTransform)).GetComponent<RectTransform>();
            r.SetParent(parent,false); r.anchorMin = r.anchorMax = r.pivot = new Vector2(0.5f,0.5f);
            r.anchoredPosition = at; r.sizeDelta = size; r.gameObject.layer = 5; return r;
        }
        private static Text Label(Transform parent,string name,string value,Vector2 at,Vector2 size,int fontSize) {
            Text text = Element(parent,name,at,size).gameObject.AddComponent<Text>();
            text.font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf"); text.text = value;
            text.fontSize = fontSize; text.color = Color.white; text.alignment = TextAnchor.MiddleCenter;
            text.horizontalOverflow = HorizontalWrapMode.Wrap; text.verticalOverflow = VerticalWrapMode.Truncate;
            text.raycastTarget = false; return text;
        }
        private static Button ButtonAt(Transform parent,string name,Vector2 at,float width = 400) {
            RectTransform rect = Element(parent,name,at,new Vector2(width,65));
            Image image = rect.gameObject.AddComponent<Image>(); image.color = new Color(0.35f,0.10f,0.19f);
            Button button = rect.gameObject.AddComponent<Button>(); button.targetGraphic = image;
            ColorBlock colors = button.colors; colors.highlightedColor = new Color(1,0.75f,0.5f);
            colors.disabledColor = new Color(0.35f,0.35f,0.35f,0.7f); button.colors = colors;
            Label(rect,"Label",name,Vector2.zero,new Vector2(width-10,60),25); return button;
        }
    }
}
