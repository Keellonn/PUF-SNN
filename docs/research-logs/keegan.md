# Keegan Hoyne's Research Log

**Owner:** Keegan Hoyne  
**Current week:** Week 4  
**Last updated:** September 22, 2026

## Current research question

Can a software prototype using a simulated noisy PUF-derived session credential reject replayed, modified, or misattributed Quest 3 head-motion windows before SNN inference while meeting our attack-rejection, macro-F1-loss, and latency targets?

## My part of the project

I'm responsible for
- Quest 3 head-motion logging
- The synthetic data generator
- Data validation and leakage tests
- Dataset splits
- Logistic regression and random forest
- SNN motion classification
- Sensor abnormality detection
- Model and latency evaluation

Will is responsible for
- The simulated PUF
- PUF measurements
- Credential reconstruction
- Session authentication
- Protecting and verifying each window
- Authentication attacks and results

We share the window format, threat model, integration, research question, literature review, presentation, and final evaluation.

## Project summary

The project tests a software system that protects Quest 3 head-motion windows before they reach a classifier.

A simulated noisy PUF helps reconstruct credential material for session establishment. HMAC checks each protected window's integrity and knowledge of the session key. Separate verifier-side state checks session identifiers, freshness, duplicates, and sequence order.

Accepted windows go to a motion classifier. A separate abnormality detector checks for unusual sensor patterns.

We'll use the same data, splits, attacks, and timing methods when comparing the different system versions.

---

# Week 1: Initial Research and Planning

## Week 1 summary

During Week 1, I
- Helped narrow the project
- Selected head motion as the first sensing task
- Defined the 5 motion classes
- Planned the Quest data format and trial process
- Separated authentication, classification, and abnormality detection
- Reviewed the assigned research papers
- Planned the attacks and evaluation
- Helped divide responsibilities
- Created most of the first presentation
- Wrote the 1 page research spec

The biggest lesson was that authentication and abnormality detection solve different problems.
A replayed valid window may look normal to the SNN, but authentication should reject it as old or duplicated.
A correctly authenticated window may still contain unusual sensor behavior if the data was changed before it received a valid tag.

## Project scope decisions

We selected these motion classes
- nod
- shake
- look_left_return
- look_right_return
- still

We chose head motion before hand tracking because it gives us a smaller first problem.
The first action window lasts 2 seconds and targets 120 samples at 60 Hz.

A trial contains
1. A 1 second prompt
2. A 2 second action
3. A 1 second rest

still means no intentional movement during the 2 second action window. It isn't the same as the rest period.

## Data plan

The first window format includes
- Head position
- Quaternion orientation
- Capture timestamps
- Tracking-valid status
- Device ID
- Session ID
- Trial ID
- Window ID
- Sequence number
- Motion label

I also identified data leakage as a major risk.
We won't randomly place pieces of one trial into training and testing. Complete trials and sessions must stay in one split.

## Model plan

The model order is
1. Logistic regression
2. Random forest
3. SNN classifier
4. Separate abnormality detector

LightGBM may be added after logistic regression and random forest work.

The SNN won't handle authentication keys or tags. It only processes windows that pass the authentication gate.

## Attack plan

Authentication should handle
- Same session replay
- Prior session replay
- Cross device substitution
- Cross session substitution
- Payload changes after tagging
- Protected metadata changes
- Duplicates
- Stale or reordered windows

The abnormality detector should evaluate
- Noise
- Drift
- Timestamp jitter
- Dropped samples
- Frozen poses
- Sudden pose jumps

## Evaluation plan

We plan to compare
1. Conventional classifier without authentication
2. SNN without authentication
3. Authenticated data with a conventional classifier
4. Authenticated data with an SNN

Planned measurements include
- Accuracy
- Precision and recall for each class
- F1 for ecah class
- Macro-F1
- Confusion matrices
- Attack rejection
- Authentication false accepts and false rejects
- Abnormality false positives
- Authentication latency
- Inference latency
- Total post-window latency

## Literature reviewed

| Source | Main lesson | How it affected the project |
|---|---|---|
| Nair et al., 2023 | VR motion can help identify users. | We treat motion as sensitive data and use pseudonymous IDs. |
| Cha et al., 2026 | PUF-derived keys can support XR authentication. | It gives us the closest authentication reference, but our PUF must be labeled simulated. |
| Eshraghian et al., 2023 | LIF SNNs can be trained with surrogate gradients. | It supports the first snnTorch classifier plan. |
| Rafique and Cheung, 2020 | VR tracking can be blocked or changed. | It supports testing freezes, noise, missing data, and jumps. |
| Shoaib et al., 2025 | XR attacks can be studied with detailed logs. | We'll record the attack, decision, reason, and latency. |
| Bäßler et al., 2022 | SNNs can detect unusual time-series patterns. | It supports testing a separate abnormality detector. |
| Li et al., 2023 | SNNs can classify temporal human activity. | It supports using head motion as the first classification task. |
| Sharmin et al., 2019 | SNNs can still be affected by adversarial inputs. | We won't assume the SNN is automatically robust. |

## Week 1 deliverables

- First research specification
- First presentation
- Research question
- Threat model
- Quest sensing and data plan
- Attack plan
- Evaluation plan
- Literature tables
- Tool plan
- Responsibility split
- First month plan
- Works cited
- Initial repository layout

## Feedback received

Dr. Garcia said the direction was much stronger, but it was still a plan instead of an implementation ready specification.

The main requested changes were
- Use measurable targets
- Clearly say the PUF is simulated
- Make the research gap statement more careful
- Define the Quest data process in detail
- Test leakage with code
- Simplify the first PUF design
- Train conventional models before the SNN
- Define abnormality detection separately
- Reduce the number of first-month attacks
- Keep a cumulative research log
- Produce working code and results

---

# Week 2: Revisions and First Implementation

## Week 2 summary so far

I've
- Read Dr. Garcia's full feedback
- Updated the research question
- Replaced vague goals with starting numerical targets
- Made the data and split rules more exact
- Defined the first abnormality experiment
- Prepared the pilot configuration and schemas
- Prepared the synthetic generator
- Prepared the validator
- Prepared the first data and leakage tests
- Reorganized the repository
- Updated the research plan and literature matrix

The original synthetic-data run produced 1,800 windows, passed the standalone validator, and passed 5 automated tests. After the Week 2 presentation, Dr. Garcia requested expanded evidence and documentation. I completed the expanded run on September 15: the saved dataset matched fixed-seed regeneration, all 21 expanded tests passed, and the analysis produced the requested tables, figures, sample window, environment record, and split-overlap evidence.

## Main Week 2 changes

| Feedback | Change |
|---|---|
| The success criteria were vague | Added starting targets for rejection, false rejects, macro-F1 change, and latency |
| The slides implied a physical Quest PUF | Changed the project to a software prototype using a simulated noisy PUF |
| The research gap was too absolute | Changed it to “based on our targeted review so far” |
| The data plan needed more detail | Added the Unity inputs, coordinate frame, quaternion rules, resampling, and validity rules |
| Leakage needed to be tested | Added trial and session leakage checks |
| The PUF design was too complicated | Removed unsupported PUF and error-correction choices |
| The SNN came too early | Put logistic regression and random forest first |
| The abnormality target was unclear | Defined a separate clean-versus-changed experiment |
| The attack list was too large | Split attacks into required and later tiers |
| Faculty wanted working evidence | Prepared the generator, validator, and tests |

## Current data choices

The synthetic pilot uses
- 6 synthetic device groups
- 3 sessions per device
- 20 trials per class in each session
- 5 motion classes
- 120 samples per window
- 1,800 total windows
- Random seed 7

The split is
- Session 1 for training
- Session 2 for validation
- Session 3 for testing

The 1,800 windows should be divided into
- 600 training windows
- 600 validation windows
- 600 testing windows
- 360 windows for each motion class

These counts were observed in the original run. The windows aren't claimed to be statistically independent, and the device groups don't model stable physical-headset differences.

## Current validation rules

The validator checks
- Required fields
- 120 samples per window
- Sample order
- Increasing timestamps
- No timestamp gap above 50 ms
- Normalized quaternions
- Quaternion sign continuity
- At least 95% valid tracking
- Positive window duration
- Unique window IDs
- Correct sequence numbers
- One split per session
- No source-trial leakage

## Current abnormality definition

A normal example is an untouched clean window.
A suspicious example is a clean window changed by one documented Tier-2 transform before authentication.
The first detector will be supervised because the synthetic program gives us the correct label.
The first models will be logistic regression and random forest. A separate SNN abnormality model comes later.

## Expanded Week 2 evidence run

I ran these commands from the official repository

python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python src/python/scripts/analyze_synthetic_data.py --run-tests --machine-model "HP Pavilion Plus Laptop 16-ab1xxx"

The run recorded
- 1,800 windows and 216,000 samples
- 600 windows in each split and 360 windows in each class
- 20 windows per class in every device-session group
- 0 missing saved sample slots, extra samples, invalid tracking flags, rejected windows, validation errors, and resampling events
- 0 prohibited window, source-trial, trial, or complete-session ID overlaps
- the expected overlap of the same 6 synthetic device/profile IDs across the cross-session splits
- an exact match between the saved dataset and regeneration with seed 7
- 21 passed tests, 0 failures, 0 errors, and 0 skipped tests in 10.381 seconds

The analysis also produced a complete sample window, a human-readable evidence report, a machine-readable evidence record, representative class trajectories, and a device/session comparison.

## Current environment

- Computer: Windows laptop
- Machine model: HP Pavilion Plus Laptop 16-ab1xxx
- Pilot configuration: `configs/pilot.json`
- Window schema: `schemas/quest-window.schema.json`
- Generator seed: 7
- Planned model seeds: 7, 17, and 27
- Original Week 2 Python version: 3.12.7 through an MSYS-based virtual environment
- Expanded evidence Python version: 3.13.14 in the Windows virtual environment
- Unity and OpenXR versions: waiting for lab confirmation

## Current blockers

| Item | What I'll check | What faculty or the lab must confirm |
|---|---|---|
| Quest setup | Headset inventory, developer mode, ADB, and existing setup | Which devices we can use and who controls access |
| Computer setup | Unity, Android, OpenXR, Python, and Git requirements | Which computer is approved for deployment |
| Human data | Keep current work synthetic | Which pre-clearance tests and recordings are allowed |
| Latency | Report median and p95 by stage | Whether the starting targets are appropriate |
| Data storage | Draft storage and deletion rules | Which approved service and policy to use |
| Main split | Explain the limits of each split | Whether cross-session should be the main pilot claim |
| FPGA work | Define the required software results first | Whether and when hardware work should begin |

### September 8, 2026 — Synthetic data testing

**Completed:** I ran the scripted head motion generator, standalone validator, and automated tests.

**Artifact produced:** The generator created 1,800 synthetic windows using schema v0.2. I recorded the results in `results/week-2/keegan/keegan.md`.

**Evidence:** The dataset contained 600 windows in each split and 360 windows for each motion class. All 5 automated tests passed. The tests checked valid data, repeatable generation, class balance, quaternion validation, session leakage, and source-trial leakage.

**What I learned:** The current generator and validation pipeline work together correctly. The split tests also showed that the validator can catch the two main leakage mistakes included in the current test suite.

**Current limitation:** These results only validate synthetic data and the rules currently implemented in the code. They do not prove that the data matches real Quest 3 motion or that it supports accurate classification.

**Next step:** Review a few generated records, confirm the shared sensor window interface with Will, and prepare the same schema for the Quest logger.

### September 15, 2026 — Expanded Week 2 evidence

**Completed:** I reran the generator and validator, then ran the expanded data and split test suite through `analyze_synthetic_data.py` using the machine model `HP Pavilion Plus Laptop 16-ab1xxx`.

**Provenance:** The run used repository commit `3936cc60377368dead0bbfa692df113cb41c7798` with a clean working tree. The generated dataset SHA-256 was `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`.

**Results:** The saved dataset exactly matched regeneration with seed 7. It contained 1,800 windows, 216,000 samples, 600 windows per split, and 360 windows per class. All 21 tests passed in 10.381 seconds with no failures, errors, or skipped tests. The analysis found no missing saved sample slots, extra samples, invalid tracking flags, rejected windows, dataset validation errors, or resampling events.

**Split evidence:** Window IDs, source-trial IDs, trial IDs, and complete session IDs had zero overlap between every split pair. The same 6 synthetic device/profile IDs intentionally appeared in all three splits because the experiment is cross-session rather than cross-device. No human participant data was used.

**Artifacts:** The analysis created `keegan-evidence.md`, `keegan-evidence.json`, `representative-trajectories.png`, `device-session-variability.png`, and `data/examples/sample-window.json`.

**Interpretation:** The results provide inspectable evidence that the generator, schema, validator, and split checks work together at the recorded commit. The plots also show the current limitation: orientation templates overlap across device and session groups, and the small position differences come from trial noise instead of calibrated device or session effects. This does not establish physical realism or real Quest performance.

### Shared tasks

- Agree on the exact authenticated-window format.
- Define the first 5 Tier-1 tests.
- Finish the faculty decision memo.
- Update both research logs.
- Prepare the revised presentation.

## Week 2 feedback received after the presentation

Dr. Garcia said the project framing and separation of responsibilities were much stronger. She also said the weekly report needs inspectable, reproducible evidence rather than statements that an artifact or test exists.

For my Week 2 synthetic-data work, the required additions are
- repository URL and relevant source commit
- exact recreation commands in the README
- the complete generator configuration and seed
- schema field descriptions, types, units, valid ranges, and a sample window
- exact motion-generation settings and limitations
- class counts by device and session
- missing-data, tracking, rejection, fixed-grid/resampling, and quality counts
- each test's purpose, expected result, and actual result
- identifier lists and prohibited-overlap checks for every split
- representative class trajectories and device/session variability figures
- an explanation that device groups don't provide class information or model physical devices

She also clarified that the primary split is cross-session, not cross-device or cross-person, and that personal-computer timing must include the machine and software context.

## Week 3 conventional classifier update

I implemented logistic regression and random forest using 840 relative-position and relative-quaternion features per window. Labels, identifiers, timestamps, tracking flags, and other metadata are excluded from the classifier input. Session 1 is training, session 2 is validation, and session 3 is testing.

The first Week 3 run reported 1.0000 for both models. I did not treat that as a real performance claim. The baseline audit found 480 exact orientation trajectories shared between test and training windows; orientation-only and combined features therefore reached 1.0000 on the original fixed-template data. Position-only accuracy was lower at 0.6167 for logistic regression and 0.5967 for random forest.

I corrected the generator by adding deterministic per-trial variation to position, orientation, timing, noise, drift, and still-motion behavior. The regenerated 1,800-window dataset still has 600 windows per split and 360 windows per class. The corrected diagnostic found zero exact test-to-training orientation matches, zero exact combined-feature matches, and zero near-duplicate orientation pairs under the 1e-6 tolerance. All 28 Python tests passed, the generated data passed validation, and the run used generator seed 7 with model seeds 7, 17, 27, 37, and 47.

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | p95 preprocessing + inference |
|---|---:|---:|---:|---:|
| Logistic regression | 0.8825 +/- 0.0000 | 0.9017 +/- 0.0000 | 0.9032 +/- 0.0000 | 0.9447 +/- 0.1519 ms |
| Random forest | 0.8607 +/- 0.0024 | 0.8933 +/- 0.0033 | 0.8936 +/- 0.0033 | 14.1448 +/- 1.4158 ms |

The values are means +/- sample standard deviations across model seeds. The corrected ablations gave 0.3533/0.3250 position-only accuracy, 0.8733/0.9000 orientation-only accuracy, near-chance permuted-label accuracy, and 0.1900 safe-metadata-only accuracy for logistic regression/random forest. Identifier-only accuracy remained 1.0000 because synthetic identifiers contain class names; identifiers remain excluded from the real feature matrix.

The timing measurements use 20 warm-up predictions, 600 individual one-window predictions, and `time.perf_counter_ns()`. Both measured preprocessing-plus-inference p95 values are below the provisional 20 ms classifier-stage target. They do not include authentication, abnormality detection, or the rest of the authenticated system.

The Quest logger correction also completed: the Unity EditMode suite now has all 9 tests passing in 0.043 seconds. The tests cover queued artificial-stream processing, fixed-grid interpolation, quaternion normalization and sign continuity, zero-orientation rejection, timestamp-gap rejection, tracking thresholds including exactly 114 valid samples out of 120, and JSONL writer validation. No human-derived motion data was collected.

Recorded baseline environment: HP Pavilion Plus Laptop 16-ab1xxx, Windows 11, Intel64 Family 6 Model 170 processor, CPython 3.13.14, NumPy 2.5.3, scikit-learn 1.9.1, and Matplotlib 3.11.2.
Repository: https://github.com/Keellonn/PUF-SNN  
Corrected implementation and results commit: `e4e0523d9232ded6c7ff266fd5d495a8c8d31fc0`
Base commit reported by the corrected diagnostic: `2c11de84bf4e321e81ce34d88dd371a25e7d8cc6`  
Corrected pilot configuration SHA-256: `7e9b12fa8679c9fe08e9396b1a9ea0f3c36465afce07f666c6d5817021924846`  
Corrected dataset SHA-256: `752b009588f3e721a8bf2f8f8fcd1cdf0f7e998446b60953dd34dd5e9e54d661`  
Original audited dataset SHA-256: `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`  
Working tree status during the corrected run: not clean because the fixes had not been committed yet

# Week 4: Authenticated Window Integration

## Shared interface and ownership agreement

I confirmed the authenticated-window contract with Will before continuing the integration work. We agreed that HMAC-SHA-256 covers the complete canonical `protected` object, motion values use fixed eight-decimal strings, and the tag remains in a separate `authentication` object. I am responsible for converting validated Quest windows into the protected motion payload and ensuring that rejected verifier decisions cannot reach inference. Will is responsible for PUF credential reconstruction, session-key derivation, tag verification, verifier-owned replay and sequence state, and the authentication attack measurements.

The protected object now includes the protocol and schema versions, device, session, and window identifiers, sequence number, capture bounds, data-quality summary, and all 120 processed motion samples. Labels, dataset splits, predictions, and verifier audit decisions remain outside the trusted sender message.

## Cross-language representation and inference gate

I implemented the Python authenticated-window builder, deterministic canonical serializer, strict JSON schema, test-only golden-vector generator, and authentication-to-inference gate. The canonicalization rules use sorted compact UTF-8 JSON, exactly eight decimal places for position and quaternion values, round-half-even behavior, normalized negative zero, integer timestamps and quality counts, and rejection of nonfinite values.

I also implemented the Unity canonical writer. Python and Unity produced the same SHA-256 value for the shared artificial motion window. The saved canonical object contains 24,308 bytes and has SHA-256 `87c89fca1426ed031788192fbcee551e91036f5d72301da4a7d5137f63bfdf2d`. The public test-only key produced expected HMAC-SHA-256 `b8ae3c52deefcb0432334388671bf82f8fec41b1a2f7edb016f5012301a882e1`.

The final targeted evidence had all 8 authenticated-window and golden-vector Python tests pass in 0.025 seconds, all 4 inference-gate tests pass in 0.013 seconds, and all 13 Unity EditMode tests pass. The Unity total includes the original nine logger tests and four new tests for the 95 percent boundary, Python golden hash, nonfinite-value rejection, and protected-motion mutation.

The inference gate requires an accepted verifier result to match the device, session, window, and sequence number in the protected message. A rejected or mismatched result stops before feature processing or inference. The accepted-path test also confirms that the fixed-decimal transport representation preserves the conventional-classifier feature vector.

Repository: https://github.com/Keellonn/PUF-SNN  
Authenticated-window interface commit: `e1c4bf4775e1b4c63657167f46edc5d6e7e72cee`  
Cross-language serialization, inference-gate, tests, and evidence commit: `9bb890c84a23dfef2ecf087292e5d772328c92c5`

## Next modeling step

1. Connect the verifier implementation and derived test session key to the agreed authenticated-window interface.
2. Run and document the five Tier-1 authentication attacks with exact expected and observed rejection reasons.
3. Measure authentication latency and total post-window latency using the stable integrated path.
4. Begin the SNN baseline after the Tier-1 integration path is reproducible and its current limitations are documented.
5. Continue Quest logger work without collecting or retaining human-derived motion data unless an approved later phase changes that scope.

---

# Hours and Work Log

Hours below don't include pre employment work. Those were my test trial hours.

## Tuesday, September 1, 2026 - 3.08 hours

### 1:00 PM - 2:10 PM - 1.17 hours

- Read Bäßler et al.'s SNN abnormality-detection paper.
- Studied how an SNN can identify unusual time-series patterns.
- Used the paper to support adding abnormality detection to the project.
- Separated motion classification, abnormality detection, and authentication.
- Added the paper to the literature table and presentation.

### 8:15 PM - 10:10 PM - 1.92 hours

- Drafted the first research specification.
- Refined the research question.
- Documented the 5 motion classes and initial trial plan.
- Added the 2-second window and 60 Hz target.
- Separated authentication attacks from sensor abnormalities.
- Added the first evaluation measurements.
- Organized and corrected the references.


## Wednesday, September 2, 2026 - 2.92 hours

### 6:25 PM - 9:20 PM - 2.92 hours

- Finished the first research specification.
- Made the data plan more specific.
- Clarified the jobs of the PUF, authentication layer, classifier, and abnormality detector.
- Explained the architecture and responsibility split to Will.
- Finished the PUF and authentication slides with Will's information.
- Revised the slide wording and terminology.
- Updated Responsibilities, and first month plan.
- Checked that the slides and specification matched.
- finished up all slides, onboarded will

## Thursday, September 3, 2026 - 0.75 hours

### 1:00 PM - 1:45 PM - 0.75 hours

- Weekly meeting
- Talked about Dr. Garcia & Sadman Italy trip, what to do the next week
- Listened to Zeeshawns presentation about bit flipping & bypassing security features within LLMs

## Saturday, September 5, 2026 - 0.75 hours

### 1:05 PM - 1:50 PM - 0.75 hours

- Read Dr. Garcia's full feedback
- Identified the difference between our plan and an implementation-ready specification
- Listed the required changes
- Planned how the 4 system conditions could use the same data and splits.

## Monday, September 7, 2026 - 5.55 hours

### 9:26 AM - 12:03 PM - 2.62 hours

- Redesigned the repository completely
- Separated code, schemas, configurations, tests, documentation, and results.
- Identified which files belong in Git and which are generated locally.
- started on markdowns, did ones for data, overall project
- Reviewed four additional papers on SNN motion classification, XR authentication, system latency, and adversarial robustness to help refine our literature matrix, model comparisons, threat model, and evaluation plan.

### 1:30 PM - 4:26 PM - 2.93 hours

- Updated the research log formatting, started on my research log
- Turned Dr. Garcia's feedback into specific technical changes.
- Updated the literature review structure.
- Replaced the research-gap statement.
- Defined logistic regression and random forest as the first models.
- Planned a fair comparison using the same data, splits, and seeds.
- Drafted the first SNN settings.
- Defined the supervised normal-versus-suspicious experiment.
- Organized attacks into 3 tiers.
- Drafted starting accuracy, security, and latency targets.
- Separated the 2-second recording period from processing latency.
- Put this information in our new Spec and my research log

## Tuesday, September 8, 2026 - 3.73 hours

### 3:50 PM - 4:39 PM - 0.82 hours

- Created faculty decision memo
- Did research to come to my decisions
- Updated what questions we still have
- Did quest logging markdown

### 5:54 PM PM - 8:49 PM - 2.92 hours

- Created generator.py & validation.py
- Created markdown for xr snn
- Created generate_data.py
- Created validate_data.py
- Created all schemas
- Created test_data.py
- Created test_splits.py
- Tested all tests
- Fixed file path and environment issues
- Generated 1.8k syntehhetic head motion windows, checked data format, timestamps, tracking quality, train/test seperation
- All 1.8k windows passed validation and all 5 automated tests passed
- Updated week 2 results markdown

## Wednesday, September 9, 2026 - 3.06 hours

### 6:25 AM - 9:29 PM - 3.06 hours

- Redid my portion slideshow, all slides are now actual slideshow ready
- Added a custom theme that I made all slides match and did the flow chart for the project
- Changed up information to update our metrics we decided on this week
- Created speaker notes for each slide, with exactly what I wanted to say / include for presenting
- Updated research log, add instructions to my results
- Added week 2 slides, aka the stuff I did in the repo / my scripts and what they do
- Practiced presenting each slide

## Thursday, September 10, 2026 - 1.28 hours

### 12:55 PM - 2:12 PM - 1.28 hours

- Weekly meeting
- Listened to Neal presentation on his project with Zeeshawn
- Listened to Amruth's research he did this week to help Sadman
- Presented SNN + PUF week 1 & 2 progress with Will, answered questions
- This presentation went over the amount of time it should've taken. I will make sure to improve on that next presentation

### Sunday, September 13, 2026 - 2.88 hours

#### 9:02 pm - 11:55 pm - 2.88 hours

- Added logistic regression and random forest classifiers using 840 relative position and quaternion features per window
- Kept labels, IDs, timestamps, and other metadata out of the model input
- Added five classifier processing tests covering features, metadata exclusion, quaternion continuity, split separation, and incomplete windows
- Used the previously validated Week 2 synthetic dataset as the initial classifier input
- Updated the dataset filename and fixed a Matplotlib plotting error
- Both models correctly classified all 600 synthetic test windows, although this does not represent expected performance on real Quest data.
- Logistic regression reached 0.5417 ms p95 latency. Changing random forest to one thread reduced its p95 from about 65 ms to 22.4288 ms, slightly above the 20 ms target.

### Monday, September 14, 2026 - 2.67 hours

#### 5:10 PM - 7:50 PM - 2. 67 hours

- Talked to zeeshawn and  confirmed that five Quest headsets are currently available, not 6. One has been missing for months
- Met with lab manager Tessa received permission from Tessa to take Quest 3 headset labeled number 2 home for project work
- Created a new Windows user on the lab computer so my project files and accounts would be separate from those of other researchers.
- Spent a large part of the session troubleshooting the new Windows account because it repeatedly loaded into a black screen. The computer had to be force restarted twice before the account became usable.
- Created  Unity Hub account
- Installed Unity 6.6 6000.6.0f1 with Android Build Support, the Android SDK and NDK tools, and OpenJDK.
- Confirmed that Git was installed, it was with version 2.51.0.windows.1 Python was not installed, but it is not currently required because Python development is being completed on my personal laptop.
- Created a Meta developer account and checked for a lab organization invitation. No invitation or organization membership was visible. Spoke with Zeeshawn and he said there wasn't one for his Quest 3 work either
- Attempted to configure Meta Horizon software but encountered an unexpected download location error, then talked with Zeeshawn and he said I was supposed to skip it, so I didn't inquire further on that issue. When 
- Cloned the shared PUF-SNN GitHub repository onto the lab computer using PowerShell, had to debug since some issues came up
- Created the initial `QuestLogger` Unity project inside the repository.
- Confirmed that Input System 1.20.0 was installed and identified that XR Plug in Management and OpenXR still need to be installed
- After a lot of issues, located and ran Unity’s bundled ADB tool. ADB started correctly, but Headset 2 did not appear in the connected device list, so USB debugging and device recognition still need to be completed, I will be doing this tomorrow
- Corrected the Unity project location to `src/quest-logger/QuestLogger` and reopened it from its new location in Unity Hub
- Configured my Git author information locally for the repository
- Committed but didn't push the initial Unity project, including its Assets, Packages, and ProjectSettings files. I thought I pushed it but forgot to verify, as soon as I'm in the lab tommorrow I will.

## Tuesday, September 15, 2026 - 4.98 hours

### 5:10 PM - 7:03 PM - 1.88 hours

- Returned to the lab computer and successfully pushed the initial Unity Quest Logger project after the previous push failed
- Confirmed that the Unity Assets, Packages, and ProjectSettings files reached GitHub
- Pulled the updated repository onto my personal laptop and verified the Unity project location
- Reviewed Dr. Garcia’s complete feedback on the Week 2 synthetic-data work
- Identified the missing configuration, schema, testing, provenance, figures, and results requirements
- Planned the necessary changes while keeping the primary experiment labeled as cross-session rather than cross-device

### 8:05 PM - 11:11 PM - 3.10 hours

- Updated `pilot.json`, the Quest window schema, the synthetic generator, the validator, and the XR / SNN documentation
- Clarified the motion-generation settings, data fields, units, valid ranges, tracking rules, and current device / session limitations
- Expanded `test_data.py` and `test_splits.py` from 5 tests to 21 tests covering schema validity, sample ordering, quaternions, tracking thresholds, identifiers, and split leakage
- Added `analyze_synthetic_data.py` to generate reproducible tables, figures, environment details, hashes, and test evidence
- Regenerated and validated 1,800 synthetic windows and 216,000 samples - all 21 tests passed with no validation errors
- Confirmed that the saved dataset matched fixed-seed regeneration and had zero prohibited identifier overlap
- Generated the sample window, JSON and Markdown evidence reports, representative trajectory figure, and device/session comparison figure
- Updated the README, Week 2 results, and research log with the commands, commit ID, dataset hash, evidence, interpretation, and limitations
- Updated `train_baselines.py` to record the machine, software environment, timing method, warm-up count, prediction count, source commit, and working-tree status
- Reran all five baseline-processing tests and both conventional classifiers from a clean commit; all tests passed and both models retained perfect classification scores
- Recorded the updated latency results: 0.3896 ms p95 for logistic regression and 21.6515 ms p95 for random forest
- Updated the Week 3 results and research log with the reproducible timing environment and provenance

## Wednesday, September 16, 2026 - 3.17 hours

### 4:55 PM - 8:05 PM - 3.17 hours

- Created the Unity Quest logger models, head-pose capture, window processor, JSONL writer, and trial controller scripts
- Used `Application.onBeforeRender` to queue position, quaternion, tracking-valid, tracking-state, and monotonic timestamp values without writing files during capture
- Added linear position interpolation and quaternion SLERP to create exactly 120 ordered samples for each 2 second window
- Added rejection rules for timestamp gaps above 50 ms, insufficient capture coverage, and tracking validity below 95 percent
- Added deterministic prompt, capture, and rest scheduling for the five head-motion classes
- Added Unity assembly definitions and three EditMode tests for sample generation, timestamp-gap rejection, and tracking-quality rejection
- Added `validate_quest_log.py` so future logger JSONL files can be checked with the existing schema and quality rules.
- Updated the Quest logger documentation and reformatted the C# files to match the existing project style.
- Installed Unity 6.6.1f1 with Android Build Support, OpenJDK, and the Android SDK and NDK tools.
- Opened and upgraded the existing `QuestLogger` project on my personal laptop
- Installed XR Plug-in Management, OpenXR, and Unity OpenXR support for Meta Quest
- Activated the Meta Quest build profile and completed the required XR Project Validation fix
- Confirmed that the Unity project compiled without Console errors
- Ran the Quest logger EditMode tests successfully and saved the test results as Week 3 evidence
- Kept human-derived recording disabled - no headset motion data was collected or retained
- Finished week 3 new presentation, based on new week 3 results, as last week Will and I presented

## Thursday, September 17, 2026 - 0.92 hours

### 1:05 PM - 2:00 PM - 0.92 hours

- Agenda for this week, word of the week
- Watched both presentations, first about the Kirchoffs key, then about digital twins

## Sunday, September 20, 2026 - 3.22 hours

### 6:52 PM - 10:05 PM - 3.22 hours

- Reviewed the entirety of Dr. Garcia's feedback
- Reviewed the Week 3 baseline results after the original perfect classifier scores were diagnosed as fixed-template leakage
- Updated the synthetic generator and reran the data generation, validation, Python tests, and baseline diagnostics
- Confirmed that all 28 Python tests passed, the regenerated 1,800-window dataset passed validation, and the corrected baseline results were about 0.90 test accuracy instead of 1.0000
- Documented the original 480 exact training to test orientation matches and confirmed that the corrected data had zero exact orientation or combined-feature matches
- Reviewed the updated classifier latency measurements, including preprocessing plus inference p95 values below the provisional 20 ms classifier-stage target
- Fixed the Unity Quest logger test and writer issues, then confirmed that all 9 Unity EditMode tests passed.
- Updated my Week 3 results documentation and research log with the corrected baseline results, diagnostic evidence, test totals, logger results, and current limitations
- Updated the Week 3 slideshow content and speaker notes so the slides use the corrected metrics, explain the original leakage issue, replace the outdated 3-test result, and show the correct next Tier 1 integration work before beginning the SNN baseline

## Monday, September 21, 2026 - 3.35 hours

### 9:15 PM - 12:36 AM - 3.35 hours

- Confirmed the shared authenticated-window design with Will, including that HMAC-SHA-256 covers the complete canonical protected object, motion values use fixed eight-decimal strings, and the authentication tag remains outside the protected object
- Confirmed that I am responsible for building the validated motion payload and controlling entry into inference, while Will is responsible for connecting the reconstructed credential, session-key derivation, and verifier logic
- Added the strict authenticated-window JSON schema and documented the versioned interface between the Quest motion pipeline and authentication layer
- Implemented deterministic Python serialization using sorted compact UTF-8 JSON, fixed eight-decimal motion strings, round-half-even behavior, and negative-zero normalization
- Added input checks that reject short windows, tracking coverage below 95 percent, invalid sample structures, and nonfinite motion values before authentication
- Added a shared test-only golden vector containing the canonical protected message, schema-valid authenticated envelope, expected SHA-256 hash, and expected HMAC-SHA-256 tag
- Confirmed that the generated canonical message contains 24,308 bytes and has SHA-256 hash `87c89fca1426ed031788192fbcee551e91036f5d72301da4a7d5137f63bfdf2d`
- Added the Python inference gate so rejected authentication decisions cannot reach feature processing or classification
- Added tests confirming that verifier results must match the correct device, session, window, and sequence number before the motion payload can proceed
- Added the Unity canonical message writer and confirmed that Unity produces the same canonical SHA-256 value as Python
- Ran all eight Python window-message and golden-vector tests successfully
- Ran all four Python inference-gate tests successfully
- Ran all 13 Unity EditMode tests successfully, including the four new canonical-serialization tests
- Saved the generated shared artifacts, Python test evidence, and Unity Test Runner screenshot in the Week 4 results folders
- Committed and pushed the initial authenticated-window interface as `e1c4bf4775e1b4c63657167f46edc5d6e7e72cee`
- Committed and pushed the cross-language serialization, inference-gate, tests, and evidence as `9bb890c84a23dfef2ecf087292e5d772328c92c5`
- Updated the Week 4 results and research log with the recorded evidence, limitations, and repository provenance

## Wednesday, September 23, 2026 - 4.92 estimated hours

### 7:03 PM - 11:58 PM - 4.92 hours

- Reviewed the completed authentication-to-classifier integration with Will and confirmed the final division of responsibilities
- Updated my work from the initial authenticated-window prototype to the final Wire Protocol 2.0 classifier boundary
- Confirmed that rejected, modified, replayed, low-quality, and incorrectly attributed windows cannot reach the classifier
- Confirmed that accepted windows are released exactly once as 120 samples containing seven relative-pose channels
- Ran all 12 classifier-integration tests successfully
- Created the deterministic recurrent SNN configuration using three random seeds
- Implemented the SNN data loader using the existing training, validation, and testing sessions
- Kept labels, identifiers, timestamps, tracking values, and split metadata out of the SNN input
- Added training-only normalization and checks for input shape, split separation, metadata exclusion, and reproducibility
- Implemented the recurrent leaky integrate-and-fire model, training loop, early stopping, evaluation metrics, confusion matrices, and CPU latency measurements
- Added and ran 14 SNN data, model, and authenticated-integration tests successfully
- Ran the official three-seed SNN baseline using the corrected synthetic dataset
- Recorded mean test accuracy of 85.50 percent and mean test macro-F1 of 85.51 percent
- Confirmed that the SNN finished 4.81 percentage points below logistic regression and met the provisional maximum five-point gap
- Recorded mean median inference latency of 9.7660 ms and mean p95 inference latency of 14.5208 ms
- Reviewed the combined confusion matrix and identified still motion and shake as the most difficult classes
- Saved the SNN metrics, training histories, confusion matrices, latency evidence, environment information, and reproducibility manifest
- Updated the Week 4 results, XR and SNN design, pilot configuration, limitations, and research documentation
- Corrected the Week 3 baseline slide by removing the misleading perfect confusion matrix from the original flawed dataset
- Updated the Week 3 validation slide to remove next steps that were completed during Week 4
- Added a shared slide explaining the final authenticated classifier boundary and the ownership split between Will and me
- Added slides covering the SNN architecture, training configuration, three-seed results, conventional-model comparison, and inference latency
- Added the combined SNN confusion matrix and explained the largest class errors
- Added a Week 4 validation and scope slide separating completed work from remaining real-Quest, total-latency, and abnormality-detection work
- Added speaker notes and matched the new diagrams and slides to the existing presentation style