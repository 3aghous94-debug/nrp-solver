# Algorithm Development

This document traces the algorithmic development from the initial swap-cascade idea through the DWEC algorithm. It's the research arc — including the dead ends, because they motivated the breakthroughs.

## Table of contents

1. [Starting point: the envy-cycle algorithm](#1-starting-point)
2. [Attempt 1: swap-cascade for unit weights (success)](#2-attempt-1-swap-cascade)
3. [Attempt 2: adjacent augmentation (failure)](#3-attempt-2-adjacent-augmentation)
4. [Attempt 3: global LE (success — the Main Theorem)](#4-attempt-3-global-le)
5. [Attempt 4: weighted swap-cascade (failure)](#5-attempt-4-weighted-swap-cascade)
6. [Attempt 5: sum-of-squares potential (failure)](#6-attempt-5-sos-potential)
7. [Attempt 6: modified swap rule (partial success)](#7-attempt-6-modified-swap-rule)
8. [Attempt 7: weight-exchange (vacuous)](#8-attempt-7-weight-exchange)
9. [Breakthrough: the DWEC algorithm](#9-breakthrough-dwec)
10. [Extension 1: per-agent feasibility (skill mix)](#10-extension-1-per-agent)
11. [Extension 2: coverage constraints](#11-extension-2-coverage)
12. [Extension 3: availability and pre-assignment](#12-extension-3-availability)

---

## 1. Starting point: the envy-cycle algorithm

The foundation is the envy-cycle algorithm of Lipton, Markakis, Mossel, and Saberi (2004):

```
For each good s:
  Give s to a source agent (no incoming envy).
  If an envy cycle forms, rotate it.
```

For unconstrained F = 2^S, this gives EF1 in polynomial time. The question: how to extend it to constrained F?

**Biswas and Barman (2018)** extended it to matroidal F using the matroid augmentation property: whenever a rotation would add a good to an agent's bundle, that addition is feasible.

**The problem.** NRP feasibility is not matroidal (rest constraints, consecutive-days rules violate the augmentation axiom). The rotation may land an agent in an infeasible bundle.

---

## 2. Attempt 1: swap-cascade for unit weights

### Idea

When direct addition is infeasible, use a swap: remove a good t from the agent's bundle, add the new good s. If the swap preserves feasibility, continue.

### Algorithm

```
For each good s:
  CASCADE(s):
    current_good := s
    loop:
      i := source agent
      if π_i ∪ {current_good} ∈ F:
        add it (direct addition)
        return
      else:
        by LE, ∃ t ∈ π_i with (π_i \ {t}) ∪ {current_good} ∈ F
        swap: π_i := (π_i \ {t}) ∪ {current_good}
        current_good := t
        continue
```

### Why it works (unit weights)

- **Swaps preserve loads.** |π_i| is unchanged (remove 1, add 1).
- **Direct additions go to source agents.** Source = least-loaded, so spread ≤ 1 is maintained.
- **Envy-cycle rotation** (Lipton et al.) handles cycles.

### Result

**The Main Theorem:** LE + feasibility ⟹ EF1. Complexity O(m²n). Verified on 56/56 instances.

---

## 3. Attempt 2: adjacent augmentation

### Idea

Maybe we don't need full LE. Maybe "adjacent augmentation" — swaps only for G_F-adjacent goods — suffices. This would be weaker and easier to verify.

### Conjecture

If F satisfies adjacent augmentation (for every A ∈ F and s ∉ A with {s,t} ∈ E(G_F) for some t ∈ A, there exists t' ∈ A with (A \ {t'}) ∪ {s} ∈ F), then EF1 is achievable.

### Refutation

The dominant-good family satisfies AA vacuously (the dominant good is isolated in G_F, so the antecedent is never triggered for it), yet EF1 fails.

**Lesson.** Exchange properties must be global, not adjacency-restricted. Goods isolated in G_F escape adjacency-based conditions.

See [REFUTATIONS.md](REFUTATIONS.md) §1.

---

## 4. Attempt 3: global LE

### Fix

Use global LE: for every A ∈ F and s ∉ A with A ∪ {s} ∉ F, there exists t ∈ A with (A \ {t}) ∪ {s} ∈ F. No adjacency restriction.

### Result

The Main Theorem (proven). The swap-cascade algorithm with global LE achieves EF1 in O(m²n).

**Families satisfying LE:**
- All matroids (by augmentation)
- Cardinality-constrained families (trivially)
- SwapHeavyFamily (non-matroidal, verified)

**Families failing LE:**
- Dominant-good family (correctly predicts EF1 failure)
- Bridge family (correctly predicts EF1 failure)
- Bottleneck family (correctly predicts the tightness boundary)

---

## 5. Attempt 4: weighted swap-cascade

### Goal

Extend the swap-cascade to weighted goods. The natural attempt: require weight-decreasing swaps (w(t) ≥ w(s)).

### The obstacle

A weighted swap at agent i changes load(i) by w(s) − w(t) ≤ 0. If i is the unique minimum-load agent, decreasing its load **increases the spread**.

**Example.** Loads (1, 5, 5), w_max = 5. Swap at agent 0: remove good of weight 5, add good of weight 2. Agent 0's load: 1 − 5 + 2 = −2. Wait, loads can't go negative.

Correct: agent 0 has bundle of total weight 1. To swap, we need t ∈ π_0 with w(t) ≥ w(s). If π_0 = {good of weight 1}, no t has w(t) ≥ 2. Swap fails.

If π_0 = {good of weight 3}, swap: remove weight-3 good, add weight-2 good. Agent 0's load: 1 − 3 + 2 = 0. New loads (0, 5, 5). Spread = 5 > w_max = 5? No, spread = 5 ≤ 5. OK.

But if π_0 = {good of weight 5}, swap: remove weight-5, add weight-2. Load: 1 − 5 + 2 = −2. Impossible — agent 0 didn't have a weight-5 good if load was 1.

The real problem: when the minimum-load agent has a heavy good and swaps it for a light good, its load drops, increasing spread.

### Result

**Failure.** The swap-cascade doesn't extend to weighted goods.

---

## 6. Attempt 5: sum-of-squares potential

### Idea

Maybe a different potential — Φ = Σ load(i)² — is monotone under weight-exchange swaps, allowing a termination proof.

### Analysis

A weighted swap at agent i changes load(i) by δ = w(t) − w(s) ≥ 0. The change in Φ:

```
ΔΦ = (ℓ_i − δ)² − ℓ_i² = δ² − 2δℓ_i = δ(δ − 2ℓ_i)
```

- ΔΦ < 0 (Φ decreases) iff δ < 2ℓ_i.
- ΔΦ > 0 (Φ increases) iff δ > 2ℓ_i.

**When i is the minimum-load agent and δ is large, Φ increases.** The potential is not monotone.

### Result

**Failure.** The sum-of-squares potential doesn't work.

---

## 7. Attempt 6: modified swap rule

### Idea

Only allow swaps that don't increase spread. Rule: swap at agent i only if (i is not the unique minimum) OR (w(t) = w(s)).

### Analysis

- **EF1 invariant is maintained** (proven): swaps at non-min agents don't change the min; weight-preserving swaps at the min don't change loads.
- **But the algorithm gets stuck.** When the min agent needs a non-weight-preserving swap and no other agent can accept, the cascade fails.

### Result

**Partial success.** EF1 is maintained when the algorithm runs, but it can't always find a valid swap. Tested on SwapHeavy r=3 m=10 bimodal: spread = 8 > w_max = 5, EF1 violated.

---

## 8. Attempt 7: weight-exchange

### Idea

Formalize the condition: F satisfies weight-exchange if for every A ∈ F and s ∉ A with A ∪ {s} ∉ F, there exists t ∈ A with w(t) ≥ w(s) and (A \ {t}) ∪ {s} ∈ F.

### Result

**Vacuous.** In 100 random families with random weights, 0 satisfied weight-exchange. The condition is so strong that it's essentially equivalent to r-completeness for the heaviest goods.

See [REFUTATIONS.md](REFUTATIONS.md) §2.

---

## 9. Breakthrough: the DWEC algorithm

### The key insight

**Don't swap. Eject.**

The swap-cascade fails because it swaps at the *same* agent that receives the new good. This couples the load changes. The fix: eject from a *different* agent.

### Algorithm

```
For each good s (decreasing weight):
  k := least-loaded agent
  if π_k ∪ {s} ∈ F:
    direct placement at k
  else:
    Find (j, t) with:
      j ≠ k (eject from non-least-loaded)
      t ∈ π_j
      (π_j \ {t}) ∪ {s} ∈ F
      w(t) ≥ w(s)
      π_k ∪ {t} ∈ F
      ℓ_j − ℓ_min ≥ w(t) − w(s) (min-preservation)
    Execute: s goes to j, t goes to k
```

### Why it works

The decreasing-weight ordering ensures all placed goods have weight ≥ w(current good). When ejecting t to make room for s:
- w(t) ≥ w(s), so j's load doesn't increase.
- The min-preservation constraint ensures j doesn't drop below ℓ_min.
- t goes to k (least-loaded), bounded by ℓ_min + w(t) ≤ ℓ_min + w_max.

### Result

**359/359 feasible instances achieve weighted-EF1.** The spread bound is proven (see [PROOFS.md](PROOFS.md) §3).

---

## 10. Extension 1: per-agent feasibility

### Challenge

Real NRP has per-agent F_i (skill mix). Does the spread bound survive?

### Analysis

Per-agent feasibility only constrains the *search* for valid (j, t) pairs, not the load dynamics. The spread bound holds when the least-loaded agent can accept each good.

When the least-loaded agent *can't* accept (skill mismatch), the algorithm falls back to relaxed placement. The structural lower bound on spread is:

```
spread ≥ max_skill_concentration − average_load
```

### Result

- **94% EF1** on heterogeneous cardinality caps.
- **100% EF1** on heterogeneous SwapHeavy.
- **52% EF1** on skill mix — the failures are structural (verified optimal against brute force).

---

## 11. Extension 2: coverage constraints

### Challenge

Real NRP needs *c* nurses per shift with specific skills. This couples agents.

### Approach

Treat each coverage slot as a separate good. A shift needing 2 nurses becomes 2 goods, each assigned independently. The standard DWEC applies to each slot.

### Result

- **87% EF1** on 200 random coverage instances.
- **98% EF1** on no-skill-mix coverage.
- **65% EF1** on heavy skill mix — failures are structural.

The ejection-chain framework **survives coverage constraints**.

---

## 12. Extension 3: availability and pre-assignment

### Availability

Per-nurse availability (days off, no-nights, part-time, vacation) fits naturally into `is_feasible_for` as additional constraints. The algorithm handles them via the same feasible-agent filtering used for skill mix.

### Pre-assignment

Pre-assigned shifts are placed in the nurse's bundle before the algorithm runs. Other nurses are forbidden from taking those shifts. The ejection mechanism can't move pre-assigned goods (they're locked).

**Bug found and fixed:** pre-assignment conflicts with availability were silently dropped. Now they're detected upfront with clear diagnostic reasons.

---

## Summary: the algorithmic stack

| Setting | Algorithm | Complexity | Result |
|---|---|---|---|
| Unit weights, LE | Swap-cascade | O(m²n) | EF1 (proven) |
| Weighted, r-complete | LPT | O(m log m) | Weighted-EF1 (proven) |
| Weighted, non-r-complete | DWEC | O(m³n) | Weighted-EF1 (proven) |
| Per-agent (skill mix) | Per-agent DWEC | O(m³n) | EF1 when structurally possible |
| Coverage | Coverage DWEC | O(m³n) | EF1 when structurally possible |
| General | ILP | NP-hard | Min spread (exact) |

The development arc: envy-cycle → swap-cascade (unit weights) → DWEC (weighted) → per-agent → coverage. Each step motivated by a real NRP feature, each proof verified computationally.
