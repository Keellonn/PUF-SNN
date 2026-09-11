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
- README documentation
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

## Next step

The next step is Layer 2: credential reconstruction.

I will use the measured PUF behavior to determine how a noisy PUF response can be converted into a repeatable stable secret.

This will include

- Selecting a justified helper-data / error-correction approach
- Measuring reconstruction success
- Measuring failed reconstruction / session false-rejection behavior
- Determining how the reconstructed secret should feed the session-authentication layer

After stable reconstruction works, the next step will be session and window authentication using HMAC-SHA-256.

# Week 1 Hours
*Not an active employee for the first week.

# Week 2 Hours

# Tuesday September, 9
## 11:07am - 4:34pm
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
**Hours to be added in from saved desktop notes
# Thursday September, 11
## 4:12pm - 5:18pm
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