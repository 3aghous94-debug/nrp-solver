# Theoretical Background

This document is the entry point to the theoretical work. For the full treatment, see the companion documents:

- **[RESEARCH.md](RESEARCH.md)** — The complete research narrative: from Aguentil's framework through the DWEC algorithm, including all the dead ends and breakthroughs.
- **[PROOFS.md](PROOFS.md)** — Formal proofs of the Main Theorem, Theorem D.1, the DWEC spread bound, the MMS corollary, BFP NP-hardness, and the Hajnal–Szemerédi application.
- **[REFUTATIONS.md](REFUTATIONS.md)** — The conjectures we refuted (Adjacent Augmentation, Weighted LE, Separator Imbalance) and what they taught us.
- **[ALGORITHM_DEVELOPMENT.md](ALGORITHM_DEVELOPMENT.md)** — The algorithmic development arc: envy-cycle → swap-cascade → DWEC, including the failed attempts.
- **[EXPERIMENTAL_RESULTS.md](EXPERIMENTAL_RESULTS.md)** — All benchmark and verification results.

## Quick summary

### Problem

Given n nurses, m shifts (with weights), per-agent feasibility F_i, and coverage requirements, find an allocation that:
- Satisfies coverage (right number of nurses with right skills per shift)
- Respects feasibility (π_i ∈ F_i for all i)
- Achieves weighted-EF1 (max load − min load ≤ w_max)

### Main results

| # | Theorem | Algorithm | Complexity | Status |
|---|---|---|---|---|
| 1 | LE + feasibility ⟹ EF1 (unit weights) | Swap-cascade | O(m²n) | Proven, 56/56 verified |
| 2 | r-completeness + LPT ⟹ weighted-EF1 | LPT round-robin | O(m log m) | Proven, 256/256 verified |
| 3 | DWEC ⟹ weighted-EF1 (non-r-complete) | Ejection chains | O(m³n) | Proven, 359/359 verified |
| 4 | MMS for r-complete F | LPT | O(m log m) | Proven |
| 5 | BFP is NP-hard | — | NP-hard | Proven |
| 6 | n ≥ Δ(H)+1 ⟹ EF1 (graph families) | Equitable coloring | poly | Proven, 31/31 verified |

### Refuted conjectures

| Conjecture | Status | Counterexample |
|---|---|---|
| Adjacent Augmentation ⟹ EF1 | Refuted | Dominant-good family |
| Weight-Exchange ⟹ weighted-EF1 | Vacuous | No non-trivial family satisfies WE |
| Separator Imbalance ⟹ EF1 | Refuted | Star graph |

### Honest limits

1. **EF1 is not always achievable.** Skill concentration and availability can make it structurally impossible. No algorithm can fix this.
2. **DWEC is optimal when EF1 is impossible.** Verified against brute force — the algorithm achieves the minimum achievable spread.
3. **Outcome counting is #P-hard.** Exact counting only for tiny instances (n^m ≤ 10⁷).
4. **Multi-schedule is sampling.** Not exhaustive enumeration.

### Algorithm hierarchy

```
Setting                          → Algorithm         → Result
─────────────────────────────────────────────────────────────────
Unit weights, LE                 → Swap-cascade      → EF1 (proven)
Weighted, r-complete             → LPT               → Weighted-EF1 (proven)
Weighted, non-r-complete         → DWEC              → Weighted-EF1 (proven)
Per-agent (skill mix)            → Per-agent DWEC    → EF1 when structurally possible
Coverage constraints             → Coverage DWEC     → EF1 when structurally possible
General                          → ILP               → Min spread (exact, NP-hard)
```

## Reading order

If you're new to the project:
1. Start here (this summary)
2. Read [RESEARCH.md](RESEARCH.md) for the full story
3. Read [PROOFS.md](PROOFS.md) for the formal proofs
4. Read [ALGORITHM_DEVELOPMENT.md](ALGORITHM_DEVELOPMENT.md) for how the algorithms evolved
5. Skim [EXPERIMENTAL_RESULTS.md](EXPERIMENTAL_RESULTS.md) for the evidence
6. Read [REFUTATIONS.md](REFUTATIONS.md) for what didn't work and why

If you just want to use the solver:
- Read [API.md](API.md) for the API reference
- Look at `examples/` for usage examples
- Skip the theory entirely — the solver works without understanding the proofs

## Verification scripts

The `theory/` directory contains all the scripts used to verify these results:

| Script | Verifies |
|---|---|
| `local_exchange_ef1.py` | Swap-cascade algorithm, LE verification |
| `weighted_extension.py` | LPT round-robin, Theorem D.1 |
| `weighted_verification.py` | Theorem D.1 stress test (256 instances) |
| `formal_proofs.py` | Formal proofs with computational checks |
| `test_aa_conjecture.py` | AA conjecture refutation |
| `refined_conjecture.py` | LE + feasibility ⟹ EF1, Hajnal–Szemerédi |
| `dwec_verification.py` | DWEC stress test (359 instances) |
| `per_agent_dwec.py` | Per-agent (skill mix) extension |
| `coverage_dwec.py` | Coverage constraints extension |
| `nsplib_validation.py` | NSPLib-style benchmark validation |
| `separator_analysis.py` | Separator imbalance refutation |
| `we_equivalence.py` | Weight-exchange vacuousness |

All scripts are runnable: `python theory/<script>.py`
