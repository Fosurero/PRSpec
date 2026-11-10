# Meta Wonder M5: one-file comparison

Two live calls on `muse-wonder-1.0`, no verifier: one on pinned Besu `8f01c7a3200780b00163ab76d544e0ef6646da41` `BlobFeeMarket.java`, and one on the same file with the pre-registered M5 mutation. Both use the full EIP-4844 text at `ethereum/EIPs@542e62eb129517130b7facc52bbb9a1f333c711e` as supplied context. This was a focused one-file experiment, not the original full scoreboard protocol. The earlier Spark full scoreboard used a different spec-fetching path, so these results are not an apples-to-apples model comparison.

- Clean file: 8 raw findings, no verifier; they require human triage.
- Mutated file: 1 raw finding, correctly describes changing the initialization of `i` from 1 to 2.
- The existing pre-registered keyword scorer marks it **inconclusive** because a clean-file finding also mentions `fakeExponential`; a human reading identifies that clean-file finding as a separate denominator-validation claim, not the index mutation. This observation does not change the original classifier's result.
- Usage metadata: clean 7,015 input / 4,988 output tokens; mutation 7,015 input / 4,471 output tokens. Verification calls: none. A separate minimal connectivity probe used 14 input / 43 output tokens. These are API response token counts, not a billing statement; actual charges and which account dashboard they appear on have not been verified.
- The mutation is deliberately injected in memory, not a Besu defect. No behavioral client test, EELS comparison, or independent verification was run here.

[Clean output](original.json) · [Mutated output](mutated.json) · [Machine-readable summary](summary.json)
