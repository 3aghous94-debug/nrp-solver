"""
Comprehensive test of the pre-assignment conflict detection fix.

Tests all conflict types:
1. Day unavailability conflict
2. Shift unavailability conflict
3. Weekday availability conflict
4. Vacation period conflict
5. Skill mismatch conflict
6. Max consecutive days conflict
7. Max weekly cap conflict
8. One shift per day conflict
9. Max night shifts conflict
10. Non-existent shift conflict
11. Already-occupied slot conflict
12. Valid pre-assignments (no false positives)
"""

import sys
sys.path.insert(0, '/home/z/my-project/scripts')
from three_features import solve_with_preassignment, PreAssignmentNRPInstance


def test_conflict_day_unavailability():
    """Pre-assignment conflicts with day unavailability."""
    print("--- Test 1: Day unavailability conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}},  # nurse 0 unavailable day 3
        pre_assignments={0: {(3, 0)}}  # but pre-assigned day 3
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible, "Should be infeasible"
    assert "day 3" in result.reason.lower() or "unavailable" in result.reason.lower(), \
           "Reason should mention day 3 or unavailability"
    print("  ✓ PASS\n")


def test_conflict_shift_unavailability():
    """Pre-assignment conflicts with shift unavailability."""
    print("--- Test 2: Shift unavailability conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=2, num_nurses=5,
        coverage={(d, s): [0] for d in range(7) for s in range(2)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_shifts={0: {1}},  # nurse 0 can't do shift 1 (nights)
        pre_assignments={0: {(0, 1)}}  # but pre-assigned night shift
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "shift 1" in result.reason.lower() or "unavailable" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_weekday_availability():
    """Pre-assignment conflicts with weekday availability."""
    print("--- Test 3: Weekday availability conflict ---")
    result = solve_with_preassignment(
        num_days=14, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0] for d in range(14)},
        nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
        weights="unit",
        available_weekdays={0: {0, 2, 4}},  # nurse 0 only Mon/Wed/Fri
        pre_assignments={0: {(1, 0)}}  # but pre-assigned Tuesday (day 1)
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "weekday" in result.reason.lower() or "doesn't work" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_vacation():
    """Pre-assignment conflicts with vacation period."""
    print("--- Test 4: Vacation conflict ---")
    result = solve_with_preassignment(
        num_days=14, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0] for d in range(14)},
        nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
        weights="unit",
        vacation_periods={0: [(10, 13)]},  # nurse 0 on vacation days 10-13
        pre_assignments={0: {(11, 0)}}  # but pre-assigned day 11
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "vacation" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_skill_mismatch():
    """Pre-assignment conflicts with skill requirement."""
    print("--- Test 5: Skill mismatch conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [1] for d in range(7)},  # all shifts need senior (skill 1)
        nurse_skills=[0, 0, 0, 0, 1],  # only nurse 4 is senior
        max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={0: {(3, 0)}}  # nurse 0 (junior) pre-assigned to senior shift
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "skill" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_max_consecutive():
    """Pre-assignment violates max consecutive days."""
    print("--- Test 6: Max consecutive days conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=2, max_weekly=5,  # max 2 consecutive
        weights="unit",
        pre_assignments={0: {(0, 0), (1, 0), (2, 0)}}  # 3 consecutive - violates
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "consecutive" in result.reason.lower() or "violates" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_max_weekly():
    """Pre-assignment violates max weekly cap."""
    print("--- Test 7: Max weekly cap conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=7, max_weekly=3,  # max 3 per week
        weights="unit",
        pre_assignments={0: {(0, 0), (1, 0), (2, 0), (3, 0)}}  # 4 shifts - violates
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "weekly" in result.reason.lower() or "violates" in result.reason.lower() or \
           "max_weekly" in result.reason.lower() or "exceed" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_one_shift_per_day():
    """Pre-assignment violates one-shift-per-day."""
    print("--- Test 8: One shift per day conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=2, num_nurses=5,
        coverage={(d, s): [0] for d in range(7) for s in range(2)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={0: {(0, 0), (0, 1)}}  # nurse 0 assigned both shifts day 0
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "multiple shifts" in result.reason.lower() or "violates" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_max_night_shifts():
    """Pre-assignment violates max night shifts."""
    print("--- Test 9: Max night shifts conflict ---")
    result = solve_with_preassignment(
        num_days=14, shifts_per_day=2, num_nurses=5,
        coverage={(d, s): [0] for d in range(14) for s in range(2)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=10,
        weights="unit",
        max_night_shifts={0: 2},  # nurse 0 max 2 nights
        pre_assignments={0: {(0, 1), (1, 1), (2, 1)}}  # 3 nights - violates
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "night" in result.reason.lower() or "violates" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_nonexistent_shift():
    """Pre-assignment to a non-existent shift."""
    print("--- Test 10: Non-existent shift conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},  # only shift 0 exists
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={0: {(3, 1)}}  # shift 1 doesn't exist
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    assert "not in coverage" in result.reason.lower()
    print("  ✓ PASS\n")


def test_conflict_already_occupied():
    """Pre-assignment to a slot already taken (with coverage 1)."""
    print("--- Test 11: Already-occupied slot conflict ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},  # 1 nurse per shift
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={0: {(3, 0)}, 1: {(3, 0)}}  # both claim day 3 shift 0
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    # The second pre-assignment should detect the slot is already taken
    assert "already" in result.reason.lower() or "conflict" in result.reason.lower()
    print("  ✓ PASS\n")


def test_valid_preassignment_no_false_positive():
    """Valid pre-assignments should NOT trigger conflict."""
    print("--- Test 12: Valid pre-assignment (no false positive) ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={0: {(2, 0)}, 2: {(5, 0)}}  # valid
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Spread: {result.spread}, EF1: {result.ef1}")
    assert result.feasible, "Valid pre-assignment should be feasible"
    # Verify pre-assignments respected
    assert any(g[0] == 2 and g[1] == 0 for g in result.allocation[0])
    assert any(g[0] == 5 and g[1] == 0 for g in result.allocation[2])
    print("  ✓ PASS\n")


def test_valid_with_availability():
    """Valid pre-assignment that respects availability."""
    print("--- Test 13: Valid pre-assignment respecting availability ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}},  # nurse 0 unavailable day 3
        pre_assignments={0: {(2, 0)}}  # nurse 0 pre-assigned day 2 (available)
    )
    print(f"  Feasible: {result.feasible}")
    assert result.feasible
    assert any(g[0] == 2 and g[1] == 0 for g in result.allocation[0])
    print("  ✓ PASS\n")


def test_multiple_conflicts():
    """Multiple pre-assignment conflicts reported together."""
    print("--- Test 14: Multiple conflicts reported together ---")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=2, num_nurses=5,
        coverage={(d, s): [0] for d in range(7) for s in range(2)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}},
        vacation_periods={1: [(0, 6)]},  # nurse 1 entire week
        pre_assignments={
            0: {(3, 0)},  # conflict: unavailable day 3
            1: {(2, 1)},  # conflict: on vacation
        }
    )
    print(f"  Feasible: {result.feasible}")
    print(f"  Reason: {result.reason}")
    assert not result.feasible
    # Should mention both conflicts
    assert "nurse 0" in result.reason.lower()
    assert "nurse 1" in result.reason.lower()
    print("  ✓ PASS\n")


def main():
    print("="*70)
    print("PRE-ASSIGNMENT CONFLICT DETECTION — COMPREHENSIVE TESTS")
    print("="*70 + "\n")
    
    tests = [
        test_conflict_day_unavailability,
        test_conflict_shift_unavailability,
        test_conflict_weekday_availability,
        test_conflict_vacation,
        test_conflict_skill_mismatch,
        test_conflict_max_consecutive,
        test_conflict_max_weekly,
        test_conflict_one_shift_per_day,
        test_conflict_max_night_shifts,
        test_conflict_nonexistent_shift,
        test_conflict_already_occupied,
        test_valid_preassignment_no_false_positive,
        test_valid_with_availability,
        test_multiple_conflicts,
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
            print(f"  ✗ ERROR: {e}\n")
            failed += 1
    
    print("="*70)
    print(f"RESULTS: {passed} passed, {failed} failed out of {len(tests)}")
    print("="*70)
    
    if failed == 0:
        print("""
  ✓ All conflict types are correctly detected:
    - Day unavailability
    - Shift unavailability  
    - Weekday availability
    - Vacation periods
    - Skill mismatch
    - Max consecutive days
    - Max weekly cap
    - One shift per day
    - Max night shifts
    - Non-existent shifts
    - Already-occupied slots
  
  ✓ Valid pre-assignments are NOT flagged as conflicts (no false positives)
  ✓ Multiple conflicts are reported together
  ✓ Clear, diagnostic error messages

  The bug is FIXED: pre-assignment/availability conflicts are now detected
  upfront with clear reasons, not silently dropped.
""")


if __name__ == "__main__":
    main()
