"""
Availability extension for the NRP solver.

Adds per-nurse availability constraints:
  - Day unavailability (specific days off)
  - Shift unavailability (can't do certain shift types, e.g., nights)
  - Partial-week availability (only works certain weekdays)
  - Date-range unavailability (vacation periods)

All of these are per-agent feasibility constraints, fitting naturally
into is_feasible_for alongside the skill check.

KEY THEORETICAL QUESTION: Does the spread bound survive availability?

  Availability restricts which nurses can take which shifts — exactly
  like skill mix. The "least-loaded feasible agent" search excludes
  unavailable nurses. When the global least-loaded is unavailable,
  we fall back to relaxed placement (EF2 or structural-limit behavior).

  So availability is analogous to skill mix: EF1 holds when structurally
  possible (enough available nurses with the right distribution), and
  the algorithm achieves the best possible spread otherwise.

  This is the honest result: availability can make EF1 structurally
  impossible (e.g., if only 1 nurse is available for a shift that
  needs 2 nurses, no algorithm can cover it).
"""

import time
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

# Import the base module
import sys
sys.path.insert(0, '/home/z/my-project/scripts')
from nrp_solver import NRPInstance, NRPSolver, NRPResult, InfeasibilityDetector, DWECBackend


class AvailabilityNRPInstance(NRPInstance):
    """NRP instance with per-nurse availability constraints."""
    
    def __init__(self, num_days: int, shifts_per_day: int, num_nurses: int,
                 coverage: Dict[Tuple[int, int], List[int]],
                 nurse_skills: List[int],
                 max_consecutive: int = 5,
                 max_weekly: int = 5,
                 weights="unit",
                 # Availability parameters:
                 unavailable_days: Optional[Dict[int, Set[int]]] = None,
                 unavailable_shifts: Optional[Dict[int, Set[int]]] = None,
                 available_weekdays: Optional[Dict[int, Set[int]]] = None,
                 vacation_periods: Optional[Dict[int, List[Tuple[int, int]]]] = None,
                 max_night_shifts: Optional[Dict[int, int]] = None):
        """
        Availability parameters (all optional, all per-nurse):
        
        unavailable_days: {nurse_idx: set of day indices they can't work}
            e.g., {0: {2, 4}} means nurse 0 can't work days 2 and 4
            
        unavailable_shifts: {nurse_idx: set of shift indices they can't work}
            e.g., {0: {1}} means nurse 0 can't work shift 1 (nights)
            
        available_weekdays: {nurse_idx: set of weekday indices (0=Mon..6=Sun) they CAN work}
            e.g., {0: {0, 2, 4}} means nurse 0 only works Mon/Wed/Fri
            If not specified, all weekdays are available.
            
        vacation_periods: {nurse_idx: list of (start_day, end_day) ranges they can't work}
            e.g., {0: [(7, 13)]} means nurse 0 on vacation week 2 (days 7-13)
            
        max_night_shifts: {nurse_idx: max night shifts (shift index 1) per planning period}
            e.g., {0: 3} means nurse 0 can work at most 3 night shifts total
        """
        super().__init__(num_days, shifts_per_day, num_nurses, coverage,
                        nurse_skills, max_consecutive, max_weekly, weights)
        
        self.unavailable_days = unavailable_days or {}
        self.unavailable_shifts = unavailable_shifts or {}
        self.available_weekdays = available_weekdays or {}
        self.vacation_periods = vacation_periods or {}
        self.max_night_shifts = max_night_shifts or {}
    
    def is_feasible_for(self, nurse_idx: int, bundle: Set) -> bool:
        """Check if bundle is feasible for nurse nurse_idx, including availability."""
        bundle = set(bundle)
        
        # === Base checks (inherited) ===
        # Weekly cap
        for week_start in range(0, self.num_days, 7):
            week_end = min(week_start + 7, self.num_days)
            count = sum(1 for (d, s, ci, sk) in bundle if week_start <= d < week_end)
            if count > self.max_weekly:
                return False
        
        # Consecutive days
        days = sorted(set(d for d, s, ci, sk in bundle))
        run = 1
        for i in range(1, len(days)):
            if days[i] == days[i-1] + 1:
                run += 1
                if run > self.max_consecutive:
                    return False
            else:
                run = 1
        
        # One shift per day
        days_with_shifts = defaultdict(set)
        for (d, s, ci, sk) in bundle:
            days_with_shifts[d].add(s)
        for d, shifts in days_with_shifts.items():
            if len(shifts) > 1 and self.shifts_per_day > 1:
                return False
        
        # Skill check
        nurse_skill = self.nurse_skills[nurse_idx]
        for (d, s, ci, req_skill) in bundle:
            if nurse_skill < req_skill:
                return False
        
        # === Availability checks (new) ===
        
        # Day unavailability
        if nurse_idx in self.unavailable_days:
            for (d, s, ci, sk) in bundle:
                if d in self.unavailable_days[nurse_idx]:
                    return False
        
        # Shift unavailability
        if nurse_idx in self.unavailable_shifts:
            for (d, s, ci, sk) in bundle:
                if s in self.unavailable_shifts[nurse_idx]:
                    return False
        
        # Weekday availability (only certain weekdays)
        if nurse_idx in self.available_weekdays:
            allowed_weekdays = self.available_weekdays[nurse_idx]
            for (d, s, ci, sk) in bundle:
                weekday = d % 7
                if weekday not in allowed_weekdays:
                    return False
        
        # Vacation periods
        if nurse_idx in self.vacation_periods:
            for (d, s, ci, sk) in bundle:
                for (start, end) in self.vacation_periods[nurse_idx]:
                    if start <= d <= end:
                        return False
        
        # Max night shifts
        if nurse_idx in self.max_night_shifts:
            night_count = sum(1 for (d, s, ci, sk) in bundle if s == 1)
            if night_count > self.max_night_shifts[nurse_idx]:
                return False
        
        return True


class AvailabilityInfeasibilityDetector(InfeasibilityDetector):
    """Extended infeasibility detection with availability."""
    
    @staticmethod
    def check(instance: AvailabilityNRPInstance) -> Tuple[bool, str]:
        # First run base checks
        feasible, reason = InfeasibilityDetector.check(instance)
        if not feasible:
            return False, reason
        
        n = instance.num_nurses
        
        # Check: for each (day, shift), enough available nurses with required skills
        for d in range(instance.num_days):
            for s in range(instance.shifts_per_day):
                if (d, s) not in instance.coverage:
                    continue
                req = instance.coverage[(d, s)]
                weekday = d % 7
                
                for req_sk in set(req):
                    count_needed = sum(1 for r in req if r == req_sk)
                    # Count nurses who: have skill, are available on this day/shift
                    count_available = 0
                    for i in range(n):
                        if instance.nurse_skills[i] < req_sk:
                            continue
                        if i in instance.unavailable_days and d in instance.unavailable_days[i]:
                            continue
                        if i in instance.unavailable_shifts and s in instance.unavailable_shifts[i]:
                            continue
                        if i in instance.available_weekdays and weekday not in instance.available_weekdays[i]:
                            continue
                        if i in instance.vacation_periods:
                            on_vacation = any(start <= d <= end 
                                            for start, end in instance.vacation_periods[i])
                            if on_vacation:
                                continue
                        count_available += 1
                    
                    if count_available < count_needed:
                        return False, (f"Day {d} shift {s} needs {count_needed} nurses with "
                                      f"skill {req_sk}, but only {count_available} are "
                                      f"available (considering availability constraints)")
        
        return True, ""


class AvailabilityDWECBackend(DWECBackend):
    """DWEC backend that uses availability-aware infeasibility detection."""
    
    def solve(self, instance: AvailabilityNRPInstance) -> NRPResult:
        # The DWEC algorithm uses instance.is_feasible_for(), which already
        # includes availability checks. So the base algorithm works unchanged.
        # We just need to use the availability-aware infeasibility detector.
        return super().solve(instance)


class AvailabilityNRPSolver:
    """Solver for NRP with availability constraints."""
    
    def __init__(self, backend: str = "dwec", ilp_time_limit: int = 60):
        self.backend_name = backend
        self.ilp_time_limit = ilp_time_limit
    
    def solve(self, instance: AvailabilityNRPInstance) -> NRPResult:
        # Availability-aware infeasibility check
        feasible, reason = AvailabilityInfeasibilityDetector.check(instance)
        if not feasible:
            return NRPResult(feasible=False, reason=reason, method="infeasibility_check")
        
        if self.backend_name == "dwec":
            return AvailabilityDWECBackend().solve(instance)
        elif self.backend_name == "ilp":
            from nrp_solver import ILPBackend
            return ILPBackend(self.ilp_time_limit).solve(instance)
        else:
            raise ValueError(f"Unknown backend: {self.backend_name}")


def solve_nrp_with_availability(num_days, shifts_per_day, num_nurses,
                                 coverage, nurse_skills,
                                 max_consecutive=5, max_weekly=5,
                                 weights="unit",
                                 unavailable_days=None,
                                 unavailable_shifts=None,
                                 available_weekdays=None,
                                 vacation_periods=None,
                                 max_night_shifts=None,
                                 backend="dwec"):
    """One-shot solver with availability."""
    instance = AvailabilityNRPInstance(
        num_days, shifts_per_day, num_nurses, coverage, nurse_skills,
        max_consecutive, max_weekly, weights,
        unavailable_days, unavailable_shifts, available_weekdays,
        vacation_periods, max_night_shifts
    )
    solver = AvailabilityNRPSolver(backend=backend)
    return solver.solve(instance)


# ============================================================
# Tests
# ============================================================

def test_basic_availability():
    """Test basic availability scenarios."""
    print("="*70)
    print("AVAILABILITY TESTS: Basic Scenarios")
    print("="*70)
    
    print("\n--- Test 1: One nurse can't work day 3 ---")
    result = solve_nrp_with_availability(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5,
        max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}}  # nurse 0 can't work day 3
    )
    print(f"  Result: {result}")
    if result.feasible:
        # Verify nurse 0 doesn't work day 3
        for (d, s, ci, sk) in result.allocation[0]:
            if d == 3:
                print(f"  BUG: nurse 0 assigned day 3!")
        print(f"  Nurse 0 bundle: {result.allocation[0]}")
        print(f"  Loads: {result.loads}")
    
    print("\n--- Test 2: Nurse 0 can't work nights (shift 1) ---")
    result = solve_nrp_with_availability(
        num_days=7, shifts_per_day=2, num_nurses=7,
        coverage={(d, s): [0] for d in range(7) for s in range(2)},
        nurse_skills=[0]*7,
        max_consecutive=5, max_weekly=5,
        weights="day_night_weekend",
        unavailable_shifts={0: {1}}  # nurse 0 can't work shift 1 (nights)
    )
    print(f"  Result: {result}")
    if result.feasible:
        # Verify nurse 0 doesn't work nights
        for (d, s, ci, sk) in result.allocation[0]:
            if s == 1:
                print(f"  BUG: nurse 0 assigned night shift!")
        night_shifts = sum(1 for (d, s, ci, sk) in result.allocation[0] if s == 1)
        print(f"  Nurse 0 night shifts: {night_shifts} (should be 0)")
        print(f"  Loads: {result.loads}")
    
    print("\n--- Test 3: Nurse 0 part-time (Mon/Wed/Fri only) ---")
    result = solve_nrp_with_availability(
        num_days=14, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0] for d in range(14)},
        nurse_skills=[0]*7,
        max_consecutive=5, max_weekly=5,
        weights="unit",
        available_weekdays={0: {0, 2, 4}}  # nurse 0 only Mon(0)/Wed(2)/Fri(4)
    )
    print(f"  Result: {result}")
    if result.feasible:
        # Verify nurse 0 only works Mon/Wed/Fri
        for (d, s, ci, sk) in result.allocation[0]:
            weekday = d % 7
            if weekday not in {0, 2, 4}:
                print(f"  BUG: nurse 0 works day {d} (weekday {weekday})")
        days_worked = sorted(set(d for (d, s, ci, sk) in result.allocation[0]))
        weekdays_worked = sorted(set(d % 7 for d in days_worked))
        print(f"  Nurse 0 weekdays worked: {weekdays_worked} (should be subset of [0,2,4])")
        print(f"  Loads: {result.loads}")
    
    print("\n--- Test 4: Nurse 0 on vacation week 2 (days 7-13) ---")
    result = solve_nrp_with_availability(
        num_days=14, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0] for d in range(14)},
        nurse_skills=[0]*7,
        max_consecutive=5, max_weekly=5,
        weights="unit",
        vacation_periods={0: [(7, 13)]}  # nurse 0 on vacation days 7-13
    )
    print(f"  Result: {result}")
    if result.feasible:
        # Verify nurse 0 doesn't work days 7-13
        for (d, s, ci, sk) in result.allocation[0]:
            if 7 <= d <= 13:
                print(f"  BUG: nurse 0 works during vacation (day {d})!")
        days_worked = sorted(set(d for (d, s, ci, sk) in result.allocation[0]))
        print(f"  Nurse 0 days worked: {days_worked}")
        print(f"  Loads: {result.loads}")


def test_combined_availability():
    """Test multiple availability constraints on the same nurse."""
    print("\n" + "="*70)
    print("AVAILABILITY TESTS: Combined Constraints")
    print("="*70)
    
    print("\n--- Test 5: Nurse 0 part-time + no nights + max 3 nights ---")
    # Wait, no nights means max_night_shifts is moot. Let me do:
    # Nurse 0: Mon/Wed/Fri only, AND max 2 shifts total
    # Actually max_night_shifts is about night shifts. Let me use a different combo.
    
    # Nurse 0: Mon/Wed/Fri only, no nights
    # Nurse 1: no Mondays, max 3 night shifts
    # Nurse 2: vacation days 10-14
    result = solve_nrp_with_availability(
        num_days=14, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [0] for d in range(14) for s in range(2)},
        nurse_skills=[0]*10,
        max_consecutive=5, max_weekly=5,
        weights="day_night_weekend",
        available_weekdays={0: {0, 2, 4}},  # nurse 0: Mon/Wed/Fri
        unavailable_shifts={0: {1}},  # nurse 0: no nights
        unavailable_days={1: {0, 7}},  # nurse 1: no Mondays (day 0 and 7)
        max_night_shifts={1: 3},  # nurse 1: max 3 nights
        vacation_periods={2: [(10, 14)]}  # nurse 2: vacation days 10-14
    )
    print(f"  Result: {result}")
    if result.feasible:
        print(f"  Loads: {result.loads}")
        # Verify constraints
        for i in range(3):
            bundle = result.allocation[i]
            days = set(d for (d, s, ci, sk) in bundle)
            shifts = set(s for (d, s, ci, sk) in bundle)
            nights = sum(1 for (d, s, ci, sk) in bundle if s == 1)
            print(f"  Nurse {i}: days={sorted(days)}, shifts={shifts}, nights={nights}")
        
        # Check nurse 0
        for (d, s, ci, sk) in result.allocation[0]:
            if d % 7 not in {0, 2, 4}:
                print(f"  BUG: nurse 0 works wrong weekday (day {d})")
            if s == 1:
                print(f"  BUG: nurse 0 works night (day {d})")
        
        # Check nurse 1
        for (d, s, ci, sk) in result.allocation[1]:
            if d % 7 == 0:
                print(f"  BUG: nurse 1 works Monday (day {d})")
        nights_1 = sum(1 for (d, s, ci, sk) in result.allocation[1] if s == 1)
        if nights_1 > 3:
            print(f"  BUG: nurse 1 has {nights_1} nights (> 3)")
        
        # Check nurse 2
        for (d, s, ci, sk) in result.allocation[2]:
            if 10 <= d <= 14:
                print(f"  BUG: nurse 2 works during vacation (day {d})")


def test_infeasibility_with_availability():
    """Test that infeasibility from availability is detected."""
    print("\n" + "="*70)
    print("AVAILABILITY TESTS: Infeasibility Detection")
    print("="*70)
    
    print("\n--- Test 6: Not enough available nurses for a shift ---")
    # 7 days, 1 shift, need 2 nurses per shift, but only 2 nurses total
    # and one is unavailable on day 3
    result = solve_nrp_with_availability(
        num_days=7, shifts_per_day=1, num_nurses=3,
        coverage={(d, 0): [0, 0] for d in range(7)},  # 2 nurses per shift
        nurse_skills=[0]*3,
        max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}}  # nurse 0 unavailable day 3
    )
    # Day 3 needs 2 nurses, only 2 available (nurses 1 and 2). Should be feasible.
    print(f"  Result: {result}")
    
    print("\n--- Test 7: Truly infeasible - not enough available ---")
    # 7 days, 1 shift, need 2 nurses per shift, 2 nurses total
    # One nurse unavailable on day 3 → only 1 available → infeasible
    result = solve_nrp_with_availability(
        num_days=7, shifts_per_day=1, num_nurses=2,
        coverage={(d, 0): [0, 0] for d in range(7)},
        nurse_skills=[0]*2,
        max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}}
    )
    print(f"  Result: {result}")
    print(f"  Reason: {result.reason}")
    
    print("\n--- Test 8: Infeasible - skill + availability ---")
    # Need 1 senior per shift, only 1 senior, but senior unavailable day 3
    result = solve_nrp_with_availability(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [1, 0] for d in range(7)},  # 1 senior + 1 junior
        nurse_skills=[1, 0, 0, 0, 0],  # 1 senior
        max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}}  # senior unavailable day 3
    )
    print(f"  Result: {result}")
    print(f"  Reason: {result.reason}")


def test_realistic_scenario():
    """Test a realistic operational scenario with mixed availability."""
    print("\n" + "="*70)
    print("AVAILABILITY TESTS: Realistic Scenario")
    print("="*70)
    
    print("""
  Scenario: 2-week hospital ward
  - 14 days, 2 shifts/day (day/night)
  - 10 nurses: 4 senior, 6 junior
  - Coverage: 1 senior + 1 junior per shift (28 senior slots, 28 junior slots)
  - Availability:
    * Nurse 0 (senior): part-time Mon-Wed only
    * Nurse 1 (senior): no nights
    * Nurse 2 (senior): vacation days 10-13
    * Nurse 5 (junior): no weekends
    * Nurse 6 (junior): max 2 nights per period
    """)
    
    instance = AvailabilityNRPInstance(
        num_days=14, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
        nurse_skills=[1, 1, 1, 1, 0, 0, 0, 0, 0, 0],  # 4 senior, 6 junior
        max_consecutive=5, max_weekly=10,
        weights="day_night_weekend",
        # Availability:
        available_weekdays={0: {0, 1, 2}},  # nurse 0: Mon-Wed
        unavailable_shifts={1: {1}},  # nurse 1: no nights
        vacation_periods={2: [(10, 13)]},  # nurse 2: vacation
        unavailable_days={5: {5, 6, 12, 13}},  # nurse 5: no weekends (days 5,6,12,13)
        max_night_shifts={6: 2},  # nurse 6: max 2 nights
    )
    solver = AvailabilityNRPSolver(backend="dwec")
    result = solver.solve(instance)
    
    print(f"  Result: {result}")
    if result.feasible:
        w_max = max(instance.weights.values())
        print(f"  Spread: {result.spread:.2f}, w_max: {w_max:.2f}, EF1: {result.ef1}")
        print(f"  Coverage OK: {result.coverage_ok}")
        print(f"  Solve time: {result.solve_time:.3f}s")
        print(f"  Loads: {[round(l,1) for l in result.loads]}")
        
        # Verify all availability constraints
        violations = []
        for i, bundle in enumerate(result.allocation):
            for (d, s, ci, sk) in bundle:
                # Nurse 0: Mon-Wed only
                if i == 0 and d % 7 not in {0, 1, 2}:
                    violations.append(f"Nurse 0 works day {d} (weekday {d%7})")
                # Nurse 1: no nights
                if i == 1 and s == 1:
                    violations.append(f"Nurse 1 works night (day {d})")
                # Nurse 2: vacation days 10-13
                if i == 2 and 10 <= d <= 13:
                    violations.append(f"Nurse 2 works during vacation (day {d})")
                # Nurse 5: no weekends
                if i == 5 and d % 7 >= 5:
                    violations.append(f"Nurse 5 works weekend (day {d})")
        
        # Nurse 6: max 2 nights
        nights_6 = sum(1 for (d, s, ci, sk) in result.allocation[6] if s == 1)
        if nights_6 > 2:
            violations.append(f"Nurse 6 has {nights_6} nights (> 2)")
        
        if violations:
            print(f"\n  AVAILABILITY VIOLATIONS ({len(violations)}):")
            for v in violations[:10]:
                print(f"    {v}")
        else:
            print(f"\n  ✓ All availability constraints satisfied!")
        
        # Show per-nurse summary
        print(f"\n  Per-nurse summary:")
        for i, bundle in enumerate(result.allocation):
            sk = "S" if i < 4 else "J"
            days = sorted(set(d for (d, s, ci, ssk) in bundle))
            nights = sum(1 for (d, s, ci, ssk) in bundle if s == 1)
            print(f"    Nurse {i} ({sk}): {len(bundle)} shifts, {nights} nights, "
                  f"load {result.loads[i]:.1f}, days {days}")


def main():
    test_basic_availability()
    test_combined_availability()
    test_infeasibility_with_availability()
    test_realistic_scenario()
    
    print("\n" + "="*70)
    print("AVAILABILITY EXTENSION SUMMARY")
    print("="*70)
    print("""
    The availability extension adds 5 types of per-nurse constraints:
    1. Day unavailability (specific days off)
    2. Shift unavailability (can't do certain shift types)
    3. Weekday availability (only works certain weekdays)
    4. Vacation periods (date ranges off)
    5. Max night shifts (cap on night shifts per period)
    
    All fit naturally into is_feasible_for as per-agent constraints.
    The DWEC algorithm handles them via the same feasible-agent filtering
    used for skill mix.
    
    The spread bound behaves as with skill mix:
    - EF1 when structurally possible (enough available nurses)
    - Best achievable spread otherwise
    - Infeasibility detected upfront when coverage can't be met
    """)


if __name__ == "__main__":
    main()
