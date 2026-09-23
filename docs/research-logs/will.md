# William's Research Log

**Owner:** William Wallace 
**Current week:** Week 2
**Last updated:** September 10, 2026

# Current research question
Can a software prototype using a simulated noisy PUF-derived session credential reject replayed, modified, or misattributed Quest 3 head-motion windows before SNN inference while meeting our attack-rejection, macro-F1-loss, and latency targets?

# My Portion of the Project

I am responsible for, the simulated PUF, PUF measurements, credential reconstruction, session authentication, protecting and verifying each window, and Authentication attacks and results
Together we will complete the window format, threat model, integration, review of literature, presentation, and the final evaluation.

# Week 1: Project Onboarding and PUF / Authentication Planning

## Week 1 summary
During Week 1, I
- Joined the project and took ownership of the PUF / authentication side
- Reviewed the initial research specification, presentation, and project architecture
- Learned the role of PUFs within the proposed authentication pipeline
- Helped separate device authentication from SNN classification and abnormality detection
- Helped define the initial threat model and authentication attack categories
- Reviewed the initial PUF enrollment, session-authentication, and window-protection ideas
- Helped refine the project responsibilities and first-month plan
- Helped prepare and revise the first presentation
- Identified the main technical areas I needed to study before implementing the PUF simulator

The main goal of Week 1 was to understand how my part of the project connected to the full system before beginning implementation.

The most important distinction was that the PUF is used to establish device/session trust, while the authentication gate protects individual sensor windows. The SNN does not perform cryptographic authentication.

## Initial PUF / authentication plan

I devided my portion of the initial system into three stages:

1. Simulate device-specific PUF behavior
2. Reconstruct stable credential material from noisy PUF responses
3. Use the reconstructed credential for session and window authentication

The intended system flow was:
Simulated PUF → credential reconstruction → session authentication → protected Quest window → authentication gate → SNN inference
At this stage, these were design concepts rather than implemented components.

## Initial authentication threat model

The authentication side of the project was intended to detect

- Replayed windows
- Windows from the wrong session
- Windows from the wrong device
- Modified sensor payloads
- Modified protected metadata
- Duplicate windows
- Stale windows
- Reordered windows

We also separated these attacks from semantic sensor attacks such as noise, drift, freezes, and pose jumps.
Authentication should determine whether a window has the expected source, integrity, session, freshness, and order.
A separate abnormality detector determines whether an authenticated motion pattern itself appears suspicious.

## Initial PUF questions

Before implementation, I needed to determine

- What type of PUF should be simulated
- How simulated devices should differ from each other
- How noise should affect repeated PUF measurements
- How enrollment should be represented
- Which measurements should be used to evaluate the PUF
- Whether the design should behave more like a weak PUF / key source or a large challenge-response system
- How PUF behavior would eventually connect to credential reconstruction

## Week 1 deliverables

- Defined my PUF / authentication responsibilities
- Initial PUF and authentication architecture
- Initial authentication threat model
- Initial attack categories
- Responsibility split
- First-month implementation plan
- Contributions to the first research specification
- Contributions to the first presentation

## Feedback going into Week 2

Dr. Garcia's feedback showed that the project needed to move from a high-level plan toward an implementation-ready specification.

The main changes affecting my portion were

- Clearly label the PUF as simulated
- Simplify the initial PUF design
- Separate PUF behavior, credential reconstruction, and authentication into distinct layers
- Measure raw PUF behavior before selecting error correction
- Justify future reconstruction methods using measured results
- Define exactly what the authentication layer protects
- Reduce the number of attacks required for the first pilot
- Produce working code, reproducible experiments, and measurable results

# Week 2: Simulated PUF Implementation and Evaluation

## Week 2 summary

During Week 2, I

- Read and organized Dr. Garcia's feedback for the PUF / authentication portion
- Reduced the PUF design into three clearly separated layers
- Studied ring-oscillator PUF behavior and the measurements needed for the pilot
- Designed a configurable software model of a noisy RO-PUF
- Built the simulated PUF in Python
- Implemented enrollment reference responses and repeated noisy measurements
- Implemented BER, reliability, uniqueness, and uniformity measurements
- Added deterministic random seeds for reproducible experiments
- Added automated tests and configuration validation
- Generated plots for PUF behavior
- Added documentation and an easy-to-run PowerShell launcher
- Integrated the simulator into the shared repository
- Re-ran the project from a separate laptop to verify reproducibility and setup instructions
- Updated my assigned presentation slides to match the revised system design

The main Week 2 result is a working Layer 1 PUF behavior model.

## Three-layer PUF / authentication design

I separated my portion of the system into three layers.

### Layer 1 - Simulated PUF behavior

Simulated PUF behavior → device-specific noisy response bits → BER / reliability / uniqueness / uniformity
This is the part implemented during Week 2.

### Layer 2 - Credential reconstruction

Noisy PUF response → helper data / error correction → stable secret
This will be designed using the behavior measured in Layer 1 rather than assuming an error-correction method in advance.

### Layer 3 - Session and window authentication

Stable secret → session authentication → session key → HMAC-protected Quest windows → authentication gate → SNN
This comes after credential reconstruction works reliably.

## Simulated RO-PUF design

The simulator models a ring-oscillator PUF.
Each simulated device contains a set of ring oscillators with persistent manufacturing variation.
Two oscillators are compared to generate one response bit:
- If RO A is faster than RO B, the response bit is 1
- Otherwise, the response bit is 0

The current baseline uses

- 6 simulated devices
- 128 ring oscillators per device
- Adjacent oscillator pairing
- 64 response bits per device
- Configurable measurement noise
- Repeated PUF readings
- A fixed random seed for reproducibility

Manufacturing variation is generated once when the device is created and remains persistent across later measurements.
Measurement noise is generated again during each reading so that the simulator can model unstable response bits.

## How to Run

Instructions on how to run and setup the simulation are given in the file: puf-auth-design.md
Within that markdown are exact instructions on how to configure and run the simulation.

## Enrollment reference

Each simulated device is measured under reference conditions to create an enrollment reference response.
The enrollment response acts as the baseline response for that device.
Later noisy readings are compared against the enrollment response to measure how much the PUF changes between readings.
This is not yet the final cryptographic enrollment protocol. It only provides the reference needed to characterize PUF behavior.

## PUF measurements

The simulator currently measures four primary properties.

### Raw bit error rate

BER measures the fraction of response bits that differ between a later noisy reading and the enrollment reference.

### Reliability

Reliability measures how consistently the same device reproduces its enrolled response.

Lower BER corresponds to higher reliability.

### Uniqueness

Uniqueness compares enrollment responses from different simulated devices.

The goal is for different devices to produce meaningfully different responses.

### Uniformity

Uniformity measures the fraction of response bits that are 1.
This is used to check whether responses contain a reasonable balance of 1s and 0s.

## Experiment pipeline

The implemented experiment follows this process:

1. Load one experiment configuration
2. Create simulated devices
3. Generate persistent manufacturing characteristics
4. Perform an enrollment read
5. Store a reference response for each device
6. Perform repeated noisy readings
7. Compare each reading with its enrollment reference
8. Calculate BER and reliability
9. Compare different devices for uniqueness
10. Calculate response uniformity
11. Save experiment results
12. Generate plots

## Plots produced

The simulator produces plots for

- Same-device versus different-device Hamming-distance behavior
- BER versus measurement-noise level
- Response uniformity across devices

These plots provide a visual check that the simulator behaves in the expected direction.

## Reproducibility and testing

The simulator is configuration driven so that one configuration controls an experiment.
Random seeds are used so that the same configuration and seed can reproduce the same simulated devices and measurements.
I also added automated tests for

- Device creation
- Persistent manufacturing variation
- RO pairing and response generation
- Configuration validation
- BER
- Reliability
- Uniqueness
- Uniformity
- Random-seed behavior
- Experiment execution

The simulator was integrated into the shared repository and successfully run on a second computer using the repository setup instructions.
This helped verify that the project was not only working on my original development environment.

## Software and documentation work

I also completed

- A PowerShell simulation launcher
- Requirements and environment setup
- Configuration documentation
- Code cleanup and humanization
- Shared-repository integration
- Cross-machine validation
- Revised presentation slides

The simulator can now be cloned, configured, and run from the shared repository without relying on my original local development environment.

## What I learned

The biggest lesson from Week 2 was that a PUF response should not immediately be treated as a cryptographic key.
The first step is to measure how the simulated PUF actually behaves.
Manufacturing variation creates the differences between devices, while measurement noise can cause the same device to produce slightly different responses across readings.
This is why BER, reliability, uniqueness, and uniformity need to be measured before selecting a credential-reconstruction method.
I also learned that enrollment at this layer is simply the creation of a reference response. The more complicated helper-data and key-reconstruction process belongs to the next layer.

## Current limitations

The current implementation

- Is a software simulation rather than a physical Quest PUF
- Does not yet perform credential reconstruction
- Does not yet implement helper data or error correction
- Does not yet derive session keys
- Does not yet authenticate Quest sensor windows
- Does not model long-term aging beyond leaving room for it in the design
- Uses a simplified environmental model that will need refinement if environmental effects are studied in more detail

These limitations are intentional because Week 2 focuses only on measuring PUF behavior before moving into authentication.

## Week 2 deliverables

- Configurable simulated RO-PUF
- Enrollment reference generation
- Repeated noisy PUF measurements
- BER measurements
- Reliability measurements
- Uniqueness measurements
- Uniformity measurements
- Noise-sweep experiments
- PUF behavior plots
- Automated tests
- Reproducible experiment configuration
- Simulation launcher
- Simulator documentation
- Shared-repository integration
- Cross-machine execution test
- Updated Week 2 presentation material

## Pairing design choice

Adjacent disjoint pairing was selected as a simple and reproducible preliminary construct for the software pilot. There is no need to introduce more complexity such as random pairing tables or having oscillators being depended on for multiple bits. Anyone who runs the simulator will understand immediately which oscillators form the response bits.
128 ROs -> 64 fixed comparisons -> 64-Bit response (This is very basic and easy to understand)
Since the pairs are disjoint, an oscillator does not influence multiple response bits. This makes the interpretation much cleaner, if bit 12 were to become unstable it will be very easy to find the specific pair rather than a large connection of shared comparisons.
Another important note is that the main focus of the project is treating the PUF as a device-bound source for credential reconstruction, not looking for a massive challenge-response authentication system. So adjacent pairing allows the focus to be on questions that matter more. 
Does the device produce a repeatable response?
How noisy is that response?
Are different devices different?
Can the noisy response reconstruct a stable credential?

Other pairing options I looked at,
Fixed randomized disjoint pairing:
- Would introduce another random variable
- Does not provide any real benefit that adjacent pairing does not already have
- Would require storing the pairing map to understand data
Overlapping adjacent pairing:
- Comparisons would share oscillators
- A frequency shift in one oscillator could potentially influence multiple response positions
- The statistical structure is harder to interpret
Challenge-selection pairing
- This could provide many challenge response pairs
- However, this requires defining a challenge interface
- Moves the project toward a strong PUF authentication model rather than the current scope

Limitation:
This simulator does not yet model physical oscillator placement so conclusions regarding the physically adjacent ring oscillators cannot be drawn from this experiment.

## Metric Definitions

### Raw Bit Error Rate (BER)

For device d, let R_d be the 64-bit enrollment/reference response and X_d,t be a later noisy reading.

BER_d,t = H(R_d, X_d,t) / 64

Thus, the implemented raw BER is the normalized Hamming distance between a device's reference response and a later reading from the same device.
The simulator reports the BER:
- per read in metrics.csv
- per device in devices.csv
- per run in summary.csv
- per noise sweep point in noise_sweep_summary.csv

## Enrollment / Reference-Response Procedure

Each simulated device is created using persistent manufacturing variation which is fixed across the measurements.

For the baseline experiment, the enrollment/reference response is generated using:
- environmental offset = 0.0
- measurement noise standard deviation = 0.0
- aging disabled

A single 64-bit reference response is generated for each device.
The response is not averaged or majority-voted.

That same stored reference response is used when calculating BER and reliability for all later noisy measurements of that device.

## Enrollment limitation

The current enrollment procedure is idealized since the reference response is generated with zero measurement noise. 

This simplifies the Week 2 behavioral evaluation however, it does not yet measure the effect of noisy enrollment on later credential reconstruction. The layer 2 reconstruction experiments should test if stable credential recovery remains possible with more realistic enrollment conditions.

## Generated Plots

### Plot 1, Same-device vs different-device Hamming distance

The same-device measurements compare the noisy baseline reading against the enrollment/reference response of the same simulated device. Different-device measurements compare the enrollment responses of every unordered pair of simulated devices.
In thyis six-device run, the same device distances are concentrated close to zero and the large majority below 0.10. In contrast, the 15 inter-device reference comparisons are concentrated between around 0.40 and 0.60. No visible overlap occurs between the two distributions in this run.
The behavior is consistent with the intention of the simulator, repeated measurements of the same simulated device remains closely to its reference response where as different simulated devices differ in around half of their response bits. The seperation shows evidence that the simulated manufacuring variation creates device specific response while the noise produces substantially slammer within device variation.

### Plot 2, BER vs Measurement Noise

This experiment varies measurement-noise standard deviation while retaining the same simulated devices and fixed enrollment responses. The tested noise levels are 0.0, 0.05,
0.10, 0.25, 0.50, and 1.0. 
Raw BER increases as the measurement noise increases. At zero noise, the repeated response matches the noiseless enrollment reference. As the noise rises, the BER follows and rises with it.
The result demonstrates that the simulator responds in the expected direction with an increase to noise. Increasing measurement uncertainity causes more oscillator pair orderings to change and thus increases the response bit's instability.
The nominal 0.10 noise operating point produces the raw BER of around 3% in this representative run, which is consistent with the baseline 20 run experiment. This error level appears low enough to justify investigating a credential reconstruction, error-correcting mechanism although, BER alone does not demonstrate that reconstruction will succeed. Layer 2 needs to measure actual reconstruction-success and false-rejection rates for the selected code. 

### Plot 3, Uniformity by Device

Uniformity is calculated from taking the fraction of bits in an enrollment/reference response that are equal to 1. The dashed line indicates 0.5 meaning a perfect balance of zeros and ones.
The six devices in this run produce reference response unifomities from around 0.41 to 0.55. Five of the six devices are very close to that 0.5 reference while one is much lower at around 0.41.
These results show that the current response are not dominated by either zeros or ones in their response. The 20 run experiment also confirms this. 
It is important to understand that uniformity near 0.5 does not establish cryptographic entropy, independence between response bits, or key strength. It only measures the balance of zeros and ones of these responses.

## Response Bit bias and Stability

To determine if individual PUF response positions exhibited systematic bias or unusually high instability, the corrected set of 20 six-device baseline simulations was pooled. 

The analysis included:
- 20 independent seeded runs
- 6 devices per run
- 120 total enrollment/reference responses
- 100 baseline noisy reads per device
- 12,000 noisy responses
- 12,000 repeated-read comparisons per bit position
- 768,000 total bit comparisons

### Response bit balance

Across the 64 response positions, the fraction of enrollment responses equal to 1 ranged from 39.17% to 60.83%, with an average of 50.07%.

Bit 56 had the lowest observed fraction of ones at 39.17% where as bit 15 has the highest at 60.83%.

No response position approached an all-zero or all-one population. These results thus do not indicate a fixed bit-position bias in the current sample. However, it is not established that the bit positions are statisically unbiased across future simulated or physical devices.

### Response bit instability

The per-bit repeated-read flip rates ranged across 1.53% - 5.31%.

The most unstable observed bit was bit 61 which had a 5.31% flip rate.
The highest 5 observed flip rates occured at bits:
- Bit 61, 5.31%
- Bit 23, 5.03%
- Bit 47, 4.54%
- Bit 7, 4.29%
- Bit 41, 4.27%

The mean per-bit flip was 3.207552% which perfectly matches the raw BER calculated over the same dataset. 


The results show an overall measureable variation in stability between bit positions however, the do not establish that specific positions are intrinsically unstable. More device samples would be needed to determine if these patterns are to persist.

## Testing Reliability and Uniqueness Change when Measurement Noise and Device Variation are Changed Independantly

Manufacturing standard deviation was varied from 0.25 to 2.0 within a fixed environment. The raw BER decreased from 11.31% at manufacturing std at 0.25 to roughly 1.45% at 2.0. And reliability went from 88.69% to 98.55%. Meaning that larger device-specific oscillator offesets will increase the comparison margin between paired oscillators and making noise less likely to reverse a response bit. 
The inter-device uniqueness stayed constant throughout the experiment. It held 47.71%. Under the current model, manufacturing variation scales zero-mean per-oscillator offsets, while response bits only depend on which oscillator in each pair has a larger frequency. Then, positive rescaling changes the magnitude of pairwise differences but it does not change the ordering for the same seeded devices. Thus, the enrollment responses remain unchanged as the manufacturing standard deviation changes.
The result of this identifies a limitation of the current behavioral model, manufacturing_std controls the seperation margin and thus reliability under measurement noise, but it will not alter the expected response ordering or uniqueness. Maybe a future physical or more detailed process could include process effects that may cause a change in uniqueness with changes in manufacturing conditions.

## Next step for Week 3

The next step is Layer 2: credential reconstruction.
I will use the measured PUF behavior to determine how a noisy PUF response can be converted into a repeatable stable secret.

This will include
- Selecting a justified helper-data / error-correction approach
- Measuring reconstruction success
- Measuring failed reconstruction / session false-rejection behavior
- Determining how the reconstructed secret should feed the session-authentication layer

After stable reconstruction works, the next step will be session and window authentication using HMAC-SHA-256.


## Week 3 Baseline

Layer 2 will begin from the frozen Week 2 PUF simulator.

PUF configuration:
- Devices: 6
- Ring Oscillators: 128
- Pairing Scheme: Adjacent
- Response Length: 64
- Manufacturing variation: 1.0
- Environmental Variations: 0.0
- Measurement noise: 0.1
- Aging: 0
- Repeated readings: 100

Week 2 simulation measurements (20 Different Simulations):
Mean:
- Raw BER: 3.2075521%
- Reliability: 96.7924479%
- Uniqueness: 49.578125%
- Uniformity: 50.0651042%

Standard Deviation:
- Raw BER: 0.4237424%
- Reliability: 0.4237424%
- Uniqueness: 1.6093045%
- Uniformity: 2.785459%

Min:
- Raw BER: 2.2630208%
- Reliability: 95.7682292%
- Uniqueness: 45.625%
- Uniformity: 45.0520833%

Max:
- Raw BER: 4.2317708%
- Reliability: 97.7369792%
- Uniqueness: 52.6041667%
- Uniformity: 55.7291667%

The simulated PUF shows an average BER of 3.207552083%. The reliability is 96.792447917%.
The inter-device uniqueness averages to 49.578125000% meaning that the responses from different simulated devices differ in almost half of their bits.
The uniformity averaged to 50.065104167% meaning that there is almost a perfect balance between zeros and ones.

These measurements and readings are the Layer 1 Baseline for selecting the layer 2 credential-reconstruction mechanism.

# Credential Reconstruction Design Memo

## PUF Response and Measured Error Behavior

### Available PUF Response Length
The current simulated design contains 128 ring oscillators with fixed adjacent disjoint pairing. The pairs follow this structure:
(RO0, RO1), (RO2, RO3), ... , (RO126, RO127)

Each pair produces one response bit using this comparison:
response[n] = 1 if frequency(RO[2n]) > frequency(RO[2n+1])
reponse[n] = 0 If anything else

Since each is use in exactly one pair, the design currently creates a fixed 64-Bit response.
Credential reconstruction must operate on the 64 response bits that are currently available from my previous Layer 1 design. This layer 2 design will not assume a 255 bit or larger PUF response unless the PUF construction is changed/re-evaluated.

### Measured Error Behavior

My baseline configuration is as follows: 
PUF configuration:
- Devices: 6
- Ring Oscillators: 128
- Pairing Scheme: Adjacent
- Response Length: 64
- Manufacturing variation: 1.0
- Environmental Variations: 0.0
- Measurement noise: 0.1
- Aging: 0
- Repeated readings: 100

For this dataset, 12,000 noisy PUF readings produced 768,000 bit comparisons against their corresponding reference responses.
BER = 24,634 / 768,000 = 3.207552 %

The mean per-bit flip was also the same, 3.207552% meaning that the calculation and response bit analysis are consistent.

It is important to understand that error behavior is not the same across all response bit positions.
Thus, the credential reconstruction design must not be based on the assumption that every response fails the same. The simulator contains meaningful variation in stability between bit positions.

### Reconstruction Requirement

The layer 2 design must tolerate the error behavior measured in the week 2 operating condition while recovering the same credential from repeated readings of the same simulated device.

The measured BER established the starting point for the error correction design. The final correction will not be chosen just from the BER alone. The success must be evaluated against the distribution of bit errors within the 64-bit response readings.

The selected construction should provide error-correction margin for ordinary noise readings while still allowing reconstruction failure to be detected when the response contains more errors than the construction can reliably correct.

## Target Reconstructed Secret Length

### Initial Target

The initial Layer 2 design will target reconstruction of a 32-bit device credential from the current 64-bit simulated PUF response.

The reconstructed credential is intentionally shorter than the 64-bit response allowing for reconstruction construction to devote a substantial portion of the available response bits to error-correction redundancy.

The goal is to demonstrate that repeated noisy responses from the same simulated device are able to reproduce the same credential with a measurable reconstruction success rate and false rejection rate.

The 32-bit credential is not made to have production strength cryptographic security. It is a simple software-pilot parameter that allows the credential reconstruction mechanism to be developed and evaluated using the current 64-bit PUF response.

### Reconstructed Credential vs. Session HMAC Key

It is important to understand that the reconstructed 32-bit credential and the session HMAC key are different.

The reconstructed credential will serve as the input to key-derivation in the future. A later stage may use HKDF-SHA-256 to derive a 256-bit per session HMAC key from the reconstructed credential.

Producing a 256-bit output from HKDF will not increase the entropy of the original reconstructed credential. Thus, the inital design must not claim 256 bits of cryptographic security just because the derived HMAC key is that long.

If there is a need for stronger credential entropy further in the future, the PUF response source will need to provide an additional validated entropy.

## Credential-Reconstruction Construction

### Selected Construction

The initial Layer 2 design will use a code-offset construction with a binary BCH (63,36,t=5) error-correcting code.

The current PUF simulation yeilds a 64 bit response. The first reconstruction design will use a fixed 63 bit subset of that response since a 63-bit block is a natural length for the selected BCH code.

Thus one response bit will go unused by the initial reconstruction construction. This is a deliberate simplification and will not require changing the validated Week 2
PUF-response design.

BCH (63,36,t=5) can represent a 36-bit message in a 63-bit codeword and will allow to correct as many as five bit errors in that codeword.

### Design Reasoning

Binary BCH construction was selected since the observed PUF errors occur directly as binary response-bit flips. BCH codes provide a configurable bit-error correction capability and can be matched very closely to the available 64-bit PUF response.

Several alternatives were considered,
- A repetition code could be simple however, it would consume a large amount of the available response bits just to protect a small credential meaning it would be inefficient.
- A Hamming code would only bring limited correction capability compared to the error distribution measured.
- The previously proposed BCH(255,63,t=30) construction was rejected for the current design because the validated PUF produces only 64 response bits. Selecting a 255-bit code would require changing the PUF response rather than designing around the behavior that was actually measured.

BCH(63,36,t=5) fits the existing response length while keeping enough message capacity for the planned 32-bit pilot credential.

### Preliminary Reconstruction-Success Expectation

At the measured BER of 3.21%, a 63-bit response would contain roughly 2.02 erroneous bits.

A BCH code that can correct up to five errors would provide correction margin beyond the average observed error count.

Under a simplified independent model with BER = 3.207552%, the probability of five or less errors in 63 bits is around 98.4%.

This value is only an analytical plan. The Week 2 results show that response-bit flip rates are not identical across different bit positions, and independence between bit errors has not been established. Thus, the reconstruction success rate and false rejection rate must be measured using the existing simulated PUF responses.

### Stored Material

Device side material:
- BCH/helper data value W
- Reconstruction configuration
- Credential verification information

The device will not persistently store the reconstructed credential itself within the initial design. The credential will be reconstructed from the PUF reading.

Trusted verifier:
- Device enrollment identifier
- Corresponding credential or derived secret needed for later session-key establishment

The current threat model treats the verifier and enrollment database as trusted. So storing the verifier secret material is acceptable for the initial design however, the assumption must be made explicitly.

## Reconstruction Verification and False Rejection

### Reconstruction Verification

In the layer 2 experiment each device will have a known credential that is established during enrollment.
For each reconstruction attempt:
- Generate a noisy PUF response from the device
- Combine noisy response with the stored helper data
- Apply the BCH decoding to recover a credential
- Compare this against the credential that was stored during enrollment
- Record the attempt as successful only if the recovered credential is equal to the enrolled credential

This protocol will not require for the device to persistently store the credential for comparison. After the reconstruction is complete and validated, the reconstructed credential will be used to derive session-key material and show possession to the trusted verifier.

### Reconstruction Failure Conditions

A reconstruction attempt is unsuccessful if the BCH decoding reports the received word can't be corrected or the decoding produces a candidate credential that does not match the established credential from enrollment. 

For layer 2, a false rejection happens when a real reading from the correct device fails to reconstruct the credential that was enrolled.
FRR = real reconstruction failures / total real reconstruction attempts

A real attempt uses:
- The correct simulated device
- That device's correct helper fata
- The intented operating condition
- No adversarial modifications

Results will contain both reconstruction success rate as well as the false-rejection rate.
Reconstruction success rate = 1 - FRR.

### Reconstruction Experiment Outputs

Every reconstruction attempt will record:
- Device ID
- Random seed
- PUF BER for the reading
- Number of differing response bits
- Reconstructed credential
- BCH decode result
- Credential match and mismatch
- Reconstruction success and failure
- Reconstruction latency

### Transition to Session Authentication
After successful reconstruction the credential that is recovered will not be directly used for the per-window HMAC key. It will rather be used to serve as an input to a session key-derivation step.

The anticipated flow will go as follows:
- PUF response
- Credential Reconstruction
- Reconstructed credential
- Session Key Derivation
- Per session HMAC key
- HMAC-SHA-256 protection of sensor window messages

The needed layer 3 session message and key derivation details will be implemented only once Layer 2 reconstruction is validated.

## Limitation of Reconstruction Design

The current limiations are:
- The PUF response is made from a synthetic simulator
- Enrollment is idealized and noiseless
- The current response length is only 64 bits
- The planned 32 bit credential is perfect for test reconstruction but not production grade security
- The BCH(63,36,t=5) construction must be validated experimentally rather than assumed to be successful
- Bit error idependence has not been established

# Hours and Work:

# Tuesday September, 9
## 11:07am - 4:34pm (5.45 Hours)
- Continued RO-PUF simulation development
- Implemented device model:
    - Persistent manufacturuing variation
    - Fixed device RO characteristics across measurements that are repeated
    - Configurable noise measurements with each PUF readings
- Implemented the RO-PUF response generation:
    - RO frequency calculation
    - Implemented adjacent oscillator pairing
    - 64 Bit response generation from 128 ROs
- Added an enrollement reference generation so noisy readings can be compared to a stored baseline
- Implemented PUF evaluation metrics
    - Bit error rate (BER)
    - Reliability
    - Device uniqueness
    - Uniformity of response
    - Hamming distance calculations
- Built baseline experiment pipeline
    - Multiple simulated devices
    - Enroll each device
    - Perform repeated PUF readings
    - Calculate and save experiment results
- Added plots to the results section using matplotlib
    - Same device, hamming distance
    - BER vs measured noise
    - Uniformity across devices
- Reviewed results and validated design
- Tested reproducibility with the random seed generation
# Wednesday September, 10
## 4:28pm - 7:16pm (2.80 Hours)
- Created PowerShell script, 'run_simulation.ps1' that runs a script to run simulation after setup.
- Created step by step instructions on how to run the PUF simulator
- Explained the overview of the simulator and how it works
- Integrated my design into Keegan's created repository
- Had to fix path/directory issues within the new shared repo
- Tested the simulation in a different environment from start to finish to validate the design
- Validated that the simulation reproduces the same results with the same configuration and seed.
## 8:43pm - 9:59pm (1.27 Hours)
- Worked on slideshow:
    - Updated existing slides towards Dr. Garcia's feedback
    - Narrowed scope of the project
    - Updated deliverables to have more detail
    - Showed a clear seperation in work between Keegan and I
# Thursday September, 11
## 12:02am - 12:36am (0.57 Hours)
- Finalized slideshow, and prepared for presenting in meeting
- Added speaker notes to ensure I hit the correct topics in the presentation
- Added my week 2 progress into the slideshow
## 1:00pm - 2:12pm (1.20 Hours)
- Weekly team meeting:
    - Listened to Amruth's presentation on the work he did for Zeeshawn
    - Listened to Ayush's presentation on the work he did for Sadman
    - Presented with Keegan our week 1 and week 2 progress
    - Answered PUF related questions
## 4:12pm - 5:18pm (1.10 Hours)
- Cleaned up literature landscape comparison matrix
- Added information to literature-review markdown including:
    - Review method
    - Research gap
    - Technical contribution
- Added information to puf-auth-design markdown including:
    - Description of design
    - How to run the simulator
    - Results and Reproducibility section
- Organized a few more files into the repository to maintain cleanliness and organization

# Monday September, 14
## 8:46pm - 10:19pm (1.55 Hours)
- Measured and sorted the baseline layer 1 PUF simulator
- Created a spreadsheet, layer1baseline.csv
- Used it to sort statistics of the PUF simulator before reconstruction
- I ran 20 simulations with different seeds and logged:
    - Seed
    - Raw BER
    - Reliability
    - Uniqueness
    - Uniformity
- Then I found the mean, standard deviation, min, and max for each metric

# Tuesday September, 15
## 5:16pm - 6:52pm (1.60 Hours)
- Organized Week 2 evidence of the design based off of Dr. Garcia's feedback:
    - Repo/commit
    - Highlighted in research log where to find the commands
    - Highlighted in research log how to configure
    - Explained how my pairing produced 64-Bit response
- Added a deep analysis of why I picked adjacent pairing and the other options I could have chosen.

# Wednesday September, 16
## 8:31pm - 11:59pm (3.47 Hours)
- Corrected week 2 baseline dataset so that all 20 simulations used 6 devices
- Recalculated layer 1 baseline stats under that corrected dataset
- Established corrected mean raw BER of 3.207552%
- Documented formal definitions for BER, reliability, uniqueness, and uniformity
- Documented enrollment response method and its limitations
- Analyzed all three plots and explained in depth each of them and what they mean
- Analyzed response-bit bias across 120 enrollment responses
- Analyzed response-bit instability across 12,000 noisy PUF readings
- Validated per-bit flip-rate calculations against the raw BER

# Thursday September, 17
## 12:00am - 1:12am (1.20 Hours)
- Identified the most and least stable response bit positions
- Generated those response bit plots
- Tested the sensitivity of the metrics when changing the manufacturing variation with noise fixed
- Documented the limitations of the of the current PUF design
- Created the layer 2 credential-reconstruction design memo

## 1:51 - 4:32am (2.68 Hours)
- Selected a 32 Bit pilot reconstructed credential target
- Proposed a BCH(63,36,t=5) code offset
- Justified the BCH candidate using the measured 64 Bit response length and BER
- Estimated expected error count
- Defined false-rejection rate 
- Defined reconstruction success and failure conditions
- Explained the outputs of reconstruction outputs
- Defined what material will be stored
- Explained how to transistion into layer 3, once reconstruction is finalized
- Added my Week 3 work into Keegan and I's presentation

# 1:04pm - 1:50pm (0.77 Hours)
- Weekly meeting
    - Listened to Zane's presentation on Kirchhoff Law Johnson Noise Key exchange systems
    - Listened to Shreyas's presentation on digital twins
- Listened to presentation feedback to try and improve upon my own presentations

# Friday September, 18
## 2:00pm - 2:18pm (0.30 Hours)
- Senior Design PUF Consultation
    - Met with a senior design student, Jayden Jones, who is working on FPGA-based PUF application
    - Discussed my simulated PUF architecture
        - Ring oscillators
        - Adjacent Pairing
        - Baseline configuration
        - Weak PUF design
    - Explained how to evaluate PUF effectiveness
    - Explained in depth 6 metrics:
        - Bit error rate
        - Reliability
        - Uniqueness
        - Uniformity
        - Response bit bias
        - Per Bit stability
    - The discussion was mainly focused on how to test and characterize PUF responses
    - Topics brought up in discussion that were beyond my current design
        - FPGA implementation of PUF (Out of scope)
        - FPGA enrollment process (Out of scope)
        - Authentication process and design (Not currently implemented)
        - Strong PUF design (Out of scope)
    - Jayden indicated that major gaps in his research were about statistics and effictiveness testing and that my testing model was very useful for his team's design

# Monday September, 21
## 9:22pm - 11:47pm (2.42 Hours)
- Began implementing layer 2 reconstruction
- Defined the code-offset construction using the 64 bit simulated PUF response
    - Fixed 63 bit subset for BCH(63, 36, t = 5)
- Defined the 32 bit pilot credential with four padding bits with seperate enrollment behavior from reconstruction
- Developed the Layer 2 outcomes,
    - Successful reconstruction
    - Decoder failure
    - Invalid padding
    - Valid format miscorrection
# Tuesday September, 22
## 1:04pm - 4:17pm (3.22 Hours)
- Continued implementation for layer 2
- Completed the main enrollment and reconstruction flow:
    - Helper data generation
    - BCH decoding
    - Credential recovery
    - Structured reconstruction results
- Reviewed reconstruction behavior around the BCH correction limit and comfirmed that response outside the t=5 scope may fail or produce invalid padding
- Reviewed and elevated noise layer 2 results to understand the impact of noise
- Layer 2 experiment results,
    - 12,000 nominal reconstruction attempts
    - 11,805 correct reconstructions
    - 195 failures
    - Success rate: 98.375%
    - FRR: 1.625%
    - Breakdown of failures,
        - 186 Decoder failures
        - 7 invalid-padding results
        - 2 valid format wrong credentials

## 5:48pm - 7:45pm (1.95 Hours)
- Finalized layer 2
- Began implementation for a basic layer 3 design
- Defined the session establishment flow using,
    - Reconstructed credential
    - Fresh client/server nonces
    - Transcript
    - HKDF-SHA256 session key derivation
    - Mutual key comfirmation
- Defined the security boundary so that a valid but incorrect Layer 2 credential cannot create an authenticated session
- Began defining the canonical authenticated sensor window format
- Replaced the earlier decimal-serialization concept with an exact binary32/fixed-width representation to support Python/C# authentication

## 10:37pm - 11:59pm (1.37 Hours)
- Continued implementation for layer 3
- Developed the sender flow for,
    - Canonical window serialization
    - Sequence assignment
    - HMAC-SHA256 generation
    - Authenticated transport envelopes
- Developed the verifier flow for,
    - Parsing
    - Session lookup
    - HMAC Verification
    - Device and session binding
    - Quality checks
    - Strict replay and sequence enforcement
- Added session lifecycle behavior such as
    - Active
    - Closed
    - Expired
    - Failed
    - Replacement
    - TTL
    - Maximum window handling
- Added verifier audit behavior and began validating that rejected messages cannot modify trusted replay state or reach the accepted boundary


# Wednesday September, 23
## 12:00am - 12:36am ()
- Finalized layer 3 implementation

## 3:46pm - 6:22pm ()
- Added tier 1 attack implementation