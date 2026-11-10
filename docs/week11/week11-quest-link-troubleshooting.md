# Quest Link troubleshooting and staff controls

November 10, 2026. Acquisition proposal: Quest 3, wired Quest Link, Unity on the
laptop, files created on that laptop. Proposed room: Torgersen 2015, availability
not yet verified. The bench scene is `Assets/Scenes/QuestLoggerBench.unity` in
the Unity project. It is a development scene, not the approved study procedure.

## Reported setup and reproduction

The prior attempt used the lab Quest 3 and Windows laptop, the Meta Quest Link
desktop application and Unity 6000.6.1f1. Desktop OpenXR was enabled with the
Oculus Touch profile. The headset/Link app versions, firmware, controller
battery levels, active runtime identity and cable/port model were not recorded.
They must be recorded on the next attempt; do not infer them from a screenshot.

1. Connect the headset by USB and open the Link desktop application.
2. The desktop application lists Quest 3 as connected/active.
3. Open the bench scene in Unity Play Mode with recording off.
4. The laptop displays the prompt and control panel. The reported headset view
   is black and the Unity status says head tracking is unavailable.
5. In the headset's own Wi-Fi or power menu, controller pointing highlights a
   control, but trigger selection fails. The user also reported no useful Meta
   button response. These observations precede any successful app recording.

Expected: the headset system UI accepts selection, Link starts, the Unity scene
renders in the headset and live head tracking becomes available. Observed:
pointing/highlighting works but selection does not, including outside Unity.

## Checks already performed

| Check | Observed result | What it establishes |
|---|---|---|
| Link desktop device listing | Connected/active | Device recognition, not an active rendered Link session |
| USB bandwidth test | USB 2, 369 Mbps; USB 3 recommended | Cable/port condition, not the demonstrated cause of failed triggers |
| Pointing at headset system buttons | Highlight follows pointing | Some pose/pointer path works; button input remains unverified |
| Headset restart | Selection failure remained | One restart did not resolve it |
| Controller battery reseat/restart | No improvement reported | No repair established; battery condition not measured |
| Desktop Play Mode controls | Earlier callback/UI checks and current synthetic tests pass | Software evidence only |

No controller hardware fault, battery fault or Unity binding fault has been
diagnosed. System-menu failure places the first troubleshooting boundary
outside the logger's application handlers. Unity bindings, UI dispatch and
application callbacks still need their own live-path checks after Link works.

## Proposed staff-operated procedure

The participant's task is seated head movement. Participant controller selection
is not required by that task. Propose staff operating Arm, Start, Skip, Stop and
Continue from the laptop. Participants see the movement prompt and can ask to
stop verbally; staff immediately use Stop or Escape. Agree the final staff
procedure with the PI before it becomes a study instruction.

The callbacks do not require a controller pose. The bench still offers its
existing controller controls; this checkpoint does not add a new interface or
claim actual desktop mouse dispatch in the Link view has been verified.

The new safeguard stops an active visit and disarms recording on application
focus loss, using reason `application_focus_lost`. Returning focus does not
resume the old visit or rearm recording. Pausing/disabling remains covered by
earlier tests. Staff must expect switching away from the Unity application to
stop the visit. A clean restart requires a fresh visit code. This event policy
does not establish that USB loss or every headset interruption sends a focus
event; test those interruptions explicitly.

## Next bounded bench checks

First ask lab support to demonstrate system-menu selection and a rendered Link
session using the assigned equipment. Try an authorized known-good controller
or cable/port if available, changing one item at a time. Do not reset the lab
headset or change account ownership as an unrecorded troubleshooting step.

Then use the [acquisition checklist](../../results/week-11/keegan/technical-review-20261110-001/acquisition-checklist.csv).
Leave every not-run row marked `NOT_RUN` until observed on the actual path:

- Record headset, cable/port, firmware, Link/runtime, Unity/package versions and
  the exact source/build identity. Keep the headset on a non-human bench fixture.
- Verify participant-facing prompts are visible and match the laptop display.
- Verify staff mouse actions and focused Escape reach the intended callbacks.
- Verify Start cannot record while disarmed, Stop ends capture immediately,
  focus/pause does not auto-resume, and the operator can distinguish each phase.
- Check source timestamps, sampling, tracking/gaps and prompt-to-capture
  alignment on the real acquisition path. Software timestamps alone do not prove
  what the participant saw. Retain a bench observation record and its limits.
- Check interruption accounting, incomplete files, reload and artificial transfer
  hashes. Do not use wearing the headset as a substitute for authorized human
  research collection or evaluation.

Actual Link tracking, prompts, control dispatch, interruptions and transfer are
still open. Synthetic passes close none of those hardware rows automatically.

Unity event reference: [OnApplicationFocus](https://docs.unity.com/en-us/engine/6000.0/script-reference/unityengine/monobehaviour/onapplicationfocus).
