"""
Coverage Constraints: The Hard Problem

WHY COVERAGE IS HARDER THAN PER-AGENT FEASIBILITY:

  Standard fair division (what we've solved):
    - Each good goes to exactly one agent.
    - Each agent's bundle must be in their F_i.
    - Constraint is PER-AGENT (independent across agents).

  Coverage (what operational NRP needs):
    - Each SHIFT needs a specific NUMBER of nurses with specific SKILLS.
    - E.g., "Monday day shift needs 2 nurses, at least 1 senior."
    - This is a GLOBAL constraint coupling multiple agents.
    - It's a matroid on (agent, shift) pairs, intersecting per-agent F_i.

WHY DWEC BREAKS:

  DWEC moves a good from agent j to agent k. With coverage:
    - Removing a good from j might violate coverage at that shift
      (now has fewer nurses than required).
    - Adding a good to k might violate skill requirements
      (now has 2 seniors, no junior).

  The ejection chain assumes goods are independent. With coverage,
  goods (shifts) have INTERNAL structure (multiple nurses per shift),
  and the ejection must preserve that structure.

TWO POSSIBLE APPROACHES:

  Approach A: Expand goods, treat coverage as a matroid intersection.
    - Each (day, shift, coverage-slot) is a separate good.
    - Coverage = partition matroid (each shift's slots go to distinct agents,
      with skill requirements).
    - Per-agent F_i = downward-closed family.
    - Allocation = point in the intersection.
    - EF1 under matroid intersection is the open theoretical question.

  Approach B: Batch assignment per shift.
    - Process shifts (not individual goods) in decreasing weight order.
    - For each shift, assign the required number of nurses simultaneously.
    - Pick the least-loaded feasible nurses (respecting skills).
    - Ejection: if a shift can't be covered, eject nurses from other shifts.

  Approach B is more directly an extension of DWEC. Let me start there.

THE BATCH-DWEC ALGORITHM (Approach B):

  For each shift s (decreasing total weight):
    1. Determine required nurses: c(s) nurses, with skill requirements.
    2. Find the c(s) least-loaded nurses who satisfy the skill requirements
       and for whom adding s is feasible (per-agent F_i).
    3. Assign s to all c(s) nurses simultaneously.
    4. If not enough feasible nurses: EJECTION.
       - Find nurses j_1, ..., j_k and shifts t_1, ..., t_k to eject.
       - Eject t_i from j_i, assign s to j_i.
       - The ejected shifts t_i need new homes (recursive).

SPREAD ANALYSIS (key question):

  When we assign shift s to c nurses simultaneously:
    - Each nurse's load increases by w(s).
    - If we pick the c least-loaded: the new loads are
      ℓ_{(1)} + w(s), ..., ℓ_{(c)} + w(s) (order statistics).
    - New max = ℓ_{(c)} + w(s).
    - New min = min(others, ℓ_{(c)} + w(s)) >= ℓ_{(1)} (the old min, if c < n).
    - Spread = ℓ_{(c)} + w(s) - ℓ_{(1)}.
    - For EF1: need ℓ_{(c)} + w(s) - ℓ_{(1)} <= w_max.
    - Since ℓ_{(c)} - ℓ_{(1)} <= old_spread <= w_max (inductive hypothesis):
      spread <= w_max + w(s) <= 2*w_max. NOT EF1!

  PROBLEM: Batch assignment of c nurses can increase spread by w(s),
  even if we pick the least-loaded. This is because ALL c nurses get
  the shift, including the c-th least-loaded who might already be
  close to the max.

  This is a fundamental obstacle. Let me think about it more.

  RESOLUTION ATTEMPT: If c = 1 (single nurse per shift), the problem
  reduces to standard DWEC. The issue is c > 1.

  For c > 1: the spread bound becomes spread <= c * w_max (each batch
  can increase spread by w(s), and there are multiple batches).

  This is too weak. We need a better approach.

  BETTER IDEA: Don't assign all c nurses at once. Assign them one at a time,
  re-sorting after each assignment.

    For shift s needing c nurses:
      For i = 1 to c:
        k = current least-loaded feasible nurse (with right skill)
        Assign s to k.
        (This is just standard DWEC, but the "good" is the same shift s,
         assigned to multiple nurses.)

  This is equivalent to treating each coverage slot as a separate good
  (Approach A). The spread bound holds as in standard DWEC.

  BUT: the skill requirement couples the slots. If shift s needs
  "1 senior + 1 junior", the first slot must go to a senior and the
  second to a junior. The ordering matters.

  ALGORITHM (refined):
    For each shift s (decreasing weight):
      Determine skill requirements: e.g., [senior, junior].
      For each required skill (in some order):
        Find least-loaded feasible nurse with that skill.
        Assign s to that nurse.
        (Use ejection if needed.)

  The skill ordering within a shift matters. Process higher-skill
  requirements first (they're more constrained).
"""

import random
from itertools import combinations, product
from collections import defaultdict
from local_exchange_ef1 import FeasibilityFamily


class CoverageNRPFamily:
    """NRP with full coverage constraints.

    Goods = shifts, each requiring multiple nurses with specific skills.
    coverage: dict (day, slot) -> list of required skills
              e.g., {(0, 'day'): [1, 0]} means day 0 day-shift needs
              1 senior (skill 1) and 1 junior (skill 0).
    """
    def __init__(self, num_days, shifts_per_day, num_nurses,
                 coverage, nurse_skills, max_consecutive, max_weekly):
        self.num_days = num_days
        self.shifts_per_day = shifts_per_day
        self.num_nurses = num_nurses
        self.coverage = coverage  # (day, slot) -> [skill requirements]
        self.nurse_skills = list(nurse_skills)
        self.max_consecutive = max_consecutive
        self.max_weekly = max_weekly

        # The "goods" are (day, slot, skill_requirement_index) tuples.
        # Each represents one coverage slot that needs a specific skill.
        self.goods = []
        for d in range(num_days):
            for s in range(shifts_per_day):
                if (d, s) in coverage:
                    for idx, req_skill in enumerate(coverage[(d, s)]):
                        self.goods.append((d, s, idx, req_skill))
        self.m = len(self.goods)
        self.S = self.goods  # alias for compatibility

    def is_feasible_for(self, agent_idx, A):
        """Check if bundle A is feasible for agent agent_idx.
        A is a set of (day, slot, cov_idx, req_skill) tuples."""
        A = set(A)

        # Cardinality (weekly cap)
        for week_start in range(0, self.num_days, 7):
            week_end = min(week_start + 7, self.num_days)
            count = sum(1 for (d, s, ci, sk) in A if week_start <= d < week_end)
            if count > self.max_weekly:
                return False

        # Consecutive days
        days = sorted(set(d for d, s, ci, sk in A))
        run = 1
        for i in range(1, len(days)):
            if days[i] == days[i-1] + 1:
                run += 1
                if run > self.max_consecutive:
                    return False
            else:
                run = 1

        # One shift per day per nurse
        days_with_shifts = defaultdict(set)
        for (d, s, ci, sk) in A:
            days_with_shifts[d].add(s)
        for d, shifts in days_with_shifts.items():
            if len(shifts) > 1 and self.shifts_per_day > 1:
                return False

        # Skill check
        nurse_skill = self.nurse_skills[agent_idx]
        for (d, s, ci, req_skill) in A:
            if nurse_skill < req_skill:
                return False

        return True

    def make_weights(self, scheme="day_night_weekend"):
        """Weights per coverage slot (same as the shift's weight)."""
        weights = {}
        for good in self.goods:
            d, s, ci, sk = good
            is_weekend = (d % 7) >= 5
            if scheme == "unit":
                w = 1.0
            elif scheme == "day_night":
                w = 2.0 if s == 1 else 1.0
            elif scheme == "weekend":
                w = 1.5 if is_weekend else 1.0
            elif scheme == "day_night_weekend":
                if s == 1 and is_weekend:
                    w = 3.0
                elif s == 1:
                    w = 2.0
                elif is_weekend:
                    w = 1.5
                else:
                    w = 1.0
            else:
                w = 1.0
            weights[good] = w
        return weights


# ============================================================
# Coverage DWEC Algorithm
# ============================================================

def coverage_dwec(family, S, n, weights, verbose=False):
    """
    DWEC adapted for coverage constraints.

    Key insight: treat each coverage SLOT as a separate good.
    Process all slots of a shift together, in decreasing weight order.
    Within a shift, process higher-skill requirements first
    (more constrained).

    The standard DWEC spread bound applies: each slot is placed at the
    least-loaded feasible nurse, with ejection if needed.
    """
    S = list(S)
    m = len(S)
    w_max = max(weights.values()) if weights else 0

    # Sort goods by: (1) decreasing weight, (2) decreasing skill requirement
    # This ensures we place the most constrained slots first.
    sorted_goods = sorted(S, key=lambda g: (-weights[g], -g[3]))

    pi = [set() for _ in range(n)]
    loads = [0.0] * n
    leftover = []
    stats = {"direct": 0, "ejections": 0, "deferred": 0, "relaxed": 0}

    # Track which (day, slot) shifts are fully covered
    shift_coverage = defaultdict(set)  # (day, slot) -> set of cov_idx assigned

    for s_good in sorted_goods:
        d, s, ci, req_skill = s_good
        min_load = min(loads)
        k = min(range(n), key=lambda i: loads[i])

        # Direct placement at least-loaded k (must have required skill)
        if (family.nurse_skills[k] >= req_skill and
            family.is_feasible_for(k, pi[k] | {s_good})):
            pi[k] = pi[k] | {s_good}
            loads[k] += weights[s_good]
            shift_coverage[(d, s)].add(ci)
            stats["direct"] += 1
            continue

        # Try ejection: find (j, t) with per-agent + skill constraints
        ejection_found = False
        agents_by_load = sorted(range(n), key=lambda i: -loads[i])
        for j in agents_by_load:
            if abs(loads[j] - min_load) < 1e-9:
                continue
            # j must have the required skill for s_good
            if family.nurse_skills[j] < req_skill:
                continue
            ejectable = []
            for t in pi[j]:
                if weights[t] >= weights[s_good] - 1e-9:
                    new_j = (pi[j] - {t}) | {s_good}
                    if family.is_feasible_for(j, new_j):
                        # t must go to k. k must have the skill for t.
                        t_req_skill = t[3]
                        if family.nurse_skills[k] >= t_req_skill:
                            if family.is_feasible_for(k, pi[k] | {t}):
                                if loads[j] - min_load >= weights[t] - weights[s_good] - 1e-9:
                                    ejectable.append(t)
            if ejectable:
                t = min(ejectable, key=lambda x: weights[x])
                pi[j] = (pi[j] - {t}) | {s_good}
                loads[j] += weights[s_good] - weights[t]
                pi[k] = pi[k] | {t}
                loads[k] += weights[t]
                shift_coverage[(d, s)].add(ci)
                stats["ejections"] += 1
                ejection_found = True
                break

        if ejection_found:
            continue

        # Relaxed: place at least-loaded feasible nurse with right skill
        feasible_agents = [i for i in range(n)
                          if family.nurse_skills[i] >= req_skill and
                          family.is_feasible_for(i, pi[i] | {s_good})]
        if feasible_agents:
            i = min(feasible_agents, key=lambda i: loads[i])
            pi[i] = pi[i] | {s_good}
            loads[i] += weights[s_good]
            shift_coverage[(d, s)].add(ci)
            stats["relaxed"] += 1
        else:
            leftover.append(s_good)
            stats["deferred"] += 1

    # Place leftover greedily — NO forcing. If no feasible nurse, leave uncovered.
    for s_good in leftover:
        d, s, ci, req_skill = s_good
        feasible_agents = [i for i in range(n)
                          if family.nurse_skills[i] >= req_skill and
                          family.is_feasible_for(i, pi[i] | {s_good})]
        if feasible_agents:
            i = min(feasible_agents, key=lambda i: loads[i])
            pi[i] = pi[i] | {s_good}
            loads[i] += weights[s_good]
            shift_coverage[(d, s)].add(ci)
        # else: leave uncovered (coverage_ok will be False)

    # Verify coverage
    coverage_ok = True
    for (d, s), reqs in family.coverage.items():
        if len(shift_coverage[(d, s)]) != len(reqs):
            coverage_ok = False
            break

    allocated = set()
    for b in pi:
        allocated |= b
    all_feasible = all(family.is_feasible_for(i, b) for i, b in enumerate(pi))
    spread = max(loads) - min(loads) if loads else 0

    stats.update({"coverage_ok": coverage_ok,
                  "all_feasible": all_feasible,
                  "loads": loads, "spread": spread,
                  "ef1": spread <= w_max + 1e-9, "w_max": w_max,
                  "leftover_count": len(leftover)})
    return pi, stats


# ============================================================
# Tests
# ============================================================

def test_basic_coverage():
    """Test coverage DWEC on basic instances."""
    print("="*70)
    print("COVERAGE DWEC: Basic Tests")
    print("="*70)

    test_cases = []

    # Case 1: 1 week, 1 shift/day, 2 nurses per shift, no skills
    coverage = {(d, 0): [0, 0] for d in range(7)}  # 2 juniors per shift
    F = CoverageNRPFamily(7, 1, 7, coverage, [0]*7, max_consecutive=5, max_weekly=5)
    test_cases.append(("1wk 1s n7 cov2 noskill", F, 7))

    # Case 2: 1 week, 1 shift/day, 2 nurses per shift, with skills
    coverage = {(d, 0): [1, 0] for d in range(7)}  # 1 senior + 1 junior per shift
    F = CoverageNRPFamily(7, 1, 7, coverage, [1, 1, 0, 0, 0, 0, 0],
                         max_consecutive=5, max_weekly=5)
    test_cases.append(("1wk 1s n7 cov2 1senior", F, 7))

    # Case 3: 2 weeks, 1 shift/day, 2 nurses per shift
    coverage = {(d, 0): [0, 0] for d in range(14)}
    F = CoverageNRPFamily(14, 1, 10, coverage, [0]*10, max_consecutive=5, max_weekly=5)
    test_cases.append(("2wk 1s n10 cov2", F, 10))

    # Case 4: 1 week, 2 shifts/day, 1 nurse per shift
    coverage = {(d, s): [0] for d in range(7) for s in range(2)}
    F = CoverageNRPFamily(7, 2, 5, coverage, [0]*5, max_consecutive=5, max_weekly=5)
    test_cases.append(("1wk 2s n5 cov1", F, 5))

    # Case 5: 1 week, 2 shifts/day, 2 nurses per shift
    coverage = {(d, s): [0, 0] for d in range(7) for s in range(2)}
    F = CoverageNRPFamily(7, 2, 10, coverage, [0]*10, max_consecutive=5, max_weekly=5)
    test_cases.append(("1wk 2s n10 cov2", F, 10))

    # Case 6: With skills, 2 shifts/day
    coverage = {(d, s): [1, 0] for d in range(7) for s in range(2)}
    F = CoverageNRPFamily(7, 2, 10, coverage,
                         [1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
                         max_consecutive=5, max_weekly=5)
    test_cases.append(("1wk 2s n10 cov2 4senior", F, 10))

    print(f"\n  {'Instance':<30} {'m':>4} {'n':>4} {'w_max':>6} "
          f"{'spread':>7} {'EF1?':>5} {'cov?':>5} {'feas?':>5} {'relax':>5}")
    print("  " + "-"*80)

    for name, F, n in test_cases:
        weights = F.make_weights("day_night_weekend" if F.shifts_per_day == 2 else "unit")
        pi, info = coverage_dwec(F, F.S, n, weights)

        ef1 = "Y" if (info['ef1'] and info['all_feasible']) else "N"
        cov = "Y" if info['coverage_ok'] else "N"
        feas = "Y" if info['all_feasible'] else "N"

        print(f"  {name:<30} {F.m:>4} {n:>4} {info['w_max']:>6.1f} "
              f"{info['spread']:>7.2f} {ef1:>5} {cov:>5} {feas:>5} "
              f"{info['relaxed']:>5}")


def test_coverage_skill_concentration():
    """Test cases where skill concentration forces structural limits."""
    print("\n" + "="*70)
    print("COVERAGE with SKILL CONCENTRATION")
    print("="*70)

    print("\n  Testing when skill requirements force structural imbalance:")

    # 1 week, 1 shift/day, each shift needs 1 senior + 1 junior
    # Only 2 seniors available. 7 shifts * 1 senior = 7 senior-shifts.
    # 2 seniors must cover 7 senior-shifts. Each gets 3-4. Load = 3-4.
    # 5 juniors cover 7 junior-shifts. Each gets 1-2. Load = 1-2.
    # Spread = 4 - 1 = 3 > w_max = 1. Structural!
    coverage = {(d, 0): [1, 0] for d in range(7)}
    F = CoverageNRPFamily(7, 1, 7, coverage,
                         [1, 1, 0, 0, 0, 0, 0],  # 2 seniors, 5 juniors
                         max_consecutive=5, max_weekly=5)
    weights = F.make_weights("unit")

    pi, info = coverage_dwec(F, F.S, 7, weights)
    print(f"\n  1wk 1s, 2 seniors + 5 juniors, each shift needs 1S+1J:")
    print(f"    m={F.m} (14 slots), n=7")
    print(f"    Loads: {info['loads']}")
    print(f"    Spread: {info['spread']:.2f}, w_max: {info['w_max']:.2f}")
    print(f"    EF1: {info['ef1']}, Coverage OK: {info['coverage_ok']}")
    print(f"    Direct: {info['direct']}, Ejections: {info['ejections']}, "
          f"Relaxed: {info['relaxed']}, Deferred: {info['deferred']}")

    # More seniors
    F2 = CoverageNRPFamily(7, 1, 7, coverage,
                          [1, 1, 1, 1, 0, 0, 0],  # 4 seniors, 3 juniors
                          max_consecutive=5, max_weekly=5)
    pi, info = coverage_dwec(F2, F2.S, 7, weights)
    print(f"\n  1wk 1s, 4 seniors + 3 juniors, each shift needs 1S+1J:")
    print(f"    Loads: {info['loads']}")
    print(f"    Spread: {info['spread']:.2f}, EF1: {info['ef1']}, "
          f"Coverage: {info['coverage_ok']}")

    # Balanced: 7 seniors, 7 juniors (but only 7 nurses total)
    # Can't have 14 nurses. Let's try 7 nurses, all senior.
    F3 = CoverageNRPFamily(7, 1, 7, coverage,
                          [1]*7,  # all senior
                          max_consecutive=5, max_weekly=5)
    pi, info = coverage_dwec(F3, F3.S, 7, weights)
    print(f"\n  1wk 1s, 7 seniors, each shift needs 1S+1J:")
    print(f"    (seniors can fill both roles)")
    print(f"    Loads: {info['loads']}")
    print(f"    Spread: {info['spread']:.2f}, EF1: {info['ef1']}, "
          f"Coverage: {info['coverage_ok']}")


def stress_test_coverage():
    """Stress test coverage DWEC on diverse instances."""
    print("\n" + "="*70)
    print("COVERAGE DWEC STRESS TEST (200 trials)")
    print("="*70)

    random.seed(42)
    trials = 200
    results = {"ef1": 0, "non_ef1": 0, "infeasible": 0, "coverage_fail": 0}
    family_results = defaultdict(lambda: {"ef1": 0, "total": 0, "cov_fail": 0})

    for trial in range(trials):
        # Random instance
        num_days = random.choice([7, 14])
        shifts_per_day = random.choice([1, 2])
        num_nurses = random.randint(5, 12)
        cov_per_shift = random.choice([1, 2])

        # Skill mix
        skill_mix_type = random.choice(["none", "light", "heavy"])
        if skill_mix_type == "none":
            nurse_skills = [0] * num_nurses
            req_skills_per_shift = [0] * cov_per_shift
        elif skill_mix_type == "light":
            num_senior = max(1, num_nurses // 3)
            nurse_skills = [1] * num_senior + [0] * (num_nurses - num_senior)
            req_skills_per_shift = [0] * cov_per_shift  # no skill req
        else:  # heavy
            num_senior = max(1, num_nurses // 3)
            nurse_skills = [1] * num_senior + [0] * (num_nurses - num_senior)
            if cov_per_shift == 2:
                req_skills_per_shift = [1, 0]  # 1 senior + 1 junior
            else:
                req_skills_per_shift = [0]  # single nurse, no skill req

        max_consecutive = random.choice([3, 5, 7])
        max_weekly = random.choice([3, 5, 7])

        coverage = {}
        for d in range(num_days):
            for s in range(shifts_per_day):
                coverage[(d, s)] = list(req_skills_per_shift)

        F = CoverageNRPFamily(num_days, shifts_per_day, num_nurses,
                             coverage, nurse_skills, max_consecutive, max_weekly)

        # Check feasibility (rough: enough nurses with right skills)
        total_senior_slots = sum(1 for reqs in coverage.values()
                                 for r in reqs if r == 1)
        if total_senior_slots > sum(1 for sk in nurse_skills if sk >= 1) * max_weekly:
            results["infeasible"] += 1
            continue

        weights = F.make_weights("day_night_weekend" if shifts_per_day == 2 else "unit")

        pi, info = coverage_dwec(F, F.S, num_nurses, weights)

        ft = skill_mix_type
        family_results[ft]["total"] += 1

        if not info['coverage_ok']:
            results["coverage_fail"] += 1
            family_results[ft]["cov_fail"] += 1
            continue

        if not info['all_feasible']:
            results["infeasible"] += 1
            continue

        if info['ef1']:
            results["ef1"] += 1
            family_results[ft]["ef1"] += 1
        else:
            results["non_ef1"] += 1

    print(f"\n  Results over {trials} trials:")
    print(f"    EF1 achieved: {results['ef1']}")
    print(f"    Non-EF1 (feasible): {results['non_ef1']}")
    print(f"    Coverage failed: {results['coverage_fail']}")
    print(f"    Infeasible: {results['infeasible']}")

    print(f"\n  By skill mix type:")
    for ft, r in family_results.items():
        total = r["total"]
        if total > 0:
            print(f"    {ft}: {total} trials, EF1={r['ef1']} ({r['ef1']/total*100:.0f}%), "
                  f"cov_fail={r['cov_fail']}")


def main():
    test_basic_coverage()
    test_coverage_skill_concentration()
    stress_test_coverage()

    print("\n" + "="*70)
    print("COVERAGE EXTENSION SUMMARY")
    print("="*70)
    print("""
    The coverage DWEC algorithm:
    - Treats each coverage SLOT as a separate good.
    - Processes slots in decreasing weight + decreasing skill order.
    - Uses standard DWEC (direct placement at least-loaded, ejection).
    - Handles skill requirements by filtering feasible nurses.

    Key findings from the tests above. The spread bound question
    (whether EF1 holds under coverage) needs careful analysis.
    """)


if __name__ == "__main__":
    main()
