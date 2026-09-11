# Literature Review and Technical Landscape

**Version:** 0.2  
**Last updated:** September 11, 2026

## Review method
We searched IEEE Xplore, USENIX, SpringerLink, arXiv, Google Scholar, and official Unity/OpenXR documentation and research for publications from 2010 through September 2026. Search phrases included combinations of "XR authentication", "VR tracking attack", "head motion identification", "PUF key derivation", "PUF modeling attack", "spiking neural network motion classification", "SNN anomaly detection", "SNN adversarial robustness", and "XR latency". We included work that informs at least one part of our system: XR sensing or attacks, PUF-based trust, freshness and replay protection, SNN inference, anomaly detection, or latency evaluation. Papers without enough technical detail to affect the design or evaluation of our project, were excluded.

## Comparison matrix

### Nair et al. [1]
What it studied,
Head and hand motion can identify VR users
What we learned from it,
Motion data sometimes can be highly identifying and needs to be treated as sensitive
How it affects our project,
Treat motion as sensitive data and prevent split leakage
### Cha et al. [2]
What it studied,
PUF-derived keys can support lightweight XR authentication and session-key establishment
What we learned from it,
A PUF can establish a device trust and support session authentication
How it affects our project,
Use a simulated PUF-derived credential within the software prototype
### Rührmair et al. [3]
What it studied,
Exposed challenge-response behavior can be modeled by machine-learning
What we learned from it,
Some exposed PUF interfaces can be predictable if there is enough challenge-response data available
How it affects our project,
Modeling attacks will be optional until our PUF interface has been fully defined
### Herder et al. [4]
What it studied,
PUF outputs must have stability before key reconstruction can be reliable
What we learned from it,
PUF responses are noisy, meaninging their stability must be measured and strong before they can be usef for key reconstruction
How it affects our project,
Measure BER, reliability, uniqueness, and uniformity first, then error correction can be justified
### Eshraghian et al. [5]
What it studied,
Training methods for spiking neural networks
What we learned from it,
LIF neurons and surrogate-gradient training are good and practical starting points for temporal SNNs
How it affects our project,
We will use a small recurrent LIF network for the initial SNN classifier
### Rafique and Cheung [6]
What it studied,
The manipulation and disruption of VR tracking data
What we learned from it,
XR tracking streams can be frozen, manipulated, or corupted
How it affects our project,
We need to test sensor attacks such as freezes, missing samples, noise, drift, and pose jumps
### Shoaib et al. [7]
What it studied,
Controlled XR attacks with a logging structure and security evaluation
What we learned from it,
Attack-specific records and per-stage measurements can make security experiments easier to analyze and understand  
How it affects our project,
We log attack type, the authentication result, model output, and latency for tests
### Bäßler et al. [8]
What it studied,
A SNN-based anomaly detection on streaming multivariate data
What we learned from it,
SNNs can be used for abnormal-pattern detection however, this needs to be treated separately from normal classification
How it affects our project,
We need to use a separate abnormality detector rather than assuming classifier confidence alone is enough
### Li et al. [9]
What it studied,
SNN-based human activity recognition
What we learned from it,
SNNs can classify temporal motion patterns and can be useful for activity-style tasks
How it affects our project,
This can support head-motion classification as apart of a small SNN test case
### Stephenson et al. [10]
What it studied,
Authentication mechanisms protect certain trust properties, not the meaning of the sensor data
What we learned from it,
Authentication will only protect specific trust properties and will not solve every XR attack
How it affects our project,
Keep the authentication gate separate from abnormal-motion detection
### Huzaifa et al. [11]
What it studied,
End to end XR system performance and latency
What we learned from it,
XR systems can be sensitive towards processing delay, which menas latency needs to be measured carefully
How it affects our project,
We report per-stage processing latency and maintain the 2-second collection window, separate from post-window latency
### harmin et al. [12]
What it studied,
Adversarial robustness of spiking neural networks
What we learned from it,
SNNs cannot automatically resist adversarial inputs
How it affects our project,
Targeted model attacks are treated as a later-stage evaluation instead of an assumed strength of the SNN

## Research gap
Based on our review to date, we have not identified a study that evaluates all of the following in one reproducible framework. Simulated PUF-derived device and session authentication; Authenticated Quest head-motion windows; SNN motion classification and separate abnormality detection; Replay, cross-session, cross-device, and sensor-stream attacks; Per-stage accuracy, security, and latency measurements. Our focus is the interaction between these parts, not simply the individual technologies.

## Proposed technical contribution
The project is far greater than a simple chain of existing components since it states and measures the boundary between two differing secuity decisions. THe authentication gate chooses whetber a motion window has the expected source, integrity, session, freshness, and order. A separate inference stage classifies accepted motion, where as an anomaly module tests for physically suspicious patterns but validated. Every attack is assigned an injection point, expected defender, measureable outcome, same windows, splits. Attacks are used across four controlled system conditions. Making it possible to choose what each layer contributes and where the combined system can still fail.

## References
[1] V. Nair et al., “Unique Identification of 50,000+ Virtual Reality Users from Head & Hand Motion Data,” in *32nd USENIX Security Symposium (USENIX Security 23)*, 2023. Accessed: Sep. 7, 2026. [Online]. Available: https://www.usenix.org/conference/usenixsecurity23/presentation/nair-identification

[2] W. Cha, H. J. Lee, S. Kook, K. Kim, and D. Won, “A Lightweight Authentication and Key Distribution Protocol for XR Glasses Using PUF and Cloud-Assisted ECC,” *Sensors*, vol. 26, no. 1, p. 217, Dec. 2025, doi: 10.3390/s26010217.

[3] U. Rührmair, F. Sehnke, J. Sölter, G. Dror, S. Devadas, and J. Schmidhuber, “Modeling Attacks on Physical Unclonable Functions,” in *Proceedings of the 17th ACM Conference on Computer and Communications Security*, 2010. Accessed: Sep. 7, 2026. [Online]. Available: https://eprint.iacr.org/2010/251

[4] C. Herder, M.-D. Yu, F. Koushanfar, and S. Devadas, “Physical Unclonable Functions and Applications: A Tutorial,” *Proceedings of the IEEE*, vol. 102, no. 8, pp. 1126-1141, Aug. 2014, doi: 10.1109/JPROC.2014.2320516.

[5] J. K. Eshraghian et al., “Training Spiking Neural Networks Using Lessons From Deep Learning,” *Proceedings of the IEEE*, vol. 111, no. 9, pp. 1016-1054, Sep. 2023, doi: 10.1109/JPROC.2023.3308088.

[6] M. Rafique and S. Cheung, “Tracking Attacks on Virtual Reality Systems,” in *2023 IEEE Conference on Virtual Reality and 3D User Interfaces Abstracts and Workshops (VRW)*, 2023. Accessed: Sep. 7, 2026. [Online]. Available: https://scholars.uky.edu/en/publications/tracking-attacks-on-virtual-reality-systems/

[7] M. Shoaib et al., “REALITYCHECK: A Framework to Evaluate and Mitigate Security Threats in Extended Reality Systems,” in *34th USENIX Security Symposium (USENIX Security 25)*, 2025. Accessed: Sep. 7, 2026. [Online]. Available: https://www.usenix.org/conference/usenixsecurity25/presentation/shoaib

[8] K. Bäßler et al., “An Evolving Spiking Neural Network for Online Anomaly Detection in Multivariate Data Streams,” *Machine Learning*, 2022, doi: 10.1007/s10994-022-06129-4.

[9] C. Li et al., “Spiking Neural Networks for Event-Based Human Activity Recognition,” *Frontiers in Neuroscience*, vol. 17, 2023, doi: 10.3389/fnins.2023.1233037.

[10] B. Stephenson et al., “SoK: Authentication in Augmented and Virtual Reality,” in *2022 IEEE Symposium on Security and Privacy Workshops*, 2022. Accessed: Sep. 7, 2026. [Online]. Available: https://ieeexplore.ieee.org/document/9833742/

[11] M. Huzaifa et al., “ILLIXR: Enabling End-to-End Extended Reality Research,” in *2021 IEEE International Symposium on Workload Characterization (IISWC)*, 2021. Accessed: Sep. 7, 2026. [Online]. Available: https://experts.illinois.edu/en/publications/illixr-an-open-testbed-to-enable-extended-reality-systems-researc

[12] S. Sharmin et al., “A Comprehensive Analysis on Adversarial Robustness of Spiking Neural Networks,” 2019, arXiv:1905.02704. Accessed: Sep. 7, 2026. [Online]. Available: https://arxiv.org/abs/1905.02704