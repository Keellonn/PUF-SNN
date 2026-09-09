# Keegan Hoyne's Research Log

**Owner:** Keegan Hoyne  
**Current week:** Week 2  
**Last updated:** September 8, 2026

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

A simulated noisy PUF helps create a device-bound session credential. The authentication layer checks the device, session, integrity, freshness, and order of each window.

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

I haven't recorded any test results yet. I'll run the code myself from the official repository before adding results.

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
- 6 simulated devices
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

These are expected values. I'll replace them with actual results after running the code.

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

## Tests I need to run

From the official repository, I'll run these commands

python -m unittest discover -s tests -p "test_data.py" -v
python -m unittest discover -s tests -p "test_splits.py" -v
python src/python/scripts/generate_data.py
python src/python/scripts/validate_data.py
python -m unittest discover -s tests -v

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
- Python version: add after checking
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

## Remaining Week 2 tasks

### My tasks

- Copy the final files into the official repository.
- Confirm the configuration and schemas are present.
- Run `test_data.py`.
- Run `test_splits.py`.
- Generate the complete dataset.
- Validate the complete dataset.
- Add more failure tests if needed.
- Record the real results.
- Add the Git commit ID.
- Complete the Quest setup checklist.
- Give Will the final window format.

### Shared tasks

- Agree on the exact authenticated-window format.
- Define the first 5 Tier-1 tests.
- Finish the faculty decision memo.
- Update both research logs.
- Prepare the revised presentation.

## Next modeling step

After the generator and validator work
1. Build feature extraction.
2. Fit normalization with training data only.
3. Train logistic regression.
4. Train random forest.
5. Report macro-F1 and per-class results.
6. Build the first SNN classifier.
7. Build the separate abnormality detector.

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

## Saturday, September 5, 2026 - 0.75 hours

### 1:05 PM - 1:50 PM - 0.75 hours

- Read Dr. Garcia's full feedback
- Identified the difference between our plan and an implementation-ready specification
- Listed the required changes
- Planned how the 4 system conditions could use the same data and splits.

## Monday, September 7, 2026 - 5.55 hours

### 9:26 AM - 12:03 PM - 2.62 hours

- Redesigned the repository for both work packages.
- Separated code, schemas, configurations, tests, documentation, and results.
- Identified which files belong in Git and which are generated locally.
- Simplified the documentation structure.
- Updated the research log formatting, started on my research log

### 1:30 PM - 4:26 PM - 2.93 hours

- Turned Dr. Garcia's feedback into specific technical changes.
- Updated the literature-review structure.
- Replaced the absolute research-gap statement.
- Defined logistic regression and random forest as the first models.
- Planned a fair comparison using the same data, splits, and seeds.
- Drafted the first SNN settings.
- Defined the supervised normal-versus-suspicious experiment.
- Organized attacks into 3 tiers.
- Drafted starting accuracy, security, and latency targets.
- Separated the 2-second recording period from processing latency.
