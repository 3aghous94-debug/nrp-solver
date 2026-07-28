"""
Per-Agent DWEC: Extending to Heterogeneous Feasibility (Skill Mix)

SETTING:
  Each agent i has their own feasibility family F_i ⊆ 2^S.
  An allocation π = (π_1, ..., π_n) is feasible iff π_i ∈ F_i for all i.
  This models skill mix: senior nurses can do tasks juniors can't.

WHAT CHANGES IN DWEC:
  1. Feasibility check becomes per-agent: F_i.is_feasible(π_i ∪ {s})
  2. Ejection constraints change:
     - (iii) (π_j \ {t}) ∪ {s} ∈ F_j  (was: ∈ F, now: ∈ F_j)
     - (v)  π_k ∪ {t} ∈ F_k            (was: ∈ F, now: ∈ F_k)
     - The ejection might be valid for one (j, k) pair but not another,
       because F_j and F_k differ.

KEY QUESTION: Does the spread bound still hold?

  Direct placement at least-loaded k:
    Constraint: π_k ∪ {s} ∈ F_k (per-agent)
    Spread analysis: SAME as before. w(s) <= w_max. ✓

  Ejection (s replaces t at j, t goes to k):
    Constraints:
      (π_j \ {t}) ∪ {s} ∈ F_j
      π_k ∪ {t} ∈ F_k
    Spread analysis: SAME as before.
      - j's load changes by w(s) - w(t) <= 0 (weight-decreasing)
      - k's load changes by +w(t)
      - min-preservation: ℓ_j - ℓ_min >= w(t) - w(s) ensures j doesn't drop below min
      - max bound: w(t) <= w_max (t was already placed)
    The per-agent feasibility doesn't affect the LOAD analysis, only
    the SEARCH for valid (j, t) pairs.

  CONCLUSION: The spread bound holds for per-agent DWEC. The proof
  is identical — per-agent feasibility only constrains WHICH (j, t)
  pairs are valid, not the load dynamics.

SUBTLETY: The "least-loaded feasible agent" might not be the global
  least-loaded. If the global least-loaded agent k can't accept s
  (because s ∉ F_k's allowed sets, e.g., s requires a skill k lacks),
  we need to either:
    (a) Eject from another agent and send the ejected good to k.
        But k might not be able to accept the ejected good either!
    (b) Place at the least-loaded agent who CAN accept s.
        But this might not be the global least-loaded, breaking the proof.

  This is the KEY NEW CHALLENGE. Let me think about it.

  RESOLUTION: The ejection must respect per-agent feasibility.
  When we eject t from j and send it to k:
    - k must be able to accept t (π_k ∪ {t} ∈ F_k)
    - If k can't accept t, we need a different target for t.
    - This might require a CHAIN of ejections (not just one).

  For now, let me implement the simple version (single ejection, t goes
  to global least-loaded k) and see how often it fails.
"""

import random
from itertools import combinations, product
from collections import defaultdict
from local_exchange_ef1 import FeasibilityFamily
from weighted_extension import brute_force_min_weighted_spread


# ============================================================
# Per-Agent Family Definitions
# ============================================================

class SkillMixFamily:
    """Per-agent feasibility with skill mix.
    Each agent has a skill level, and goods require certain skills.
    Agent i can take good s iff skill(i) >= required_skill(s)
    AND the bundle satisfies cardinality/consecutive constraints.
    """
    def __init__(self, S, agent_skills, good_skills, r, K=None):
        """
        S: list of goods
        agent_skills: list of skill levels, one per agent
        good_skills: dict mapping good -> required skill level
        r: max bundle size
        K: max consecutive days (optional, for NRP-like)
        """
        self.S = list(S)
        self.m = len(S)
        self.n = len(agent_skills)
        self.agent_skills = list(agent_skills)
        self.good_skills = dict(good_skills)
        self.r = r
        self.K = K

    def is_feasible_for(self, agent_idx, A):
        """Check if bundle A is feasible for agent agent_idx."""
        A = set(A)
        # Cardinality
        if len(A) > self.r:
            return False
        # Skill check
        for s in A:
            if self.agent_skills[agent_idx] < self.good_skills[s]:
                return False
        # Consecutive days (if applicable)
        if self.K is not None:
            days = sorted(set(s[0] if isinstance(s, tuple) else s for s in A))
            run = 1
            for i in range(1, len(days)):
                if days[i] == days[i-1] + 1:
                    run += 1
                    if run > self.K:
                        return False
                else:
                    run = 1
        return True


class HeterogeneousSwapHeavy:
    """Per-agent SwapHeavy: each agent i has F_i = {|A|<=r_i} ∪ {|A|=r_i+1, 0∈A}.
    Different agents have different r_i (skill caps)."""
    def __init__(self, S, agent_caps):
        """
        S: list of goods
        agent_caps: list of cardinality caps, one per agent
        """
        self.S = list(S)
        self.m = len(S)
        self.n = len(agent_caps)
        self.agent_caps = list(agent_caps)

    def is_feasible_for(self, agent_idx, A):
        A = set(A)
        r = self.agent_caps[agent_idx]
        if len(A) <= r:
            return True
        if len(A) == r + 1 and 0 in A:
            return True
        return False


class UniformHeterogeneous:
    """Per-agent uniform matroid: F_i = {|A| <= r_i}."""
    def __init__(self, S, agent_caps):
        self.S = list(S)
        self.m = len(S)
        self.n = len(agent_caps)
        self.agent_caps = list(agent_caps)

    def is_feasible_for(self, agent_idx, A):
        return len(set(A)) <= self.agent_caps[agent_idx]


# ============================================================
# Per-Agent DWEC Algorithm
# ============================================================

def per_agent_dwec(family, S, n, weights, verbose=False):
    """
    Per-Agent DWEC algorithm.
    family: object with is_feasible_for(agent_idx, A) method.
    """
    S = list(S)
    m = len(S)
    w_max = max(weights.values()) if weights else 0
    sorted_goods = sorted(S, key=lambda s: -weights[s])

    pi = [set() for _ in range(n)]
    loads = [0.0] * n
    leftover = []
    stats = {"direct": 0, "ejections": 0, "deferred": 0, "iterations": 0}

    for s in sorted_goods:
        stats["iterations"] += 1
        min_load = min(loads)
        k = min(range(n), key=lambda i: loads[i])

        # Direct placement at least-loaded k (per-agent feasibility)
        if family.is_feasible_for(k, pi[k] | {s}):
            pi[k] = pi[k] | {s}
            loads[k] += weights[s]
            stats["direct"] += 1
            if verbose:
                print(f"  Direct: {s} (w={weights[s]}) -> agent {k} (load {loads[k]:.2f})")
            continue

        # Ejection: find (j, t) with per-agent constraints
        # (i)   j != k
        # (ii)  t ∈ π_j
        # (iii) (π_j \ {t}) ∪ {s} ∈ F_j  (per-agent)
        # (iv)  w(t) >= w(s)
        # (v)   π_k ∪ {t} ∈ F_k  (per-agent)
        # (vi)  ℓ_j - ℓ_min >= w(t) - w(s)
        ejection_found = False
        agents_by_load = sorted(range(n), key=lambda i: -loads[i])

        for j in agents_by_load:
            if abs(loads[j] - min_load) < 1e-9:
                continue  # skip least-loaded (and tied)

            ejectable = []
            for t in pi[j]:
                if weights[t] >= weights[s] - 1e-9:
                    new_j = (pi[j] - {t}) | {s}
                    if family.is_feasible_for(j, new_j):
                        if family.is_feasible_for(k, pi[k] | {t}):
                            if loads[j] - min_load >= weights[t] - weights[s] - 1e-9:
                                ejectable.append(t)

            if ejectable:
                t = min(ejectable, key=lambda x: weights[x])
                pi[j] = (pi[j] - {t}) | {s}
                loads[j] += weights[s] - weights[t]
                pi[k] = pi[k] | {t}
                loads[k] += weights[t]
                stats["ejections"] += 1
                ejection_found = True
                if verbose:
                    print(f"  Eject: {s} -> agent {j}, eject {t} -> agent {k}")
                    print(f"    loads: {[f'{l:.2f}' for l in loads]}")
                break

        if not ejection_found:
            # Try placing at next-least-loaded feasible agent
            placed = False
            for i in sorted(range(n), key=lambda i: loads[i]):
                if i == k:
                    continue
                if family.is_feasible_for(i, pi[i] | {s}):
                    pi[i] = pi[i] | {s}
                    loads[i] += weights[s]
                    stats["direct"] += 1
                    placed = True
                    if verbose:
                        print(f"  Direct (non-min): {s} -> agent {i} (load {loads[i]:.2f})")
                    break

            if placed:
                continue

            # Defer
            leftover.append(s)
            stats["deferred"] += 1
            if verbose:
                print(f"  Defer: {s} (w={weights[s]})")

    # Place leftover greedily
    for s in leftover:
        for i in sorted(range(n), key=lambda i: loads[i]):
            if family.is_feasible_for(i, pi[i] | {s}):
                pi[i] = pi[i] | {s}
                loads[i] += weights[s]
                break
        else:
            # Force placement
            i = min(range(n), key=lambda i: loads[i])
            pi[i] = pi[i] | {s}
            loads[i] += weights[s]

    allocated = set()
    for b in pi:
        allocated |= b
    coverage = (allocated == set(S))
    all_feasible = all(family.is_feasible_for(i, b) for i, b in enumerate(pi))
    spread = max(loads) - min(loads) if loads else 0

    stats.update({"coverage": coverage, "all_feasible": all_feasible,
                  "loads": loads, "spread": spread,
                  "ef1": spread <= w_max + 1e-9, "w_max": w_max,
                  "leftover_count": len(leftover)})
    return pi, stats


# ============================================================
# Brute force for per-agent (for verification)
# ============================================================

def brute_force_per_agent(family, S, n, weights):
    """Brute-force min spread for per-agent feasibility."""
    S = list(S)
    m = len(S)
    best_spread = float('inf')
    best_alloc = None

    for assignment in product(range(n), repeat=m):
        pi = [set() for _ in range(n)]
        for j, agent in enumerate(assignment):
            pi[agent].add(S[j])
        if not all(family.is_feasible_for(i, b) for i, b in enumerate(pi)):
            continue
        loads = [sum(weights[s] for s in b) for b in pi]
        spread = max(loads) - min(loads)
        if spread < best_spread:
            best_spread = spread
            best_alloc = [set(b) for b in pi]
    return best_spread, best_alloc


# ============================================================
# Tests
# ============================================================

def test_skill_mix_basic():
    """Test per-agent DWEC on basic skill-mix instances."""
    print("="*70)
    print("PER-AGENT DWEC: Basic Skill-Mix Tests")
    print("="*70)

    # Test 1: Uniform heterogeneous caps
    print("\n  Test 1: Heterogeneous cardinality caps")
    print(f"  {'m':>4} {'n':>4} {'caps':<20} {'w_max':>6} "
          f"{'spread':>7} {'EF1?':>5} {'feas?':>5} {'eject':>5} {'def':>4} {'BF_min':>8}")
    print("  " + "-"*85)

    test_cases = [
        # (m, n, caps, weights)
        (6, 3, [2, 2, 2], {i: float(6-i) for i in range(6)}),
        (6, 3, [3, 2, 1], {i: float(6-i) for i in range(6)}),  # heterogeneous
        (9, 3, [3, 3, 3], {i: float(9-i) for i in range(9)}),
        (9, 3, [4, 3, 2], {i: float(9-i) for i in range(9)}),  # heterogeneous
        (8, 4, [2, 2, 2, 2], {i: float(8-i) for i in range(8)}),
        (8, 4, [3, 2, 2, 1], {i: float(8-i) for i in range(8)}),  # very heterogeneous
        (10, 3, [4, 3, 3], {i: float(10-i) for i in range(10)}),
        (10, 3, [5, 3, 2], {i: float(10-i) for i in range(10)}),  # extreme
    ]

    for m, n, caps, weights in test_cases:
        F = UniformHeterogeneous(range(m), caps)
        pi, info = per_agent_dwec(F, F.S, n, weights)

        # Brute force
        bf_spread, _ = brute_force_per_agent(F, F.S, n, weights)

        ef1_str = "Y" if (info['ef1'] and info['all_feasible'] and info['coverage']) else "N"
        feas_str = "Y" if info['all_feasible'] else "N"
        caps_str = str(caps)

        print(f"  {m:>4} {n:>4} {caps_str:<20} {info['w_max']:>6.1f} "
              f"{info['spread']:>7.2f} {ef1_str:>5} {feas_str:>5} "
              f"{info['ejections']:>5} {info['deferred']:>4} {bf_spread:>8.2f}")


def test_skill_mix_with_skills():
    """Test with actual skill requirements on goods."""
    print("\n" + "="*70)
    print("PER-AGENT DWEC: Skill Requirements on Goods")
    print("="*70)

    print(f"\n  {'m':>4} {'n':>4} {'agent_sk':<15} {'good_sk':<15} "
          f"{'w_max':>6} {'spread':>7} {'EF1?':>5} {'feas?':>5} {'eject':>5}")
    print("  " + "-"*85)

    # Skill levels: 0 = junior, 1 = mid, 2 = senior
    # Goods require certain skill levels
    test_cases = [
        # 6 goods, 3 agents, all can do everything (baseline)
        (6, 3, [2, 2, 2], {i: 0 for i in range(6)}, 2,
         {i: float(6-i) for i in range(6)}),
        # 6 goods, 3 agents, one senior can do hard goods
        (6, 3, [2, 1, 1], {0: 2, 1: 2, 2: 1, 3: 1, 4: 0, 5: 0}, 2,
         {i: float(6-i) for i in range(6)}),
        # 9 goods, 3 agents, mixed skills
        (9, 3, [2, 1, 1], {0: 2, 1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 0, 7: 0, 8: 0}, 3,
         {i: float(9-i) for i in range(9)}),
        # 8 goods, 4 agents, one senior only
        (8, 4, [2, 1, 1, 1], {0: 2, 1: 2, 2: 1, 3: 1, 4: 1, 5: 0, 6: 0, 7: 0}, 2,
         {i: float(8-i) for i in range(8)}),
        # 10 goods, 3 agents, all seniors
        (10, 3, [2, 2, 2], {i: 0 for i in range(10)}, 4,
         {i: float(10-i) for i in range(10)}),
        # 10 goods, 3 agents, skill-constrained
        (10, 3, [2, 1, 0], {0: 2, 1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 7: 0, 8: 0, 9: 0}, 4,
         {i: float(10-i) for i in range(10)}),
    ]

    for m, n, agent_sk, good_sk, r, weights in test_cases:
        F = SkillMixFamily(range(m), agent_sk, good_sk, r)
        pi, info = per_agent_dwec(F, F.S, n, weights)

        ef1_str = "Y" if (info['ef1'] and info['all_feasible'] and info['coverage']) else "N"
        feas_str = "Y" if info['all_feasible'] else "N"
        agent_str = str(agent_sk)
        good_str = str(list(good_sk.values()))

        print(f"  {m:>4} {n:>4} {agent_str:<15} {good_str:<15} "
              f"{info['w_max']:>6.1f} {info['spread']:>7.2f} "
              f"{ef1_str:>5} {feas_str:>5} {info['ejections']:>5}")


def test_heterogeneous_swap_heavy():
    """Test on heterogeneous SwapHeavy (different r_i per agent)."""
    print("\n" + "="*70)
    print("PER-AGENT DWEC: Heterogeneous SwapHeavy")
    print("="*70)

    print(f"\n  {'m':>4} {'n':>4} {'caps':<20} {'w_type':<10} "
          f"{'w_max':>6} {'spread':>7} {'EF1?':>5} {'feas?':>5} {'eject':>5} {'def':>4}")
    print("  " + "-"*85)

    test_cases = [
        (10, 3, [3, 3, 3], "skewed"),
        (10, 3, [4, 3, 2], "skewed"),
        (10, 3, [4, 3, 3], "bimodal"),
        (10, 3, [5, 3, 2], "bimodal"),
        (12, 4, [3, 3, 3, 3], "skewed"),
        (12, 4, [4, 3, 3, 2], "skewed"),
        (7, 3, [2, 2, 2], "bimodal"),
        (7, 3, [3, 2, 2], "bimodal"),
    ]

    for m, n, caps, w_type in test_cases:
        F = HeterogeneousSwapHeavy(range(m), caps)
        if w_type == "skewed":
            weights = {i: float(m - i) for i in range(m)}
        else:
            weights = {i: (5.0 if i < m // 2 else 1.0) for i in range(m)}

        pi, info = per_agent_dwec(F, F.S, n, weights)

        ef1_str = "Y" if (info['ef1'] and info['all_feasible'] and info['coverage']) else "N"
        feas_str = "Y" if info['all_feasible'] else "N"
        caps_str = str(caps)

        print(f"  {m:>4} {n:>4} {caps_str:<20} {w_type:<10} "
              f"{info['w_max']:>6.1f} {info['spread']:>7.2f} "
              f"{ef1_str:>5} {feas_str:>5} {info['ejections']:>5} {info['deferred']:>4}")


def stress_test_per_agent():
    """500-trial stress test on per-agent families."""
    print("\n" + "="*70)
    print("PER-AGENT DWEC: 500-Trial Stress Test")
    print("="*70)

    random.seed(42)
    trials = 500
    results = {"ef1": 0, "non_ef1": 0, "infeasible": 0, "leftover": 0}
    worst_ratio = 0
    family_types = defaultdict(int)
    family_ef1 = defaultdict(int)
    non_ef1_cases = []

    for trial in range(trials):
        family_type = random.choice(["uniform_het", "swapheavy_het", "skill_mix"])

        m = random.randint(6, 12)
        n = random.randint(2, 5)

        if family_type == "uniform_het":
            caps = [random.randint(2, 5) for _ in range(n)]
            F = UniformHeterogeneous(range(m), caps)
            max_cap = sum(caps)
        elif family_type == "swapheavy_het":
            caps = [random.randint(2, 4) for _ in range(n)]
            F = HeterogeneousSwapHeavy(range(m), caps)
            max_cap = sum(caps) + 1  # one agent can have cap+1
        else:  # skill_mix
            r = random.randint(2, 4)
            agent_sk = [random.randint(0, 2) for _ in range(n)]
            good_sk = {i: random.randint(0, 2) for i in range(m)}
            F = SkillMixFamily(range(m), agent_sk, good_sk, r)
            max_cap = n * r

        if m > max_cap:
            results["infeasible"] += 1
            continue

        weight_type = random.choice(["uniform", "skewed", "bimodal", "random"])
        if weight_type == "uniform":
            weights = {i: 1.0 for i in range(m)}
        elif weight_type == "skewed":
            weights = {i: float(m - i) for i in range(m)}
        elif weight_type == "bimodal":
            weights = {i: (5.0 if i < m // 2 else 1.0) for i in range(m)}
        else:
            weights = {i: round(random.uniform(1, 5), 1) for i in range(m)}

        w_max = max(weights.values())

        pi, info = per_agent_dwec(F, F.S, n, weights)

        family_types[family_type] += 1
        if info['leftover_count'] > 0:
            results['leftover'] += 1

        if not info['all_feasible'] or not info['coverage']:
            results['infeasible'] += 1
            continue

        spread = info['spread']
        ratio = spread / w_max if w_max > 0 else 0
        worst_ratio = max(worst_ratio, ratio)

        if info['ef1']:
            results['ef1'] += 1
            family_ef1[family_type] += 1
        else:
            results['non_ef1'] += 1
            non_ef1_cases.append((trial, family_type, m, n, weight_type, spread, w_max,
                                  info.get('leftover_count', 0)))

    print(f"\n  Results over {trials} trials:")
    print(f"    EF1 achieved: {results['ef1']}")
    print(f"    EF1 violated: {results['non_ef1']}")
    print(f"    Infeasible: {results['infeasible']}")
    print(f"    With leftover: {results['leftover']}")
    print(f"    Worst spread/w_max ratio: {worst_ratio:.3f}")

    print(f"\n  By family type:")
    for ft in family_types:
        total = family_types[ft]
        ef1 = family_ef1[ft]
        rate = ef1 / total * 100 if total > 0 else 0
        print(f"    {ft}: {total} trials, {ef1} EF1 ({rate:.0f}%)")

    if non_ef1_cases:
        print(f"\n  Non-EF1 cases (first 10):")
        for trial, ft, m, n, wt, spread, w_max, leftover in non_ef1_cases[:10]:
            print(f"    trial={trial}, type={ft}, m={m}, n={n}, weights={wt}, "
                  f"spread={spread:.2f}, w_max={w_max:.2f}, leftover={leftover}")

    return results, non_ef1_cases


def test_per_agent_vs_ilp():
    """Compare per-agent DWEC against brute-force optimum."""
    print("\n" + "="*70)
    print("PER-AGENT DWEC vs BRUTE-FORCE OPTIMUM")
    print("="*70)

    random.seed(42)
    print(f"\n  {'type':<12} {'m':>4} {'n':>4} {'w_type':<10} "
          f"{'w_max':>6} {'DWEC':>8} {'OPT':>8} {'ratio':>6} {'EF1?':>5}")
    print("  " + "-"*75)

    ratios = []
    for trial in range(20):
        m = random.randint(6, 9)
        n = random.randint(2, 3)
        caps = [random.randint(2, 4) for _ in range(n)]
        F = UniformHeterogeneous(range(m), caps)

        if sum(caps) < m:
            continue  # infeasible

        w_type = random.choice(["skewed", "bimodal", "random"])
        if w_type == "skewed":
            weights = {i: float(m - i) for i in range(m)}
        elif w_type == "bimodal":
            weights = {i: (5.0 if i < m // 2 else 1.0) for i in range(m)}
        else:
            weights = {i: round(random.uniform(1, 5), 1) for i in range(m)}

        w_max = max(weights.values())

        pi_dwec, info_dwec = per_agent_dwec(F, F.S, n, weights)
        bf_spread, _ = brute_force_per_agent(F, F.S, n, weights)

        if bf_spread == float('inf'):
            continue

        ratio = info_dwec['spread'] / max(bf_spread, 0.01)
        ratios.append(ratio)
        ef1 = "Y" if (info_dwec['ef1'] and info_dwec['all_feasible']) else "N"

        print(f"  {'uniform_het':<12} {m:>4} {n:>4} {w_type:<10} "
              f"{w_max:>6.1f} {info_dwec['spread']:>8.2f} {bf_spread:>8.2f} "
              f"{ratio:>6.2f} {ef1:>5}")

    if ratios:
        print(f"\n  Average DWEC/OPT ratio: {sum(ratios)/len(ratios):.2f}")
        print(f"  Max ratio: {max(ratios):.2f}")


def main():
    test_skill_mix_basic()
    test_skill_mix_with_skills()
    test_heterogeneous_swap_heavy()
    stress_test_per_agent()
    test_per_agent_vs_ilp()

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("""
    Per-Agent DWEC extends the algorithm to heterogeneous feasibility:
    - Each agent has their own F_i (skill mix, different caps).
    - The spread bound (spread <= w_max) STILL HOLDS because:
      * Direct placement at least-loaded: load analysis unchanged.
      * Ejection: per-agent feasibility only constrains the SEARCH,
        not the load dynamics.
    - The min-preservation constraint works the same way.

    Key new challenge: when the least-loaded agent can't accept ANY good
    (due to skill mismatch), the algorithm must place at a non-least-loaded
    agent, which can break the spread bound. The current implementation
    handles this with a greedy fallback, but the EF1 guarantee is lost
    in that case.

    Test the algorithm above to see how often this happens.
    """)


if __name__ == "__main__":
    main()
