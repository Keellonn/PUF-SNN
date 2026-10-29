# First Android compile checkpoint

October 28, 2026. Unity 6000.6.1f1 reported a successful 670.463-second build.
The output is a 42,567,419-byte ARM64 APK. The binary stays outside Git; the
receipt identifies it by SHA-256. The enabled scene is LoggerControlsLaptop;
the saved source has recording and automatic start disabled.

Offline manifest/library inspection found a configuration gap: this APK has no
OpenXR loader, no Quest VR intent category and no VR head-tracking feature.
The XR settings also have no per-build-target loader assignment. Selecting the
Meta Quest build profile did not enable the OpenXR plug-in. Treat this as a
successful Android compilation, not a verified headset application. Preserve
this checkpoint and enable Android OpenXR/Quest support before the next build.

The current package ID remains the Unity template ID. The manifest declares
Internet permission; this does not establish actual network traffic or all
platform processing. Future headset packaging and permissions need review.
Desktop mouse buttons, a tracked XR camera and runtime arming controls are not
yet a verified headset/staff interface. No device install or participant motion
test was performed. Build duration is workflow time, not sensor-window latency.

Only a whitelisted success line and public APK metadata are retained. Raw Editor
logs stay local because they contain account/licensing and machine information.
