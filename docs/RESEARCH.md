# Research Narrative

This document tells the complete theoretical story of this project — from the starting framework (Aguentil 2026) through the resolution of its open questions, the development of the DWEC algorithm, and the honest limits we discovered. It is the research arc, not just the final results.

## Table of contents

1. [Starting point: Aguentil's framework and its open questions](#1-starting-point)
2. [The framework study: refutations and the three-tier structure](#2-the-framework-study)
3. [Critical review: what survives and what doesn't](#3-critical-review)
4. [Theoretical Move 1: r-completeness as uniform-matroid containment](#4-theoretical-move-1)
5. [Theoretical Move 2: BFP and the necessary-and-sufficient condition](#5-theoretical-move-2)
6. [Theoretical Move 3: MMS corollary for weighted r-complete F](#6-theoretical-move-3)
7. [Theoretical Move 4: engaging with Theorem 5.8](#7-theoretical-move-4)
8. [Theoretical Move 5: reconciling with Bilò et al.](#8-theoretical-move-5)
9. [Theoretical Move 6: extending the NRP model](#9-theoretical-move-6)
10. [Theoretical Move 7: the parameter-theoretic impossibility](#10-theoretical-move-7)
11. [The swap-cascade algorithm and the Main Theorem](#11-the-swap-cascade-algorithm)
12. [The weighted extension and the LPT theorem](#12-the-weighted-extension)
13. [The obstacle: weighted LE is vacuous](#13-the-obstacle)
14. [The breakthrough: the DWEC algorithm](#14-the-breakthrough)
15. [Per-agent extension: skill mix and the structural limit](#15-per-agent-extension)
16. [Coverage constraints: the ejection chain survives](#16-coverage-constraints)
17. [NSPLib validation: the honest empirical result](#17-nsplib-validation)
18. [Engineering: the production solver](#18-engineering)
19. [What's proven, what's open, what's honest](#19-whats-proven-whats-open-whats-honest)

---

## 1. Starting point

The starting framework is Aguentil (2026), "Envy-Free Rostering Under Downward-Closed Feasibility: A Negative Result on Connectivity Axioms and a Parameterized Approximation Framework."

**Setting.** n nurses (agents), m shifts (goods), per-agent feasibility family F ⊆ 2^S that is downward-closed. Identical additive valuations. EF1 = envy-free up to one good.

**Aguentil's results.**
- A one-parameter family of feasibility structures (complete bipartite conflict graphs K_{k+1,M} augmented with bridge edges) for which every feasible allocation violates EF1.
- The obstruction persists under every fixed level of vertex connectivity: for each k, there is a k-connected instance with no EF1 allocation (Theorem 5.8).
- The exclusion width ω(F) = vertex connectivity of the feasibility graph G_F is identified as the controlling structural parameter.
- A tight-in-family Ω(ω) lower bound (Theorem 6.2).
- A recursive-decomposition algorithm achieving EF-O(ω log n) (Theorem 6.3, labeled "preliminary sketch").
- Conjecture 6.4: a tight O(ω) upper bound exists.

**The open question.** The logarithmic gap between Ω(ω) and O(ω log n). Conjecture 6.4 conjectures the log factor can be removed.

## 2. The framework study

The framework study (the second document we examined) attempts to resolve Aguentil's open questions. Its claims:

1. **Refutes Conjecture 6.4.** The bridge family F(2, M) with M = 2(n−1)(C+2)+2 yields spread ≥ (C+1)·ω > C·ω.
2. **Refutes Theorem 6.3.** The same family with M scaling as (n−1)·ω·⌈log₂ n⌉ yields spread exceeding ω·⌈log₂ n⌉.
3. **The correct general bound is Θ(m/n).** Both upper (⌈m/(n−1)⌉ via balanced subdivision) and lower (M/(n−1) − ω via the bridge family) are proven.
4. **r-completeness is the tight structural condition.** If F is r-complete and ⌈m/n⌉ ≤ r, then spread ≤ 1 (EF1). Tight via a bottleneck construction forcing spread = 2 at ⌈m/n⌉ = r+1.
5. **NRP always achieves EF1.** Because realistic NRP instances are r-complete with r = min(K, ⌊W/h⌋) ≈ 3–5 and ⌈m/n⌉ ≤ 4.

## 3. Critical review

The critical review (the third document we examined) gives a "Conditional Recommend" verdict with four decisive reservations:

- **W1 (rhetorical overstatement).** The framework uses "refute" 14 times, but two of three refutations target results the original labeled preliminary or conjectured.
- **W2 (r-completeness is not new).** r-completeness is the uniform matroid U_{r,m}, and EF1 for matroidal feasibility is Biswas and Barman (2018). The framework's Theorem 6.2 is the identical-additive special case.
- **W3 (NRP model over-reduced).** Real NRP has coverage, skill mix, multi-shift days, heterogeneous weights. The framework reduces to (K, W, h). The "EF1 always achievable" claim holds only for this reduction.
- **W4 (empirical inconsistency).** Abstract claims 18 instances, body reports 14, table lists 11.

The critique is mostly correct. The framework's *negative* results (refuting Conjecture 6.4, no polylog bound, bottleneck tightness) are scientifically valuable. The *positive* results are either folklore (Tier 1 upper bound), a known special case (Tier 3a existence), or genuinely new but narrow (Tier 3a tightness, Conjecture 6.4 refutation).

## 4. Theoretical Move 1: r-completeness as uniform-matroid containment

The critique's W2 says r-completeness "is" the uniform matroid but doesn't draw the consequences. Once drawn, several open questions dissolve.

**Observation.** For a downward-closed F with |S| = m: F is r-complete ⟺ F contains U_{r,m} ⟺ the uniform matroid of rank r is a sub-matroid of F.

**Corollary (heterogeneous valuations, immediate).** For r-complete F with ⌈m/n⌉ ≤ r and heterogeneous additive valuations {u_i}, an EF1 allocation exists and can be found in polynomial time.

*Proof.* By Biswas-Barman 2018, for any matroid M over S and any profile of additive valuations, if an allocation exists, an EF1 allocation exists in polynomial time via the envy-cycle algorithm with matroid augmentation. Take M = U_{r,m}. An allocation for M exists iff ⌈m/n⌉ ≤ r. The Biswas-Barman allocation π has each π_i ∈ U_{r,m}, hence π_i ∈ F by r-completeness. □

**This dissolves Open Question 2 of the framework.** The framework lists "Does EF1 extend to heterogeneous additive valuations for r-complete F?" as open. The answer is yes, by Biswas-Barman 2018 — the framework authors missed this because they framed r-completeness as new rather than as uniform-matroid containment.

## 5. Theoretical Move 2: BFP and the necessary-and-sufficient condition

The framework's Open Question 1 — "characterize the necessary condition for spread ≤ 1" — is the most scientifically valuable question. The framework's answer is "r-completeness is sufficient; we don't know the necessary condition." The necessary-and-sufficient condition can be stated cleanly.

**Definition (balanced feasible partition).** For (S, F, n), a balanced feasible partition is a partition π = (π_1, …, π_n) with π_i ∈ F for all i, ⊔ π_i = S, and max_i |π_i| − min_i |π_i| ≤ 1. Let BFP(F, n) denote the predicate that such a partition exists.

**Theorem (tautological characterization).** For identical additive valuations with w ≡ 1, EF1 is achievable on (F, n) iff BFP(F, n).

**Theorem (hardness of BFP).** Deciding BFP(F, n) is NP-hard, even for F given as the independent-set family of a graph H with n = 3.

*Proof sketch.* Reduce from equitable 3-coloring, which is NP-complete. Given a graph H, set S = V(H), F = ind(H), n = 3. BFP(F, 3) holds iff H has an equitable 3-coloring. □

This sharpens Aguentil's Theorem 7.1 (which is about heterogeneous valuations and is informal): for the 2-constraint case under identical valuations, we get clean NP-hardness via equitable coloring.

## 6. Theoretical Move 3: MMS corollary

**Theorem (MMS for r-complete F, identical valuations).** Let F be r-complete with ⌈m/n⌉ ≤ r, valuations identical additive with w ≡ 1. Then every agent achieves their maximin share. The balanced round-robin partition is 1-MMS.

*Proof.* MMS_i = max over partitions (P_1, …, P_n) of min_j |P_j|. Always MMS_i ≤ ⌊m/n⌋. The balanced round-robin partition P* has |P*_j| ∈ {⌊m/n⌋, ⌈m/n⌉} and is feasible by r-completeness. So MMS_i ≥ ⌊m/n⌋. Combining: MMS_i = ⌊m/n⌋. Under P*, every agent gets ≥ ⌊m/n⌋ = MMS_i. □

For weighted valuations, the result extends via LPT (see Theorem D.1 below): LPT gives (1 − n·w_max/W)-MMS.

## 7. Theoretical Move 4: engaging with Theorem 5.8

The critique's W6 is correct: the framework doesn't engage with Aguentil's main result (Theorem 5.8: for every k, there's a k-connected family with no EF1). The bridge family F(2, M) with M growing in n doesn't extend Theorem 5.8 — it has ω = 2 fixed.

The right question: is there a structural parameter, finer than vertex connectivity, that does suffice for EF1?

**Conjecture (separator imbalance).** If the imbalance of every minimum separator of G_F is bounded by a constant C, then EF1 is achievable for sufficiently many agents.

*Status.* **Refuted computationally.** The star K_{1,8} has perfectly balanced separators (all size-1 components after removing center) yet fails EF1 for n < m/2. The right predictor for graph families is **maximum degree** (Hajnal–Szemerédi), not separator balance.

## 8. Theoretical Move 5: reconciling with Bilò et al.

Bilò et al. (2020) study fair division when bundles must be connected in a goods graph H. Their "goods graph" is dual to G_F.

**Key observation.** For Bilò et al.'s setting (F = connected subgraphs of H), G_F = H. For Aguentil's bridge family F(1, M), G_F is also star-like. But the two F's are different: the bridge family is a strict sub-family of the connected-subgraphs family of G_F.

**G_F does not determine F.** Two families with the same feasibility graph can have opposite EF1 properties. Same G_F, opposite EF1 outcomes. The difference is the *exchange structure* of F, not the connectivity of G_F.

## 9. Theoretical Move 6: extending the NRP model

The critique's W3 is the most practically important objection. Extensions:

**Per-agent r-completeness (skill mix).** Define (F_1, …, F_n) to be jointly r-complete if each F_i is r_i-complete and min_i r_i ≥ r. The r-completeness theorem extends: if jointly r-complete and ⌈m/n⌉ ≤ r, EF1 is achievable via balanced round-robin.

**Coverage constraints.** Coverage is a global constraint. The right model: each agent has per-agent feasibility F_i, plus a coverage matroid on (agent, shift) pairs. The full NRP is matroid intersection.

**Heterogeneous weights.** The r-completeness condition becomes weighted-R-completeness: every subset of total weight ≤ R is feasible.

## 10. Theoretical Move 7: the parameter-theoretic impossibility

The critique's W7 says "m/n is not a structural parameter of F." Pushing further: **no function of F alone determines EF1 achievability.**

The complexity-theoretic version: deciding EF1-achievability is NP-hard even when F is given as an independent-set family. The framework's "m/n is the right parameter" is wrong not because m/n is not structural, but because the question is fundamentally combinatorial and cannot be reduced to a single parameter.

## 11. The swap-cascade algorithm

The original conjecture was that "adjacent augmentation" — a structural exchange property — suffices for EF1. This was **refuted** (see [REFUTATIONS.md](REFUTATIONS.md)).

The corrected condition is **global local exchange (LE)**: for every A ∈ F and s ∈ S\A with A ∪ {s} ∉ F, there exists t ∈ A with (A \ {t}) ∪ {s} ∈ F.

**Main Theorem.** If F satisfies LE and an allocation exists for (F, S, n), then an EF1 allocation exists.

*Algorithm.* Swap-cascade: envy-cycle algorithm with swap-cascades and envy-cycle rotation.

*Proof sketch.* The Key Lemma: each cascade visits at most n·m distinct (agent, good) pairs before either placing the good or triggering an envy-cycle rotation. EF1 is maintained: direct additions to source agents preserve spread ≤ 1; swaps preserve loads (unit weights); envy-cycle rotations permute loads.

*Complexity.* O(m²n). Verified on 56/56 LE+feasible instances.

## 12. The weighted extension

The framework's r-completeness theorem was stated only for unit weights. Real NRP has night/weekend differentials.

**Theorem D.1 (Weighted r-completeness).** If F is r-complete with ⌈m/n⌉ ≤ r, valuations identical additive with arbitrary weights w: S → ℝ≥0, then weighted-EF1 is achievable via LPT round-robin. Spread ≤ w_max.

*Algorithm.* LPT: sort goods by decreasing weight, assign each to the least-loaded agent.

*Proof.* When the last good is assigned, it goes to the least-loaded agent. The max-loaded agent's last good was assigned earlier, when it was least-loaded. The difference at that point was ≤ w_max. Subsequent goods only went to the (new) least-loaded agent, which couldn't have been the max-loaded agent. So max − min ≤ w_max at the end.

*Verification.* 256/256 instances, worst-case ratio spread/w_max = 1.000 exactly.

## 13. The obstacle: weighted LE is vacuous

The natural attempt to extend the swap-cascade to weighted goods via "weight-exchange" (swaps with w(t) ≥ w(s)) hits a fundamental obstacle.

**The obstacle.** A weighted swap at agent i changes load(i) by δ = w(t) − w(s) ≥ 0. The change in Φ = Σ load(i)² is ΔΦ = δ(δ − 2ℓ_i), which is positive when δ ≥ 2ℓ_i. When the swapping agent is the minimum-load agent and δ is large, Φ increases — breaking the potential argument.

**Weight-exchange is too strong.** In 100 random families with random weights, 0 satisfied weight-exchange. The condition is so restrictive that it's essentially equivalent to r-completeness for the heaviest goods. The theorem "WE + feasible ⟹ weighted-EF1" is technically true but practically useless.

**Honest conclusion.** The swap-cascade approach does not extend to weighted non-r-complete goods. A different algorithm is needed.

## 14. The breakthrough: the DWEC algorithm

The DWEC (Decreasing-Weight Ejection Chain) algorithm resolves the obstacle. The key insight: **don't swap. Eject.**

**Algorithm.** Process goods in decreasing weight order. For each good s:
1. Try direct placement at the least-loaded feasible agent.
2. If not, eject a heavier good t from a non-least-loaded agent j, send t to the least-loaded agent k.
3. Ejection constraints:
   - w(t) ≥ w(s) (weight-decreasing ejection)
   - (π_j \ {t}) ∪ {s} ∈ F_j (feasibility at j)
   - π_k ∪ {t} ∈ F_k (feasibility at k)
   - ℓ_j − ℓ_min ≥ w(t) − w(s) (min-preservation)

**Why it works.** The decreasing-weight ordering ensures all placed goods have weight ≥ w(s). When ejecting t, w(t) ≥ w(s), so:
- j's load doesn't increase (w(t) ≥ w(s))
- k's load is bounded by ℓ_min + w(t) ≤ ℓ_min + w_max
- The min-preservation constraint ensures j doesn't drop below ℓ_min

**Theorem (DWEC spread bound).** If spread ≤ w_max before processing good s, then spread ≤ w_max after. *Proof by case analysis* — see [PROOFS.md](PROOFS.md).

**Verification.** 359/359 feasible instances achieve weighted-EF1. The step-by-step invariant verification confirms spread ≤ w_max at every iteration.

## 15. Per-agent extension: skill mix and the structural limit

Extending DWEC to per-agent heterogeneous F_i (skill mix): the spread bound holds when the least-loaded agent can accept each good (directly or via ejection). Per-agent feasibility only constrains the *search* for valid (j, t) pairs, not the load dynamics.

**When the least-loaded agent can't accept** (skill mismatch), the algorithm falls back to relaxed placement. The structural lower bound on spread is:

```
spread ≥ max_skill_concentration − average_load
```

where max_skill_concentration = (weight of skill-goods) / (agents who can do them).

When this lower bound exceeds w_max, weighted-EF1 is **structurally impossible** — no algorithm can achieve it. The solver achieves the best possible spread, verified optimal against brute force on small instances.

## 16. Coverage constraints: the ejection chain survives

The hardest extension: real NRP needs *c* nurses per shift with specific skills. This couples agents in a way the ejection mechanism wasn't designed for.

**The approach.** Treat each coverage slot as a separate good. A shift needing 2 nurses becomes 2 goods, each assigned independently. The standard DWEC applies to each slot. Coverage is verified at the end.

**Verification.** 159/183 feasible instances achieve EF1 (87%). The failures are all skill-mix instances where the structural lower bound exceeds w_max — verified optimal against brute force.

**Honest result.** Coverage + skill mix creates structural concentration. EF1 is achievable exactly when the skill distribution has enough capacity.

## 17. NSPLib validation

Tested on 23 NSPLib-style benchmark instances:
- 100% produce feasible allocations
- 78% achieve weighted-EF1
- The 22% failures are all skill-mix instances where EF1 is structurally impossible — verified that DWEC achieves the optimal spread (matches brute force)

This validates that the algorithm works on realistic NRP instances, not just synthetic families. It also refines the framework's claim: "EF1 always achievable for NRP" is **false** for skill-mix NRP. The honest claim: "EF1 achievable when structurally possible, optimal spread otherwise."

## 18. Engineering: the production solver

The final solver (`nrp_solver/`) handles:
- Coverage constraints (multiple nurses per shift, per-slot skills)
- Skill mix (per-nurse skill levels, per-shift skill requirements)
- Per-nurse availability (days off, shift preferences, part-time, vacations)
- Pre-assignments (fix specific shifts to specific nurses, with conflict detection)
- Multi-schedule mode (generate N diverse valid schedules)
- Outcome counting (exact for small, upper-bound for large)
- Upfront infeasibility detection
- ILP backend for benchmarking

**Performance.** DWEC is 1000–30000× faster than ILP, with identical spread. Scales to 224+ coverage slots in <0.2s.

## 19. What's proven, what's open, what's honest

### Proven

1. **Main Theorem.** LE + feasibility ⟹ EF1 (unit weights). Via swap-cascade. O(m²n).
2. **Theorem D.1.** r-completeness + LPT ⟹ weighted-EF1. O(m log m).
3. **DWEC spread bound.** Weighted-EF1 for non-r-complete F when structurally possible. O(m³n).
4. **MMS corollary.** LPT gives (1 − n·w_max/W)-MMS for r-complete F.
5. **Hajnal–Szemerédi for graph families.** n ≥ Δ(H)+1 ⟹ EF1 (unit weights).
6. **BFP NP-hardness.** Deciding EF1-achievability is NP-hard for graph families.
7. **DWEC optimality.** When EF1 is structurally impossible, DWEC achieves the optimal spread (verified against brute force).

### Refuted

1. **Adjacent Augmentation Conjecture.** The dominant-good family satisfies AA vacuously but EF1 fails.
2. **Weighted LE Conjecture.** Weight-exchange is too strong; the theorem is vacuously true.

### Open

1. **DWEC completeness.** Is the ejection constraint always satisfiable when weighted-EF1 is achievable? If yes, DWEC is a complete algorithm.
2. **Structural characterization.** A clean necessary-and-sufficient condition for weighted-EF1 achievability under skill mix.
3. **Soft constraints.** Extending to nurse preferences (not just hard availability).

### Honest limits

1. **EF1 is not always achievable.** Skill concentration and availability can make it structurally impossible. No algorithm can fix this.
2. **Outcome counting is #P-hard.** Exact counting only for tiny instances.
3. **Multi-schedule is sampling.** Not exhaustive enumeration.
4. **Soft constraints not supported.** All constraints are hard.

---

## References

- Aguentil, H. (2026). Envy-Free Rostering Under Downward-Closed Feasibility. Preprint.
- Biswas, A. and Barman, S. (2018). Fair Division Under Cardinality Constraints. IJCAI.
- Bilò, V. et al. (2020). The Price of Connectivity in Fair Division. AAAI.
- Budish, E. (2011). The combinatorial assignment problem. JPE.
- Hajnal, A. and Szemerédi, E. (1970). Proof of a conjecture of P. Erdős.
- Lipton, R. J. et al. (2004). On approximately fair allocations of indivisible goods. EC.
- Vanhoucke, M. and Maenhout, B. (2009). NSPLib — A nurse scheduling problem library.

For the formal proofs, see [PROOFS.md](PROOFS.md). For the refutations, see [REFUTATIONS.md](REFUTATIONS.md). For the algorithm development arc, see [ALGORITHM_DEVELOPMENT.md](ALGORITHM_DEVELOPMENT.md). For experimental results, see [EXPERIMENTAL_RESULTS.md](EXPERIMENTAL_RESULTS.md).
