# Keegan Hoyne's Research Log

**Owner:** Keegan Hoyne  
**Current week:** Week 3  
**Last updated:** September 15, 2026

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

The original synthetic-data run produced 1,800 windows, passed the standalone validator, and passed 5 automated tests. Those results are recorded below. After the Week 2 presentation, Dr. Garcia requested expanded evidence and documentation, so the revised checks still need a separate run before their results are reported.

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

## Expanded Week 2 tests and evidence to run

From the official repository, I'll run these commands

python -m pip install -e .
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python src/python/scripts/analyze_synthetic_data.py --run-tests --machine-model "YOUR LAPTOP MODEL"

Afterward, I'll record
- Python version
- Commands
- Number of tests passed or failed
- Number of generated windows
- Class counts
- Split counts
- Validation errors
- Problems and fixes
- Git commit ID
- My interpretation

## Current environment

- Computer: Windows laptop
- Pilot configuration: `configs/pilot.json`
- Window schema: `schemas/quest-window.schema.json`
- Generator seed: 7
- Planned model seeds: 7, 17, and 27
- Original Week 2 Python version: 3.12.7 through an MSYS-based virtual environment
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

**Artifact produced:** The generator created 1,800 synthetic windows using schema v0.2. I recorded the results in `results/week-2/keegan.md`.

**Evidence:** The dataset contained 600 windows in each split and 360 windows for each motion class. All 5 automated tests passed. The tests checked valid data, repeatable generation, class balance, quaternion validation, session leakage, and source-trial leakage.

**What I learned:** The current generator and validation pipeline work together correctly. The split tests also showed that the validator can catch the two main leakage mistakes included in the current test suite.

**Current limitation:** These results only validate synthetic data and the rules currently implemented in the code. They do not prove that the data matches real Quest 3 motion or that it supports accurate classification.

**Next step:** Review a few generated records, confirm the shared sensor window interface with Will, and prepare the same schema for the Quest logger.

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

I implemented logistic regression and random forest using 840 relative-position and relative-quaternion features per window. Labels, identifiers, timestamps, tracking flags, and other metadata were excluded from the classifier input.

Session 1 was used for training, session 2 for validation, and session 3 for testing. Five baseline-processing tests passed in the recorded run.

| Model | Validation macro-F1 | Test accuracy | Test macro-F1 | Median inference | p95 inference |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 1.0000 | 1.0000 | 1.0000 | 0.29 ms | 0.5417 ms |
| Random forest | 1.0000 | 1.0000 | 1.0000 | 14.38 ms | 22.4288 ms |

Both models classified all 600 synthetic test windows correctly. These results show that the software pipeline works on the current generator, not that it will achieve perfect performance on real Quest data. The fixed class templates and lack of stable device/session motion effects can make the classification task artificially easy.

The timing measurements cover model prediction only. Logistic regression is below the provisional 20 ms post-window target for this stage, but the complete pipeline hasn't met that target yet. Random forest is slightly above it.

Recorded baseline environment: Python 3.13.14 on Windows 11, NumPy 2.5.3, scikit-learn 1.9.1, and Matplotlib 3.11.2. The machine model wasn't recorded.

Recorded source commit: `975fb10651857955fc7e3b0414691fe5508d9b47`  
Recorded dataset SHA-256: `0e29a1091db2a82968e75ef879934cb3164c38f4df874766f2c29c76b3231f00`

## Next modeling step

1. Install the revised Week 2 configuration, schema, generator, validator, and tests.
2. Commit those source changes and record the source commit ID.
3. Rerun the expanded Week 2 evidence and inspect the generated tables and figures.
4. Commit the generated evidence and updated results.
5. Rerun the conventional baselines against the revised, validated dataset.
6. Confirm the shared authenticated-window interface with Will.
7. Submit the Tier-2 abnormality design before implementing the detector.
8. Begin the full SNN and Tier-2 implementation after the required Tier-1 integration path is stable.

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

### Monday, September 14, 2026 - 2.88 hours

#### 9:02 pm - 11:55 pm - 2.88 hours

- Added logistic regression and random forest classifiers using 840 relative position and quaternion features per window
- Kept labels, IDs, timestamps, and other metadata out of the model input
- Added five classifier processing tests covering features, metadata exclusion, quaternion continuity, split separation, and incomplete windows
- Used the previously validated Week 2 synthetic dataset as the initial classifier input
- Updated the dataset filename and fixed a Matplotlib plotting error
- Both models correctly classified all 600 synthetic test windows, although this does not represent expected performance on real Quest data.
- Logistic regression reached 0.5417 ms p95 latency. Changing random forest to one thread reduced its p95 from about 65 ms to 22.4288 ms, slightly above the 20 ms target.

### Tuesday, September 14, 2026 - 2.67 hours

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
