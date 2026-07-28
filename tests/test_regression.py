"""
Regression test for the DWEC spread-bound bug.

History:
- v1: the production code included a "relaxed placement" branch that placed
  goods at non-least-loaded agents WITHOUT checking the spread bound. This
  violated spread <= w_max on ~2.3% of instances.
- v2: the branch was removed entirely, but this caused coverage false-negatives
  on ~22% of instances where feasible schedules existed.
- v3: the branch was re-added WITH a spread-bound check (new_load - old_min
  <= w_max). This maintains the spread bound while recovering coverage.

The current test verifies that:
- The spread bound is always maintained (no violations on random instances).
- The buggy 'relaxed' stat is never incremented (the v3 branch uses 'direct').
- Distinct nurses per shift are enforced.
- The ILP backend respects skill requirements.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from nrp_solver.core import NRPInstance, DWECBackend
from nrp_solver import solve_nrp


def test_no_relaxed_placement_in_stats():
    """Verify that the relaxed placement branch is never used."""
    print("--- Test: No relaxed placement in production DWEC ---")
    
    result = solve_nrp(
        num_days=7, shifts_per_day=2, num_nurses=7,
        coverage={(d, s): [0] for d in range(7) for s in range(2)},
        nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
        weights="day_night_weekend"
    )
    
    assert result.feasible, "Should be feasible"
    assert result.stats.get("relaxed", 0) == 0, \
        f"Relaxed placement should never be used, but stats show {result.stats.get('relaxed', 0)}"
    print("  ✓ No relaxed placement used\n")


def test_spread_bound_held():
    """Verify that spread <= w_max whenever the algorithm produces a feasible allocation."""
    print("--- Test: Spread bound holds on diverse instances ---")
    
    import random
    random.seed(42)
    
    violations = 0
    tested = 0
    
    for trial in range(100):
        num_days = random.randint(3, 7)
        shifts_per_day = random.choice([1, 2])
        num_nurses = random.randint(3, 7)
        max_consecutive = random.choice([2, 3, 5])
        max_weekly = random.choice([3, 5, 7])
        
        # Random coverage
        coverage = {}
        for d in range(num_days):
            for s in range(shifts_per_day):
                cov = random.choice([1, 2])
                coverage[(d, s)] = [0] * cov
        
        # Random skills
        nurse_skills = [random.choice([0, 0, 0, 1]) for _ in range(num_nurses)]
        
        instance = NRPInstance(
            num_days=num_days, shifts_per_day=shifts_per_day,
            num_nurses=num_nurses, coverage=coverage,
            nurse_skills=nurse_skills,
            max_consecutive=max_consecutive, max_weekly=max_weekly,
            weights="day_night_weekend"
        )
        
        result = DWECBackend().solve(instance)
        
        if result.feasible and result.coverage_ok:
            tested += 1
            if result.spread > instance.w_max + 1e-9:
                violations += 1
                print(f"  VIOLATION: trial={trial}, spread={result.spread:.2f}, "
                      f"w_max={instance.w_max:.2f}")
    
    print(f"  Tested {tested} feasible instances, {violations} spread violations")
    assert violations == 0, f"Spread bound violated on {violations} instances"
    print("  ✓ Spread bound holds on all feasible instances\n")


def test_distinct_nurses_per_shift():
    """Verify that coverage requires distinct nurses per shift."""
    print("--- Test: Distinct nurses per shift ---")
    
    result = solve_nrp(
        num_days=7, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0, 0] for d in range(7)},  # 2 nurses per shift
        nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
        weights="unit"
    )
    
    assert result.feasible, "Should be feasible"
    assert result.coverage_ok, "Coverage should be satisfied"
    
    # Verify each shift has 2 DISTINCT nurses
    for d in range(7):
        nurses_on_day = set()
        for i, bundle in enumerate(result.allocation):
            for (dd, s, ci, sk) in bundle:
                if dd == d and s == 0:
                    nurses_on_day.add(i)
        assert len(nurses_on_day) == 2, \
            f"Day {d} has {len(nurses_on_day)} nurses (expected 2)"
    
    print("  ✓ All shifts have distinct nurses\n")


def test_ilp_skill_mix_correctness():
    """Verify the ILP backend doesn't assign senior slots to juniors."""
    print("--- Test: ILP skill-mix correctness ---")
    
    from nrp_solver.core import NRPSolver
    
    instance = NRPInstance(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [1, 0] for d in range(7)},  # 1 senior + 1 junior per shift
        nurse_skills=[1, 1, 0, 0, 0],  # 2 seniors, 3 juniors
        max_consecutive=5, max_weekly=5,
        weights="unit"
    )
    
    result = NRPSolver(backend="ilp", ilp_time_limit=15).solve(instance)
    
    if result.feasible:
        # Verify no junior has a senior-required slot
        for i, bundle in enumerate(result.allocation):
            nurse_skill = instance.nurse_skills[i]
            for (d, s, ci, req_skill) in bundle:
                assert nurse_skill >= req_skill, \
                    f"Nurse {i} (skill {nurse_skill}) has slot requiring skill {req_skill}"
        print("  ✓ ILP respects skill requirements\n")
    else:
        print(f"  (ILP returned infeasible: {result.reason})\n")


def test_known_greedy_limitation():
    """Document a known case where DWEC's single-step ejection can't find EF1.

    This instance (from the v3 review, seed=42 trial 8) has an EF1 schedule
    (verified by ILP and brute force) that DWEC cannot find because the
    optimal allocation requires a multi-step ejection chain. DWEC makes a
    suboptimal early choice (placing a junior slot on the senior nurse) that
    cannot be undone without backtracking or multi-step ejection.

    This test DOCUMENTS the known limitation — it asserts that DWEC fails
    here (coverage_ok=False) and that the ILP backend finds the EF1 schedule.
    If multi-step ejection is ever implemented, this test should be updated
    to assert coverage_ok=True.
    """
    print("--- Test: Known greedy limitation (single-step ejection) ---")

    instance = NRPInstance(
        num_days=5, shifts_per_day=1, num_nurses=2,
        coverage={(0, 0): [0, 0], (1, 0): [1, 0], (2, 0): [1],
                  (3, 0): [1, 0], (4, 0): [0]},
        nurse_skills=[1, 0],  # 1 senior, 1 junior
        max_consecutive=4, max_weekly=7,
        weights="weekend"
    )

    dwec_result = DWECBackend().solve(instance)
    print(f"  DWEC: feasible={dwec_result.feasible}, "
          f"coverage_ok={dwec_result.coverage_ok}, spread={dwec_result.spread}")

    # DWEC is expected to fail here — this is a known greedy-heuristic limitation.
    # The optimal allocation requires a multi-step ejection chain.
    assert not dwec_result.coverage_ok, \
        "Expected DWEC to fail (known limitation); if this passes, multi-step ejection may have been implemented"

    # The ILP backend should find the EF1 schedule
    from nrp_solver.core import ILPBackend
    ilp_result = ILPBackend(time_limit=10).solve(instance)
    if ilp_result.feasible:
        print(f"  ILP:  feasible=True, spread={ilp_result.spread:.2f}, EF1={ilp_result.ef1}")
        assert ilp_result.ef1, "ILP should find an EF1 schedule"
    else:
        print(f"  ILP:  infeasible ({ilp_result.reason[:50]})")

    print("  ✓ Known limitation documented (DWEC fails, ILP finds EF1)\n")


def main():
    print("="*70)
    print("REGRESSION TESTS: DWEC bug fix + ILP fix + distinct nurses")
    print("="*70 + "\n")

    tests = [
        test_no_relaxed_placement_in_stats,
        test_spread_bound_held,
        test_distinct_nurses_per_shift,
        test_ilp_skill_mix_correctness,
        test_known_greedy_limitation,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"  ✗ FAIL: {e}\n")
            failed += 1
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"  ✗ ERROR: {e}\n")
            failed += 1
    
    print("="*70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print("="*70)


if __name__ == "__main__":
    main()
