# Refutations

This document records the conjectures that were refuted during this research. Negative results are as valuable as positive ones — they tell us which paths are dead ends.

## Table of contents

1. [Adjacent Augmentation Conjecture (REFUTED)](#1-adjacent-augmentation-conjecture)
2. [Weighted LE Conjecture (VACUOUS)](#2-weighted-le-conjecture)
3. [Separator Imbalance Hypothesis (REFUTED)](#3-separator-imbalance-hypothesis)

---

## 1. Adjacent Augmentation Conjecture

### The conjecture

**Conjecture (original, from early in this research).** *If F satisfies adjacent augmentation — for every A ∈ F and s ∉ A with {s,t} ∈ E(G_F) for some t ∈ A, there exists t' ∈ A with (A \ {t'}) ∪ {s} ∈ F — then EF1 is achievable.*

### Motivation

The hope was that adjacent augmentation would be the right exchange property: weaker than matroid augmentation but strong enough to handle non-matroidal families like connected-subgraph families. The condition only constrains swaps involving G_F-adjacent goods, which seemed natural.

### Refutation

**Counterexample: the dominant-good family.**

F = {A ⊆ S : s₀ ∉ A} ∪ {{s₀}} (Aguentil's Construction 3.2). Here s₀ is incompatible with every other good.

- G_F is the clique K_{m-1} on the leaves, with s₀ isolated.
- **Adjacent augmentation holds vacuously.** s₀ is not adjacent to any good in G_F, so the antecedent "{s,t} ∈ E(G_F) for some t ∈ A" is never triggered for s = s₀. For leaf-to-leaf additions, direct addition always works (leaves form a clique in G_F, so all leaf subsets are feasible).
- **But EF1 fails** for n = 2, m ≥ 4: the unique feasible allocation is ({s₀}, {all leaves}) with spread m−2 ≥ 2 > 1.

### Why the conjecture fails

Adjacent augmentation only constrains swaps involving G_F-adjacent goods. **Goods that are isolated in G_F (dominant goods) escape the condition entirely.** The obstruction is precisely the isolated vertex — the one structural feature adjacent augmentation doesn't touch.

### The fix: global local exchange (LE)

The corrected condition is **global**: for every A ∈ F and s ∈ S\A with A ∪ {s} ∉ F, there exists t ∈ A with (A \ {t}) ∪ {s} ∈ F. No adjacency restriction.

The dominant-good family **fails** global LE: A = {1,2} (two leaves), s = s₀. A ∪ {s₀} = {s₀, 1, 2} ∉ F. Swap: {s₀, 1} ∉ F, {s₀, 2} ∉ F. No valid swap.

The Main Theorem (proven) uses global LE, not adjacent augmentation.

### Computational verification

```
Family                              AA?    LE?    EF1?   Conjecture?
Dominant-good m=4 (EF1 FAILS)       Yes    No     No     FAIL
Dominant-good m=6 (EF1 FAILS)       Yes    No     No     FAIL
Bridge F(2,4) (EF1 FAILS)           No     No     No     OK
IS of Path P_6 (EF1 holds)          No     No     Yes    OK
IS of Star K_{1,5} (EF1 fails)      Yes    No     No     FAIL
IS of Complete K_4 n=3 (infeasible) Yes    Yes    No     OK
```

The conjecture fails on dominant-good and star graphs (AA holds, EF1 fails).

Verification script: `theory/test_aa_conjecture.py`

---

## 2. Weighted LE Conjecture

### The conjecture

**Conjecture (Theorem D.2, original).** *If F satisfies weight-exchange — for every A ∈ F and s ∉ A with A ∪ {s} ∉ F, there exists t ∈ A with w(t) ≥ w(s) AND (A \ {t}) ∪ {s} ∈ F — then weighted-EF1 is achievable.*

### Motivation

The Main Theorem (unit weights) works because swaps preserve loads exactly. The natural attempt for weighted goods: require weight-decreasing swaps (w(t) ≥ w(s)) so the swap doesn't increase the swapping agent's load.

### The obstacle

**Weight-exchange swaps can still increase spread.** A swap at agent i changes load(i) by δ = w(t) − w(s) ≥ 0. If i is the unique minimum-load agent, decreasing its load *increases* the spread.

Concrete example: min_load = 1, w(t) = 5, w(s) = 2. δ = 3. Agent i's load goes from 1 to 1 − 3 = −2... wait, that's negative. Let me redo: the swap adds s (weight 2) and removes t (weight 5). Agent i's load changes by +2 − 5 = −3. Load goes from 1 to −2? No — loads can't be negative.

The correct analysis: the swap is at agent i, who has load ℓ_i. After swap: ℓ_i' = ℓ_i − w(t) + w(s) = ℓ_i − δ. If i was the minimum, the new minimum is ℓ_i − δ < ℓ_i. The spread increases by δ.

### Weight-exchange is too strong

In 100 random families with random weights, **0 satisfied weight-exchange**. The condition requires that for every infeasible addition, you can swap out a heavier-or-equal good. When the incoming good is the globally heaviest, no such swap exists — unless the family is structured so the heaviest good can always be directly added (which is essentially r-completeness for the heaviest goods).

**Tested families where weight-exchange fails:**
- Uniform matroids with skewed weights (can't swap a heavier good out when incoming is heaviest)
- SwapHeavy families with bimodal weights (bundle of light goods can't accept heavy good via weight-decreasing swap)
- Almost all non-trivial weighted families

**Tested families where weight-exchange holds:**
- Graphic matroids (verified)
- Unit weights (reduces to global LE)

### Status: vacuously true

The theorem "WE + feasible ⟹ weighted-EF1" is **technically true but practically useless**. The condition is so strong that no non-trivial weighted family satisfies it. The theorem reduces to Theorem D.1 (r-completeness) in practice.

### The fix: DWEC

The right algorithm for weighted non-r-complete families is **DWEC** (Decreasing-Weight Ejection Chain), which uses directed ejections (not swaps) and the min-preservation constraint. See [PROOFS.md](PROOFS.md) §3.

Verification script: `theory/we_equivalence.py`

---

## 3. Separator Imbalance Hypothesis

### The hypothesis

**Hypothesis (early in this research).** *If the imbalance of every minimum separator of G_F is bounded by a constant C, then EF1 is achievable for sufficiently many agents.*

where imbalance = (size of largest component after separation) / (size of smallest non-trivial component).

### Motivation

The bridge family F(ω, M) has a minimum separator of size ω that splits G_F into components of sizes 1 and M−1 — extremely unbalanced. The hope was that balanced separators would prevent this obstruction.

### Refutation

**Counterexample: the star graph K_{1,m−1}.**

- G_F = star with center c and m−1 leaves.
- Minimum separator: {c} (size 1).
- After removing c: m−1 isolated vertices, all of size 1. **Perfectly balanced** (imbalance = 1).
- But EF1 **fails** for n < m/2: the center is a dominant good, forcing the unique allocation ({c}, {all leaves}) with spread m−2.

The star has the most balanced separators possible, yet fails EF1. Separator imbalance does not predict EF1 achievability.

### The correct predictor: maximum degree

For independent-set families (F = ind(H)), the right predictor is **maximum degree** Δ(H):
- By Hajnal–Szemerédi, n ≥ Δ(H) + 1 ⟹ EF1.
- The star K_{1,m−1} has Δ = m−1, so needs n ≥ m for EF1. This matches: EF1 holds iff n ≥ (m+1)/2 for the star.

### Computational verification

```
Graph              |V|   κ   imbalance   spread(n=3)   EF1?
Complete K_6         6    5   1.0         ?             ?     (n < Δ+1=6, infeasible)
Path P_10           10    1   8.0         1             Yes   (Δ=2, n=3 ≥ 3)
Cycle C_10          10    2   7.0         1             Yes   (Δ=2, n=3 ≥ 3)
Star K_{1,8}         9    1   1.0         3             No    (Δ=8, n=3 < 9)
Bipartite K_{3,3}    6    3   1.0         2             No    (Δ=3, n=3 < 4)
Grid 3x3             9    2   6.0         0             Yes   (Δ=4, n=3 < 5, but EF1 anyway)
```

The star has the lowest imbalance (1.0) yet fails EF1. The path has high imbalance (8.0) yet achieves EF1. Separator imbalance is not the predictor; maximum degree is.

Verification script: `theory/separator_analysis.py`

---

## Summary

| Conjecture | Status | Counterexample |
|---|---|---|
| Adjacent Augmentation ⟹ EF1 | **Refuted** | Dominant-good family (AA holds vacuously, EF1 fails) |
| Weight-Exchange ⟹ weighted-EF1 | **Vacuous** | No non-trivial weighted family satisfies WE |
| Separator Imbalance ⟹ EF1 | **Refuted** | Star graph (perfectly balanced separators, EF1 fails) |

### What the refutations taught us

1. **Exchange properties must be global, not adjacency-restricted.** The dominant-good obstruction exploits the gap in adjacent augmentation. Global LE handles it.

2. **Weighted swaps don't extend to weighted goods.** The swap abstraction breaks down when swaps change loads. Ejection (directed transfer) is the right mechanism.

3. **Graph invariants of G_F don't predict EF1.** G_F doesn't determine F — two families with the same G_F can have opposite EF1 properties. The right predictor depends on F's structure, not G_F's connectivity.

These negative results directly motivated the positive results (Main Theorem via global LE, DWEC via ejection chains).
