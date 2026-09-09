# Faculty Decision Memo

**Prepared by:** Keegan Hoyne  

## Decisions ready for faculty

### 1. Work allowed before human research approval

Virginia Tech guidance says research involving people or human-derived research data needs the proper HRPP determination before it begins.

Until then, we plan to work with
- Synthetic data
- Approved public data
- Software simulation
- Data validation
- Tool setup
- Scripted headset tests only if permitted

We won't recruit participants or save human motion recordings without approval.

**Decision needed:** Please confirm whether limited scripted headset tests are allowed before the HRPP decision and whether any resulting motion data may be saved.

### 2. Initial latency targets

We'll measure:

- Authentication latency
- Preprocessing latency
- Inference latency
- Total post-window decision latency
- Overhead compared with the same pipeline without authentication

The 2 second recording window isn't included in the processing target.

Our proposed starting targets are
- Authentication p95 of 1 ms or less
- Post-window decision p95 of 20 ms or less
- Authentication overhead of 10% or less

P95 means that 95% of measurements should be at or below the target.

If those targets are too strict for the first software prototype, our backup targets are

- Authentication p95 of 5 ms or less
- Post-window decision p95 of 50 ms or less
- Authentication overhead of 20% or less

**Decision needed:** We were going to start with the 1 ms, 20 ms, and 10% targets. Are these appropriate for the project, or should we use the backup targets?

## Work we need to finish before asking

### Quest 3 setup

Before asking you to confirm the headset setup, we still need to review
- The 6 headset inventory
- Existing lab documentation
- Meta developer organization requirements
- Developer mode requirements
- ADB setup
- Current headset and runtime versions
- The setup checklist

After that, we'll report what we verified and what remains unknown.

### Personal laptop or lab computer

Before asking for approval, we still need to compare
- Unity requirements
- Android SDK, NDK, and JDK requirements
- OpenXR and Meta XR requirements
- Python and Git requirements
- Personal laptop hardware
- Available lab-computer hardware
- Storage requirements

Our current decision is to use personal laptops for documentation, Git, synthetic data, testing, and small models. Quest deployment would use the approved lab setup if required.

### Installation and testing permission

Before asking who can approve installation, we need to document whether the project requires
- Headset developer mode
- A Meta developer account
- ADB access
- Lab administrator permission
- IT permission
- Permission to install Unity and Android tools

Once this is documented, faculty can approve what falls under their authority or direct us to the correct lab or IT administrator.

### Data storage and deletion

Before asking faculty to approve a data plan, we still need to finish a proposal covering
- Data types and sensitivity
- Storage location
- Who can access the data
- File naming
- Participant identifiers
- Retention period
- Backups
- De-identification
- Deletion

Our current plan is to keep code, schemas, configurations, tests, and synthetic data in GitHub. Any approved human data would go in restricted university storage.

### FPGA validation

We won't begin FPGA implementation or deployment during the first month.

The software work comes first
- Simulated PUF measurements
- Credential reconstruction
- Session authentication
- Window protection and verification
- Conventional model baselines
- Initial SNN results
- Attack results
- Latency results

After those results exist, we'll research candidate FPGA platforms, cost, software tools, and access requirements. Faculty can then decide whether hardware validation is worth starting.

No FPGA decision is needed now.

## Sources reviewed

- Virginia Tech HRPP responsibilities - (https://www.research.vt.edu/research-support/forms-guidance/hrpp/sop-researcher-investigator-responsibilities.html)
- Meta Quest development setup - (https://developers.meta.com/horizon/design/prototype-setup-software/)
- ILLIXR - (https://experts.illinois.edu/en/publications/illixr-an-open-testbed-to-enable-extended-reality-systems-researc)
- REALITYCHECK - (https://www.usenix.org/system/files/usenixsecurity25-shoaib.pdf)
- PXRA - (https://pmc.ncbi.nlm.nih.gov/articles/PMC12788305/)