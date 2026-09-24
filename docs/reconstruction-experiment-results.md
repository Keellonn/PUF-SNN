# Week 3 Layer 2 experimental results

## Experiment Overview
Much like the layer 1 baseline I established through experiments, the layer 2 baseline was defined using a 20 seperate seed experiment. I took the 20 runs from the layer 1 baseline and ran the layer 2 simulation and recorded the important stats.

## Results
Seed-specific statistics and data is stored in,
\results\week3\will\layer2baseline.csv

Overall statistics,
- Attempt total: 12000
- Success Count: 11805
- Success Rate: 98.375%
- Failure Count: 195
- FRR: 1.625%
- Decoder Failures: 186
- Invalid Format: 7
- Max Latency: 2390163000 ns
- Mean Latency: 4865066.308 ns

## Important Takeaways
Across the 20 seeded Layer 2 runs, the reconstruction system successfully recovered the enrolled credential in 11,805 of 12,000 attempts, giving an observed reconstruction success rate of 98.375%. The observed false rejection rate (FRR) was 1.625%. This is above the current provisional 1% target, so the present BCH(63,36,t=5) construction should be treated as a working baseline rather than a final optimized reconstruction design. Most reconstruction failures were BCH decoder failures. Of the 195 total failures, 186 were decoder failures and 7 produced invalid-format or invalid-padding results. The remaining 2 failures were valid-format wrong-credential reconstructions, or miscorrections. These cases are especially important because Layer 2 can return a structurally valid credential without knowing whether it is the originally enrolled credential. The miscorrection cases justify the Layer 3 key-confirmation step. Layer 3 must independently verify possession of the expected credential-derived key rather than assuming that every valid-format Layer 2 result is correct. Reconstruction performance varied across the 20 simulated PUF populations. The pooled 98.375% success rate therefore does not imply that every simulated device or seed has the same reconstruction reliability. The results demonstrate that BCH-based reconstruction is generally successful under the nominal Layer 1 noise conditions, but the observed failure rate shows that reconstruction reliability remains an important limitation of the current pilot. The recorded mean reconstruction latency was approximately 4.87 ms across these single-run experiments. The maximum recorded latency of approximately 2.39 seconds is dominated by the first cold BCH decode/JIT initialization and should not be interpreted as normal steady-state reconstruction latency. Layer 2 establishes a candidate credential only. It does not authenticate sensor windows or provide replay, freshness, ordering, or payload-integrity protection. Those responsibilities are handled by Layer 3. These results support proceeding to Layer 3 with the current reconstruction design as the frozen pilot baseline while clearly documenting the observed 1.625% FRR and the existence of rare valid-format miscorrections.