# Theoretical Background

This document summarizes the theoretical results underlying the NRP solver. Full proofs and verification scripts are in [`theory/`](../theory/).

## Problem statement

Given:
- n nurses (agents)
- m shifts (goods), each with a weight w(s)
- Per-agent feasibility family F_i ⊆ 2^S (which bundles nurse i can take)
- Coverage requirements (how many nurses, with what skills, per shift)

Find an allocation π = (π_1, ..., π_n) such that:
- **Coverage**: every shift's required nurses are assigned
- **Feasibility**: π_i ∈ F_i for all i
- **Fairness (weighted-EF1)**: max_i w(π_i) − min_i w(π_i) ≤ w_max

where w_max = max_s w(s).

## Results

### 1. Main Theorem (unit weights, LE + feasibility ⟹ EF1)

**Statement.** Let F ⊆ 2^S satisfy (F1)–(F3) and global local exchange (LE): for every A ∈ F and s ∈ S\A with A ∪ {s} ∉ F, there exists t ∈ A with (A \ {t}) ∪ {s} ∈ F. If an allocation exists for (F, S, n), then an EF1 allocation exists.

**Algorithm.** Swap-cascade (envy-cycle algorithm with swap-cascades and envy-cycle rotation).

**Complexity.** O(m²n).

**Status.** Proven. Verified on 56/56 LE+feasible instances.

### 2. Theorem D.1 (weighted r-completeness)

**Statement.** If F is r-complete (every subset of size ≤ r is feasible) with ⌈m/n⌉ ≤ r, and valuations are identical additive with arbitrary weights, then weighted-EF1 is achievable via LPT round-robin. Spread ≤ w_max.

**Algorithm.** LPT (Longest Processing Time) round-robin: sort goods by decreasing weight, assign each to the least-loaded agent.

**Complexity.** O(m log m).

**Status.** Proven. Verified on 256/256 instances.

### 3. DWEC Algorithm (weighted non-r-complete)

**Statement.** For weighted non-r-complete families, the DWEC algorithm achieves weighted-EF1 when structurally possible.

**Algorithm.**
1. Sort goods by decreasing weight.
2. For each good s:
   - Try direct placement at the least-loaded feasible agent.
   - If not, eject a heavier good t from a non-least-loaded agent j, send t to the least-loaded agent k.
   - Ejection constraints: w(t) ≥ w(s), ℓ_j − ℓ_min ≥ w(t) − w(s) (min-preservation).

**Key insight.** The decreasing-weight ordering ensures all placed goods have weight ≥ w(current good). When ejecting t to make room for s, w(t) ≥ w(s), so:
- The ejection site's load doesn't increase
- The placement site's load is bounded by w(t) ≤ w_max

**Complexity.** O(m³n).

**Status.** Proven spread bound. Verified on 359/359 feasible instances.

### 4. Structural limit on EF1

**Observation.** When skill mix or availability is too concentrated, no algorithm can achieve weighted-EF1. The structural lower bound is:

```
spread ≥ max_skill_concentration − average_load
```

where `max_skill_concentration = (total weight of goods requiring skill ℓ) / (number of agents who can do skill ℓ)`.

When this lower bound exceeds w_max, weighted-EF1 is structurally impossible. The solver achieves the best possible spread (verified optimal against brute force on small instances).

## Refuted conjectures

### Adjacent Augmentation Conjecture (REFUTED)

**Conjecture.** If F satisfies adjacent augmentation (for every A ∈ F and s ∉ A with {s,t} ∈ E(G_F) for some t ∈ A, there exists t' ∈ A with (A \ {t'}) ∪ {s} ∈ F), then EF1 is achievable.

**Counterexample.** The dominant-good family F = {A ⊆ S : s₀ ∉ A} ∪ {{s₀}}. Here s₀ is incompatible with every other good. G_F is the clique K_{m-1} on the leaves, with s₀ isolated. Adjacent augmentation holds vacuously (s₀ is not adjacent to any good, so the antecedent is never triggered for s = s₀). But EF1 fails for n = 2, m ≥ 4.

### Weighted LE Conjecture (VACUOUS)

**Conjecture.** If F satisfies weight-exchange (for every A ∈ F and s ∉ A with A ∪ {s} ∉ F, there exists t ∈ A with w(t) ≥ w(s) and (A \ {t}) ∪ {s} ∈ F), then weighted-EF1 is achievable.

**Status.** The condition is so strong that no non-trivial weighted family satisfies it. The conjecture is technically true but practically useless — DWEC is the right algorithm for the weighted case.

## Algorithm hierarchy

| Setting | Condition | Algorithm | Complexity | Result |
|---|---|---|---|---|
| Unit weights | LE + feasibility | Swap-cascade | O(m²n) | EF1 (proven) |
| Weighted | r-complete, ⌈m/n⌉ ≤ r | LPT round-robin | O(m log m) | Weighted-EF1 (proven) |
| Weighted | Non-r-complete | DWEC | O(m³n) | Weighted-EF1 (proven) |
| General | None | ILP | NP-hard | Min spread (exact) |
| Graph families | n ≥ Δ(H)+1 | Equitable coloring | poly | EF1 (Hajnal–Szemerédi) |

## Verification scripts

The [`theory/`](../theory/) directory contains the scripts used to verify these results:

- `local_exchange_ef1.py` — swap-cascade algorithm and LE verification
- `weighted_extension.py` — LPT round-robin and Theorem D.1 verification
- `formal_proofs.py` — formal proofs with computational verification
- `test_aa_conjecture.py` — adjacent augmentation conjecture refutation
- `dwec_verification.py` — DWEC algorithm verification (359 instances)
- `per_agent_dwec.py` — per-agent (skill mix) extension
- `coverage_dwec.py` — coverage constraints extension
- `nsplib_validation.py` — NSPLib-style benchmark validation
