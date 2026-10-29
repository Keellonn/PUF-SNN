# OpenXR configuration clarification

October 28, 2026. The user's current Android/Meta Quest settings show OpenXR
and Initialize XR on Startup checked. The saved settings now reference the
Android manager and the OpenXRLoader asset. Do not ask the operator to re-enable
an already checked provider or describe the current provider as disabled.

The initial APK inspection remains a narrower fact: that binary contains no
OpenXR native loader, Quest VR category or head-tracking feature. The serialized
settings file read at the initial post-build inspection was empty; its hash is
6d9186dbe3b63c22e9e8c6c89758a37ebd8a2ee9dd3cd3ff57b9800d700d1af4.
The later settings file with an Android assignment has hash
fde33d048d552eaeac9c43897a85bf2d09813a05aa3f663f7bcc5f44c29bc97b.
These observations do not establish when or why the state was created/serialized,
and do not show that the user manually changed the checkbox. The earlier
statement that OpenXR was disabled was too strong.

The present issue is the orange project-validation icon. Read the individual
validation messages, resolve the relevant settings and inspect the next APK.
Do not attribute the first APK's contents to a cause that has not been verified.
The initial build receipt is retained unchanged as a historical observation;
its suggested provider-enabling step is superseded by this clarification.

## Later resolved compile configuration

The subsequent bench APK contains `libUnityOpenXR.so`, `libopenxr_loader.so`,
the Quest VR category and head-tracking metadata. [The later receipt](../results/week-9/keegan/quest-bench-20261028-001/README.md)
identifies that artifact. This closes the offline packaging discrepancy for
that APK; it does not explain the first APK's history or establish runtime
headset behavior. The original receipt is unchanged.
