"""
Three new features for the NRP solver:

1. MULTI-SCHEDULE MODE
   Returns N diverse schedules by varying the good processing order.
   Each schedule is valid (feasible + EF1 when possible).
   Diverse via: different weight orderings, different tie-breaking.
   Not exhaustive — a sample of valid schedules.

2. PRE-PROCESSING: COUNT OF VALID OUTCOMES
   - Fast feasibility check: does ANY solution exist? (milliseconds)
   - Upper bound on count: rough estimate via capacity analysis
   - Exact count: exhaustive enumeration (only for tiny instances, m <= ~12)
   - Honest guidance: "instance is small enough to enumerate" vs "too large"

3. PRE-ASSIGNMENT
   Fix specific shifts to specific nurses before solving.
   Implemented as: the nurse's bundle starts with the pre-assigned shifts,
   and other nurses are forbidden from taking those shifts.
   The solver then allocates the remaining shifts normally.
"""

import time
import random
from itertools import product, combinations
from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional

from .availability import (
    AvailabilityNRPInstance, AvailabilityNRPSolver, solve_nrp_with_availability,
    AvailabilityInfeasibilityDetector
)
from .core import NRPResult, DWECBackend, InfeasibilityDetector


# ============================================================
# FEATURE 1: MULTI-SCHEDULE MODE
# ============================================================

class MultiScheduleSolver:
    """Returns multiple diverse schedules by varying good ordering."""
    
    def __init__(self, num_schedules: int = 5, seed: int = 42,
                 backend: str = "dwec", ilp_time_limit: int = 60):
        self.num_schedules = num_schedules
        self.seed = seed
        self.backend = backend
        self.ilp_time_limit = ilp_time_limit
    
    def solve(self, instance: AvailabilityNRPInstance) -> List[NRPResult]:
        """Return up to num_schedules diverse schedules."""
        # First check feasibility
        feasible, reason = AvailabilityInfeasibilityDetector.check(instance)
        if not feasible:
            return [NRPResult(feasible=False, reason=reason, method="infeasibility_check")]
        
        results = []
        seen_allocations = set()
        
        # Strategy 1: Default ordering (decreasing weight, decreasing skill)
        result = AvailabilityNRPSolver(backend=self.backend,
                                       ilp_time_limit=self.ilp_time_limit).solve(instance)
        if result.feasible:
            key = self._alloc_key(result.allocation)
            if key not in seen_allocations:
                results.append(result)
                seen_allocations.add(key)
        
        # Strategy 2-N: Vary the good ordering
        rng = random.Random(self.seed)
        
        for i in range(1, self.num_schedules):
            # Create a varied ordering
            ordering_strategy = i % 4
            
            if ordering_strategy == 0:
                # Random shuffle of goods
                goods = list(instance.goods)
                rng.shuffle(goods)
            elif ordering_strategy == 1:
                # Increasing weight (reverse of default)
                goods = sorted(instance.goods,
                             key=lambda g: (instance.weights[g], g[3]))
            elif ordering_strategy == 2:
                # Sort by skill requirement first, then weight
                goods = sorted(instance.goods,
                             key=lambda g: (g[3], -instance.weights[g]))
            else:
                # Random with weight bias
                goods = sorted(instance.goods, key=lambda g: -instance.weights[g])
                # Swap some adjacent goods
                for _ in range(len(goods) // 4):
                    j = rng.randint(0, len(goods) - 2)
                    goods[j], goods[j+1] = goods[j+1], goods[j]
            
            # Solve with this ordering
            result = self._solve_with_ordering(instance, goods)
            if result and result.feasible:
                key = self._alloc_key(result.allocation)
                if key not in seen_allocations:
                    results.append(result)
                    seen_allocations.add(key)
            
            if len(results) >= self.num_schedules:
                break
        
        return results
    
    def _alloc_key(self, allocation: List[Set]) -> Tuple:
        """Create a hashable key for an allocation (for dedup)."""
        return tuple(frozenset(b) for b in allocation)
    
    def _solve_with_ordering(self, instance: AvailabilityNRPInstance,
                            goods_order: List) -> Optional[NRPResult]:
        """Solve with a specific good ordering."""
        n = instance.num_nurses
        weights = instance.weights
        w_max = instance.w_max
        
        pi = [set() for _ in range(n)]
        loads = [0.0] * n
        leftover = []
        shift_coverage = defaultdict(set)
        
        for s_good in goods_order:
            d, s, ci, req_skill = s_good
            min_load = min(loads)
            k = min(range(n), key=lambda i: loads[i])
            
            if (instance.nurse_skills[k] >= req_skill and
                instance.is_feasible_for(k, pi[k] | {s_good})):
                pi[k] = pi[k] | {s_good}
                loads[k] += weights[s_good]
                shift_coverage[(d, s)].add(ci)
                continue
            
            # Ejection
            ejection_found = False
            agents_by_load = sorted(range(n), key=lambda i: -loads[i])
            for j in agents_by_load:
                if abs(loads[j] - min_load) < 1e-9:
                    continue
                if instance.nurse_skills[j] < req_skill:
                    continue
                ejectable = []
                for t in pi[j]:
                    if weights[t] >= weights[s_good] - 1e-9:
                        new_j = (pi[j] - {t}) | {s_good}
                        if instance.is_feasible_for(j, new_j):
                            t_req_skill = t[3]
                            if instance.nurse_skills[k] >= t_req_skill:
                                if instance.is_feasible_for(k, pi[k] | {t}):
                                    if loads[j] - min_load >= weights[t] - weights[s_good] - 1e-9:
                                        ejectable.append(t)
                if ejectable:
                    t = min(ejectable, key=lambda x: weights[x])
                    pi[j] = (pi[j] - {t}) | {s_good}
                    loads[j] += weights[s_good] - weights[t]
                    pi[k] = pi[k] | {t}
                    loads[k] += weights[t]
                    shift_coverage[(d, s)].add(ci)
                    ejection_found = True
                    break
            
            if ejection_found:
                continue

            # Defer to leftover (no relaxed placement — it violates the spread bound)
            leftover.append(s_good)
        
        # Place leftover: only at global least-loaded (maintains spread bound)
        for s_good in leftover:
            d, s, ci, req_skill = s_good
            k = min(range(n), key=lambda i: loads[i])
            if (instance.nurse_skills[k] >= req_skill and
                instance.is_feasible_for(k, pi[k] | {s_good})):
                pi[k] = pi[k] | {s_good}
                loads[k] += weights[s_good]
                shift_coverage[(d, s)].add(ci)
        
        coverage_ok = all(
            len(shift_coverage[(d, s)]) == len(reqs)
            for (d, s), reqs in instance.coverage.items()
        )
        all_feasible = all(instance.is_feasible_for(i, b) for i, b in enumerate(pi))
        spread = max(loads) - min(loads) if loads else 0
        
        return NRPResult(
            feasible=coverage_ok and all_feasible,
            allocation=pi, loads=loads, spread=spread,
            ef1=spread <= w_max + 1e-9,
            coverage_ok=coverage_ok,
            method="dwec_multi"
        )


def solve_multiple_schedules(num_days, shifts_per_day, num_nurses,
                              coverage, nurse_skills,
                              max_consecutive=5, max_weekly=5,
                              weights="unit",
                              unavailable_days=None, unavailable_shifts=None,
                              available_weekdays=None, vacation_periods=None,
                              max_night_shifts=None,
                              pre_assignments=None,
                              num_schedules=5, seed=42):
    """One-shot multi-schedule solver."""
    instance = PreAssignmentNRPInstance(
        num_days, shifts_per_day, num_nurses, coverage, nurse_skills,
        max_consecutive, max_weekly, weights,
        unavailable_days, unavailable_shifts, available_weekdays,
        vacation_periods, max_night_shifts, pre_assignments
    )
    solver = MultiScheduleSolver(num_schedules=num_schedules, seed=seed)
    return solver.solve(instance)


# ============================================================
# FEATURE 2: PRE-PROCESSING — COUNT OF VALID OUTCOMES
# ============================================================

class OutcomeCounter:
    """Count or estimate the number of valid schedules."""
    
    @staticmethod
    def analyze(instance: AvailabilityNRPInstance) -> Dict:
        """
        Returns analysis of the solution space:
        - feasible: does any solution exist?
        - exact_count: exact number of feasible schedules (if small enough)
        - ef1_count: exact number of EF1 schedules (if small enough)
        - upper_bound: rough upper bound on count
        - enumerable: is exact counting feasible?
        - recommendation: guidance on whether to enumerate
        """
        # AvailabilityInfeasibilityDetector is already imported at module level
        
        result = {
            "feasible": False,
            "exact_count": None,
            "ef1_count": None,
            "upper_bound": None,
            "enumerable": False,
            "recommendation": "",
            "analysis_time": 0.0
        }
        
        t0 = time.time()
        
        # Step 1: Feasibility check
        feasible, reason = AvailabilityInfeasibilityDetector.check(instance)
        result["feasible"] = feasible
        if not feasible:
            result["recommendation"] = f"Infeasible: {reason}"
            result["analysis_time"] = time.time() - t0
            return result
        
        n = instance.num_nurses
        m = instance.m
        w_max = instance.w_max
        
        # Step 2: Upper bound (crude)
        # Each slot can go to at most n nurses (with right skill).
        # Upper bound = product of (feasible nurses per slot).
        upper = 1
        for good in instance.goods:
            req_skill = good[3]
            d, s = good[0], good[1]
            feasible_nurses = sum(
                1 for i in range(n)
                if instance.nurse_skills[i] >= req_skill and
                instance._nurse_available_for(i, d, s)
            )
            upper *= max(feasible_nurses, 1)
        result["upper_bound"] = upper
        
        # Step 3: Can we enumerate exactly?
        # Exhaustive enumeration is n^m. Feasible if n^m <= 10^7.
        total_assignments = n ** m
        result["enumerable"] = total_assignments <= 10_000_000
        
        if result["enumerable"]:
            # Exact count
            exact_count, ef1_count = OutcomeCounter._enumerate_exact(instance)
            result["exact_count"] = exact_count
            result["ef1_count"] = ef1_count
            
            if ef1_count == 0:
                result["recommendation"] = (
                    f"No EF1 schedules exist (though {exact_count} feasible schedules do). "
                    f"Use min-spread solver instead."
                )
            elif ef1_count <= 100:
                result["recommendation"] = (
                    f"{ef1_count} EF1 schedules exist. "
                    f"Small enough to enumerate all if needed."
                )
            elif ef1_count <= 10000:
                result["recommendation"] = (
                    f"{ef1_count} EF1 schedules exist. "
                    f"Enumerable but may be slow. Consider sampling."
                )
            else:
                result["recommendation"] = (
                    f"{ef1_count} EF1 schedules exist. "
                    f"Too many to enumerate practically. Use multi-schedule sampling."
                )
        else:
            result["recommendation"] = (
                f"Instance too large to enumerate exactly ({n}^{m} = {total_assignments:.2e} assignments). "
                f"Upper bound on feasible schedules: {upper:.2e}. "
                f"Use multi-schedule mode to sample valid schedules."
            )
        
        result["analysis_time"] = time.time() - t0
        return result
    
    @staticmethod
    def _enumerate_exact(instance: AvailabilityNRPInstance) -> Tuple[int, int]:
        """Exact enumeration. Only for small instances."""
        n = instance.num_nurses
        goods = instance.goods
        m = len(goods)
        w_max = instance.w_max
        
        feasible_count = 0
        ef1_count = 0
        
        for assignment in product(range(n), repeat=m):
            pi = [set() for _ in range(n)]
            for j, a in enumerate(assignment):
                pi[a].add(goods[j])
            
            # Check feasibility
            if not all(instance.is_feasible_for(i, b) for i, b in enumerate(pi)):
                continue
            
            # Check coverage (each slot assigned to exactly one nurse, distinct nurses per shift)
            shift_nurses = defaultdict(set)
            for i, b in enumerate(pi):
                for (d, s, ci, sk) in b:
                    if ci in shift_nurses[(d, s)]:
                        break  # duplicate
                    shift_nurses[(d, s)].add(ci)
            if any(len(shift_nurses[(d, s)]) != len(reqs)
                   for (d, s), reqs in instance.coverage.items()):
                continue
            
            feasible_count += 1
            
            # Check EF1
            loads = [sum(instance.weights[g] for g in b) for b in pi]
            spread = max(loads) - min(loads)
            if spread <= w_max + 1e-9:
                ef1_count += 1
        
        return feasible_count, ef1_count


def count_possible_outcomes(num_days, shifts_per_day, num_nurses,
                             coverage, nurse_skills,
                             max_consecutive=5, max_weekly=5,
                             weights="unit",
                             unavailable_days=None, unavailable_shifts=None,
                             available_weekdays=None, vacation_periods=None,
                             max_night_shifts=None,
                             pre_assignments=None):
    """One-shot outcome counter."""
    instance = PreAssignmentNRPInstance(
        num_days, shifts_per_day, num_nurses, coverage, nurse_skills,
        max_consecutive, max_weekly, weights,
        unavailable_days, unavailable_shifts, available_weekdays,
        vacation_periods, max_night_shifts, pre_assignments
    )
    return OutcomeCounter.analyze(instance)


# ============================================================
# FEATURE 3: PRE-ASSIGNMENT
# ============================================================

class PreAssignmentNRPInstance(AvailabilityNRPInstance):
    """NRP instance with pre-assigned shifts.
    
    pre_assignments: dict {nurse_idx: set of (day, shift) tuples}
    e.g., {0: {(0, 1), (3, 0)}} means nurse 0 is pre-assigned to
    day 0 shift 1 and day 3 shift 0.
    """
    
    def __init__(self, num_days, shifts_per_day, num_nurses,
                 coverage, nurse_skills,
                 max_consecutive=5, max_weekly=5, weights="unit",
                 unavailable_days=None, unavailable_shifts=None,
                 available_weekdays=None, vacation_periods=None,
                 max_night_shifts=None,
                 pre_assignments=None):
        super().__init__(num_days, shifts_per_day, num_nurses, coverage,
                        nurse_skills, max_consecutive, max_weekly, weights,
                        unavailable_days, unavailable_shifts, available_weekdays,
                        vacation_periods, max_night_shifts)
        
        self.pre_assignments = pre_assignments or {}
        
        # Build pre-assigned goods lookup
        # For each (day, shift) that's pre-assigned, mark which nurse gets it
        # and which coverage slot it fills.
        self.pre_assigned_goods = {}  # good -> nurse_idx
        self.pre_assigned_nurse_goods = defaultdict(set)  # nurse_idx -> set of goods
        self.pre_assignment_conflicts = []  # list of (nurse_idx, day, shift, reason)
        
        for nurse_idx, day_shifts in self.pre_assignments.items():
            for (d, s) in day_shifts:
                # Validate (d, s) exists in coverage
                if (d, s) not in coverage:
                    self.pre_assignment_conflicts.append(
                        (nurse_idx, d, s,
                         f"shift (day {d}, shift {s}) not in coverage"))
                    continue
                
                reqs = coverage[(d, s)]
                # Find the first unassigned coverage slot for this (day, shift)
                registered = False
                for ci in range(len(reqs)):
                    good = (d, s, ci, reqs[ci])
                    if good not in self.pre_assigned_goods:
                        # Check nurse can actually do this (skill, availability, etc.)
                        if self.is_feasible_for(nurse_idx, {good}):
                            self.pre_assigned_goods[good] = nurse_idx
                            self.pre_assigned_nurse_goods[nurse_idx].add(good)
                            registered = True
                            break
                        else:
                            # Diagnose WHY it's infeasible
                            reason = self._diagnose_preassignment_conflict(nurse_idx, good)
                            self.pre_assignment_conflicts.append(
                                (nurse_idx, d, s, reason))
                            registered = True  # mark to stop trying other slots
                            break
                if not registered:
                    # All slots for this (d, s) are already pre-assigned
                    self.pre_assignment_conflicts.append(
                        (nurse_idx, d, s,
                         f"all coverage slots for (day {d}, shift {s}) already pre-assigned"))
    
    def _diagnose_preassignment_conflict(self, nurse_idx: int, good) -> str:
        """Diagnose why a pre-assignment is infeasible for the nurse."""
        d, s, ci, req_skill = good
        nurse_skill = self.nurse_skills[nurse_idx]
        
        if nurse_skill < req_skill:
            return (f"nurse {nurse_idx} skill {nurse_skill} < required {req_skill} "
                    f"for (day {d}, shift {s})")
        
        if nurse_idx in self.unavailable_days and d in self.unavailable_days[nurse_idx]:
            return (f"nurse {nurse_idx} unavailable on day {d} "
                    f"(in unavailable_days)")
        
        if nurse_idx in self.unavailable_shifts and s in self.unavailable_shifts[nurse_idx]:
            return (f"nurse {nurse_idx} unavailable for shift {s} "
                    f"(in unavailable_shifts)")
        
        if nurse_idx in self.available_weekdays:
            allowed = self.available_weekdays[nurse_idx]
            weekday = d % 7
            if weekday not in allowed:
                return (f"nurse {nurse_idx} doesn't work weekday {weekday} "
                        f"(available_weekdays={allowed})")
        
        if nurse_idx in self.vacation_periods:
            for start, end in self.vacation_periods[nurse_idx]:
                if start <= d <= end:
                    return (f"nurse {nurse_idx} on vacation days {start}-{end} "
                            f"(includes day {d})")
        
        # Check against existing pre-assignments for this nurse
        existing = self.pre_assigned_nurse_goods[nurse_idx]
        if existing:
            # Check weekly cap
            for week_start in range(0, self.num_days, 7):
                week_end = min(week_start + 7, self.num_days)
                count = sum(1 for g in existing if week_start <= g[0] < week_end)
                if week_start <= d < week_end:
                    if count + 1 > self.max_weekly:
                        return (f"nurse {nurse_idx} would exceed max_weekly "
                                f"{self.max_weekly} in week containing day {d}")
            
            # Check consecutive days
            days = sorted(set(g[0] for g in existing) | {d})
            run = 1
            for i in range(1, len(days)):
                if days[i] == days[i-1] + 1:
                    run += 1
                    if run > self.max_consecutive:
                        return (f"nurse {nurse_idx} would exceed max_consecutive "
                                f"{self.max_consecutive} around day {d}")
                else:
                    run = 1
            
            # Check one shift per day
            days_with_shifts = defaultdict(set)
            for g in existing:
                days_with_shifts[g[0]].add(g[1])
            days_with_shifts[d].add(s)
            for dd, shifts in days_with_shifts.items():
                if len(shifts) > 1 and self.shifts_per_day > 1:
                    return (f"nurse {nurse_idx} would have multiple shifts on day {dd}")
            
            # Check max night shifts
            if nurse_idx in self.max_night_shifts and s == 1:
                night_count = sum(1 for g in existing if g[1] == 1)
                if night_count + 1 > self.max_night_shifts[nurse_idx]:
                    return (f"nurse {nurse_idx} would exceed max_night_shifts "
                            f"{self.max_night_shifts[nurse_idx]}")
        
        return f"nurse {nurse_idx} cannot take (day {d}, shift {s}) for unknown reason"
    
    def has_pre_assignment_conflicts(self) -> bool:
        """Returns True if any pre-assignment conflicts with constraints."""
        return len(self.pre_assignment_conflicts) > 0
    
    def get_pre_assignment_conflicts(self) -> List[Tuple]:
        """Returns list of (nurse_idx, day, shift, reason) for conflicting pre-assignments."""
        return self.pre_assignment_conflicts
    
    def is_feasible_for(self, nurse_idx: int, bundle: Set) -> bool:
        """Check feasibility, including that pre-assigned goods are respected."""
        bundle = set(bundle)
        
        # Base checks (inherited)
        if not super().is_feasible_for(nurse_idx, bundle):
            return False
        
        # Pre-assignment checks:
        # 1. If a good in bundle is pre-assigned to a DIFFERENT nurse, infeasible.
        for good in bundle:
            if good in self.pre_assigned_goods:
                if self.pre_assigned_goods[good] != nurse_idx:
                    return False
        
        # 2. If a good is pre-assigned to THIS nurse, it's fine (they must take it).
        # But we don't force inclusion here — that's handled by the solver
        # initializing bundles with pre-assigned goods.
        
        return True
    
    def _nurse_available_for(self, nurse_idx: int, day: int, shift: int) -> bool:
        """Check if nurse is available for a given day/shift (for counting)."""
        weekday = day % 7
        if nurse_idx in self.unavailable_days and day in self.unavailable_days[nurse_idx]:
            return False
        if nurse_idx in self.unavailable_shifts and shift in self.unavailable_shifts[nurse_idx]:
            return False
        if nurse_idx in self.available_weekdays and weekday not in self.available_weekdays[nurse_idx]:
            return False
        if nurse_idx in self.vacation_periods:
            for start, end in self.vacation_periods[nurse_idx]:
                if start <= day <= end:
                    return False
        return True


class PreAssignmentDWECBackend(DWECBackend):
    """DWEC backend that respects pre-assignments."""
    
    def solve(self, instance: PreAssignmentNRPInstance) -> NRPResult:
        t0 = time.time()
        n = instance.num_nurses
        weights = instance.weights
        w_max = instance.w_max
        
        # Initialize bundles with pre-assigned goods
        pi = [set() for _ in range(n)]
        loads = [0.0] * n
        shift_coverage = defaultdict(set)
        
        for nurse_idx, goods in instance.pre_assigned_nurse_goods.items():
            for good in goods:
                pi[nurse_idx].add(good)
                loads[nurse_idx] += weights[good]
                shift_coverage[(good[0], good[1])].add(good[2])
        
        # Remaining goods to assign
        remaining_goods = [g for g in instance.goods if g not in instance.pre_assigned_goods]
        
        # Sort remaining goods
        sorted_goods = sorted(remaining_goods,
                             key=lambda g: (-weights[g], -g[3]))
        
        leftover = []
        stats = {"direct": 0, "ejections": 0, "relaxed": 0, "deferred": 0,
                 "pre_assigned": len(instance.pre_assigned_goods)}
        
        for s_good in sorted_goods:
            d, s, ci, req_skill = s_good
            min_load = min(loads)
            k = min(range(n), key=lambda i: loads[i])
            
            if (instance.nurse_skills[k] >= req_skill and
                instance.is_feasible_for(k, pi[k] | {s_good})):
                pi[k] = pi[k] | {s_good}
                loads[k] += weights[s_good]
                shift_coverage[(d, s)].add(ci)
                stats["direct"] += 1
                continue
            
            # Ejection
            ejection_found = False
            agents_by_load = sorted(range(n), key=lambda i: -loads[i])
            for j in agents_by_load:
                if abs(loads[j] - min_load) < 1e-9:
                    continue
                if instance.nurse_skills[j] < req_skill:
                    continue
                ejectable = []
                for t in pi[j]:
                    # Can't eject pre-assigned goods
                    if t in instance.pre_assigned_goods:
                        continue
                    if weights[t] >= weights[s_good] - 1e-9:
                        new_j = (pi[j] - {t}) | {s_good}
                        if instance.is_feasible_for(j, new_j):
                            t_req_skill = t[3]
                            if instance.nurse_skills[k] >= t_req_skill:
                                if instance.is_feasible_for(k, pi[k] | {t}):
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

            # Defer to leftover (no relaxed placement — it violates the spread bound)
            leftover.append(s_good)
            stats["deferred"] += 1
        
        # Place leftover: only at global least-loaded (maintains spread bound)
        for s_good in leftover:
            d, s, ci, req_skill = s_good
            k = min(range(n), key=lambda i: loads[i])
            if (instance.nurse_skills[k] >= req_skill and
                instance.is_feasible_for(k, pi[k] | {s_good})):
                pi[k] = pi[k] | {s_good}
                loads[k] += weights[s_good]
                shift_coverage[(d, s)].add(ci)
        
        coverage_ok = all(
            len(shift_coverage[(d, s)]) == len(reqs)
            for (d, s), reqs in instance.coverage.items()
        )
        all_feasible = all(instance.is_feasible_for(i, b) for i, b in enumerate(pi))
        spread = max(loads) - min(loads) if loads else 0
        
        t1 = time.time()
        return NRPResult(
            feasible=coverage_ok and all_feasible,
            allocation=pi, loads=loads, spread=spread,
            ef1=spread <= w_max + 1e-9,
            coverage_ok=coverage_ok,
            method="dwec_preassign",
            solve_time=t1 - t0,
            stats=stats
        )


class PreAssignmentSolver:
    """Solver that handles pre-assignments."""
    
    def __init__(self, backend: str = "dwec", ilp_time_limit: int = 60):
        self.backend = backend
        self.ilp_time_limit = ilp_time_limit
    
    def solve(self, instance: PreAssignmentNRPInstance) -> NRPResult:
        feasible, reason = AvailabilityInfeasibilityDetector.check(instance)
        if not feasible:
            return NRPResult(feasible=False, reason=reason, method="infeasibility_check")
        
        # Check pre-assignment conflicts (NEW: detected during instance construction)
        if instance.has_pre_assignment_conflicts():
            conflicts = instance.get_pre_assignment_conflicts()
            conflict_descs = [f"Nurse {ni} → (day {d}, shift {s}): {reason}"
                            for ni, d, s, reason in conflicts]
            return NRPResult(
                feasible=False,
                reason="Pre-assignment conflicts detected:\n  " +
                       "\n  ".join(conflict_descs),
                method="pre_assignment_conflict_check"
            )
        
        # Check pre-assignments are valid as a set (in case of interaction effects)
        for nurse_idx, goods in instance.pre_assigned_nurse_goods.items():
            if not instance.is_feasible_for(nurse_idx, goods):
                return NRPResult(
                    feasible=False,
                    reason=f"Pre-assignment for nurse {nurse_idx} violates constraints: {goods}",
                    method="pre_assignment_check"
                )
        
        return PreAssignmentDWECBackend().solve(instance)


def solve_with_preassignment(num_days, shifts_per_day, num_nurses,
                              coverage, nurse_skills,
                              max_consecutive=5, max_weekly=5,
                              weights="unit",
                              unavailable_days=None, unavailable_shifts=None,
                              available_weekdays=None, vacation_periods=None,
                              max_night_shifts=None,
                              pre_assignments=None):
    """One-shot solver with pre-assignments."""
    instance = PreAssignmentNRPInstance(
        num_days, shifts_per_day, num_nurses, coverage, nurse_skills,
        max_consecutive, max_weekly, weights,
        unavailable_days, unavailable_shifts, available_weekdays,
        vacation_periods, max_night_shifts, pre_assignments
    )
    solver = PreAssignmentSolver()
    return solver.solve(instance)


# ============================================================
# TESTS
# ============================================================

def test_multi_schedule():
    """Test multi-schedule mode."""
    print("="*70)
    print("FEATURE 1: MULTI-SCHEDULE MODE")
    print("="*70)
    
    print("\n  Instance: 2 weeks, 1 shift/day, 7 nurses, no skills")
    results = solve_multiple_schedules(
        num_days=14, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0] for d in range(14)},
        nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
        weights="unit",
        num_schedules=5
    )
    
    print(f"  Got {len(results)} schedules:")
    for i, r in enumerate(results):
        if r.feasible:
            print(f"    Schedule {i+1}: spread={r.spread:.2f}, EF1={r.ef1}, "
                  f"loads={[round(l,1) for l in r.loads]}")
    
    # Verify diversity
    unique_allocs = set()
    for r in results:
        if r.feasible:
            key = tuple(frozenset(b) for b in r.allocation)
            unique_allocs.add(key)
    print(f"  Unique schedules: {len(unique_allocs)}")
    
    # Larger instance
    print("\n  Instance: 4 weeks, 2 shifts/day, 14 nurses, day/night weights")
    results = solve_multiple_schedules(
        num_days=28, shifts_per_day=2, num_nurses=14,
        coverage={(d, s): [0] for d in range(28) for s in range(2)},
        nurse_skills=[0]*14, max_consecutive=5, max_weekly=10,
        weights="day_night_weekend",
        num_schedules=5
    )
    print(f"  Got {len(results)} schedules:")
    for i, r in enumerate(results):
        if r.feasible:
            print(f"    Schedule {i+1}: spread={r.spread:.2f}, EF1={r.ef1}, "
                  f"time={r.solve_time:.3f}s")


def test_outcome_counter():
    """Test outcome counting."""
    print("\n" + "="*70)
    print("FEATURE 2: OUTCOME COUNTING")
    print("="*70)
    
    # Small instance (enumerable)
    print("\n  Small instance (7 days, 3 nurses, enumerable):")
    analysis = count_possible_outcomes(
        num_days=7, shifts_per_day=1, num_nurses=3,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*3, max_consecutive=5, max_weekly=5,
        weights="unit"
    )
    print(f"    Feasible: {analysis['feasible']}")
    print(f"    Enumerable: {analysis['enumerable']}")
    print(f"    Exact count: {analysis['exact_count']}")
    print(f"    EF1 count: {analysis['ef1_count']}")
    print(f"    Upper bound: {analysis['upper_bound']}")
    print(f"    Analysis time: {analysis['analysis_time']:.3f}s")
    print(f"    Recommendation: {analysis['recommendation']}")
    
    # Medium instance (not enumerable)
    print("\n  Medium instance (14 days, 5 nurses, NOT enumerable):")
    analysis = count_possible_outcomes(
        num_days=14, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(14)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit"
    )
    print(f"    Feasible: {analysis['feasible']}")
    print(f"    Enumerable: {analysis['enumerable']}")
    print(f"    Upper bound: {analysis['upper_bound']:.2e}")
    print(f"    Analysis time: {analysis['analysis_time']:.3f}s")
    print(f"    Recommendation: {analysis['recommendation']}")
    
    # Large instance
    print("\n  Large instance (28 days, 10 nurses, 2 shifts):")
    analysis = count_possible_outcomes(
        num_days=28, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [0] for d in range(28) for s in range(2)},
        nurse_skills=[0]*10, max_consecutive=5, max_weekly=10,
        weights="unit"
    )
    print(f"    Feasible: {analysis['feasible']}")
    print(f"    Enumerable: {analysis['enumerable']}")
    print(f"    Upper bound: {analysis['upper_bound']:.2e}")
    print(f"    Recommendation: {analysis['recommendation']}")
    
    # Infeasible instance
    print("\n  Infeasible instance:")
    analysis = count_possible_outcomes(
        num_days=7, shifts_per_day=1, num_nurses=2,
        coverage={(d, 0): [0, 0] for d in range(7)},  # 2 nurses per shift, only 2 nurses
        nurse_skills=[0]*2, max_consecutive=5, max_weekly=2,  # capacity 4 < 14
        weights="unit"
    )
    print(f"    Feasible: {analysis['feasible']}")
    print(f"    Recommendation: {analysis['recommendation']}")


def test_preassignment():
    """Test pre-assignment feature."""
    print("\n" + "="*70)
    print("FEATURE 3: PRE-ASSIGNMENT")
    print("="*70)
    
    print("\n  Instance: 7 days, 1 shift/day, 5 nurses")
    print("  Pre-assign: nurse 0 gets day 2, nurse 2 gets day 5")
    
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={0: {(2, 0)}, 2: {(5, 0)}}
    )
    
    print(f"  Result: {result}")
    if result.feasible:
        print(f"  Loads: {result.loads}")
        for i, b in enumerate(result.allocation):
            print(f"    Nurse {i}: {sorted(b)}")
        
        # Verify pre-assignments
        assert (2, 0, 0, 0) in result.allocation[0], "Nurse 0 should have day 2"
        assert (5, 0, 0, 0) in result.allocation[2], "Nurse 2 should have day 5"
        print("  ✓ Pre-assignments respected!")
    
    # Test with coverage (multiple nurses per shift)
    print("\n  Instance: 7 days, 1 shift/day, 7 nurses, 2 per shift")
    print("  Pre-assign: nurse 1 gets one slot of day 3")
    
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [0, 0] for d in range(7)},  # 2 nurses per shift
        nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
        weights="unit",
        pre_assignments={1: {(3, 0)}}
    )
    
    print(f"  Result: {result}")
    if result.feasible:
        # Verify nurse 1 has day 3
        has_day3 = any(g[0] == 3 and g[1] == 0 for g in result.allocation[1])
        print(f"  Nurse 1 has day 3: {has_day3}")
        print(f"  Loads: {result.loads}")
    
    # Test: pre-assignment that violates constraints
    print("\n  Instance: Pre-assignment violates max_consecutive")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=2, max_weekly=5,  # max 2 consecutive
        weights="unit",
        pre_assignments={0: {(0, 0), (1, 0), (2, 0)}}  # 3 consecutive - violates!
    )
    print(f"  Result: {result}")
    if not result.feasible:
        print(f"  Reason: {result.reason}")
    
    # Test: pre-assignment with availability
    print("\n  Instance: Pre-assignment conflicts with availability")
    result = solve_with_preassignment(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
        weights="unit",
        unavailable_days={0: {3}},  # nurse 0 unavailable day 3
        pre_assignments={0: {(3, 0)}}  # but pre-assigned day 3 - conflict!
    )
    print(f"  Result: {result}")
    if not result.feasible:
        print(f"  Reason: {result.reason}")


def test_all_features_combined():
    """Test all three features together."""
    print("\n" + "="*70)
    print("ALL FEATURES COMBINED")
    print("="*70)
    
    print("""
  Scenario: 2-week ward with:
  - Coverage: 1 senior + 1 junior per shift (day/night)
  - 10 nurses (4 senior, 6 junior)
  - Nurse 0 (senior) pre-assigned to day 0 night shift
  - Nurse 5 (junior) unavailable weekends
  - Nurse 2 (senior) on vacation days 10-13
  - Want: 3 diverse schedules + outcome count
    """)
    
    # First: count outcomes
    print("  Step 1: Count possible outcomes")
    analysis = count_possible_outcomes(
        num_days=14, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
        nurse_skills=[1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
        max_consecutive=5, max_weekly=10,
        weights="day_night_weekend",
        unavailable_days={5: {5, 6, 12, 13}},
        vacation_periods={2: [(10, 13)]},
        pre_assignments={0: {(0, 1)}}  # nurse 0 pre-assigned day 0 night
    )
    print(f"    Feasible: {analysis['feasible']}")
    print(f"    Enumerable: {analysis['enumerable']}")
    print(f"    Upper bound: {analysis['upper_bound']:.2e}")
    print(f"    Recommendation: {analysis['recommendation']}")
    
    # Second: get 3 diverse schedules
    print("\n  Step 2: Get 3 diverse schedules")
    results = solve_multiple_schedules(
        num_days=14, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
        nurse_skills=[1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
        max_consecutive=5, max_weekly=10,
        weights="day_night_weekend",
        unavailable_days={5: {5, 6, 12, 13}},
        vacation_periods={2: [(10, 13)]},
        pre_assignments={0: {(0, 1)}},
        num_schedules=3
    )
    
    print(f"    Got {len(results)} schedules:")
    for i, r in enumerate(results):
        if r.feasible:
            # Verify pre-assignment
            pre_ok = any(g[0] == 0 and g[1] == 1 for g in r.allocation[0])
            print(f"      Schedule {i+1}: spread={r.spread:.2f}, EF1={r.ef1}, "
                  f"pre-assign OK={pre_ok}")


def main():
    test_multi_schedule()
    test_outcome_counter()
    test_preassignment()
    test_all_features_combined()
    
    print("\n" + "="*70)
    print("SUMMARY OF NEW FEATURES")
    print("="*70)
    print("""
    1. MULTI-SCHEDULE MODE (solve_multiple_schedules)
       - Returns N diverse valid schedules
       - Diversification via good-ordering variation
       - Each schedule independently valid (feasible + EF1 when possible)
       - Use case: "give me 5 options to choose from"
    
    2. OUTCOME COUNTING (count_possible_outcomes)
       - Fast feasibility check (milliseconds)
       - Upper bound on count (capacity analysis)
       - EXACT count for small instances (n^m <= 10^7)
       - Recommendation: "enumerable" vs "too large, use sampling"
       - Use case: "should I enumerate all, or sample?"
    
    3. PRE-ASSIGNMENT (solve_with_preassignment)
       - Fix specific shifts to specific nurses before solving
       - Solver respects pre-assignments (can't move them)
       - Detects conflicts (pre-assignment violates constraints)
       - Use case: "nurse 0 must work day 0 night shift"
    
    All three features compose: you can pre-assign shifts, count outcomes,
    and get multiple schedules — all in one workflow.
    """)


if __name__ == "__main__":
    main()
