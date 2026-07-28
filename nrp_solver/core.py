"""
Production NRP Solver Module

Clean API for solving nurse rostering with EF1 fairness guarantees.

Usage:
    from nrp_solver import NRPSolver, NRPInstance
    
    instance = NRPInstance(
        num_days=14,
        shifts_per_day=2,
        num_nurses=10,
        coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},  # 1 senior + 1 junior
        nurse_skills=[1,1,1,1,1,0,0,0,0,0],  # 5 senior, 5 junior
        max_consecutive=5,
        max_weekly=10,
        weights="day_night_weekend",
    )
    
    solver = NRPSolver()
    result = solver.solve(instance)
    
    if result.feasible:
        print(f"Spread: {result.spread:.2f}")
        print(f"EF1: {result.ef1}")
        print(f"Coverage satisfied: {result.coverage_ok}")
        for i, bundle in enumerate(result.allocation):
            print(f"Nurse {i}: {bundle}")
    else:
        print(f"Infeasible: {result.reason}")
"""

from collections import defaultdict
from typing import List, Dict, Set, Tuple, Optional
import time


# ============================================================
# Data structures
# ============================================================

class NRPInstance:
    """A nurse rostering problem instance."""
    
    def __init__(self, num_days: int, shifts_per_day: int, num_nurses: int,
                 coverage: Dict[Tuple[int, int], List[int]],
                 nurse_skills: List[int],
                 max_consecutive: int = 5,
                 max_weekly: int = 5,
                 weights: str = "unit"):
        """
        Args:
            num_days: planning horizon in days
            shifts_per_day: shifts per day (1 or 2)
            num_nurses: number of nurses
            coverage: dict (day, shift) -> list of required skills
                      e.g., {(0, 0): [1, 0]} means day 0 shift 0 needs
                      1 senior (skill 1) and 1 junior (skill 0)
            nurse_skills: list of skill levels, one per nurse
            max_consecutive: max consecutive working days
            max_weekly: max shifts per week per nurse
            weights: weight scheme - "unit", "day_night", "weekend",
                     "day_night_weekend", or a custom dict
        """
        self.num_days = num_days
        self.shifts_per_day = shifts_per_day
        self.num_nurses = num_nurses
        self.coverage = coverage
        self.nurse_skills = list(nurse_skills)
        self.max_consecutive = max_consecutive
        self.max_weekly = max_weekly
        self.weight_scheme = weights if isinstance(weights, str) else "custom"
        self.custom_weights = weights if isinstance(weights, dict) else None
        
        # Build goods (coverage slots)
        self.goods = []
        for d in range(num_days):
            for s in range(shifts_per_day):
                if (d, s) in coverage:
                    for idx, req_skill in enumerate(coverage[(d, s)]):
                        self.goods.append((d, s, idx, req_skill))
        self.m = len(self.goods)
        
        # Build weights
        self.weights = self._make_weights()
        self.w_max = max(self.weights.values()) if self.weights else 0
    
    def _make_weights(self) -> Dict:
        weights = {}
        for good in self.goods:
            d, s, ci, sk = good
            is_weekend = (d % 7) >= 5
            scheme = self.weight_scheme
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
            elif scheme == "custom":
                w = self.custom_weights.get((d, s), 1.0)
            else:
                w = 1.0
            weights[good] = w
        return weights
    
    def is_feasible_for(self, nurse_idx: int, bundle: Set) -> bool:
        """Check if bundle is feasible for nurse nurse_idx."""
        bundle = set(bundle)
        
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
        
        return True


class NRPResult:
    """Result of solving an NRP instance."""
    
    def __init__(self, feasible: bool, allocation: Optional[List[Set]] = None,
                 loads: Optional[List[float]] = None, spread: float = 0.0,
                 ef1: bool = False, coverage_ok: bool = False,
                 reason: str = "", method: str = "", solve_time: float = 0.0,
                 stats: Optional[Dict] = None):
        self.feasible = feasible
        self.allocation = allocation
        self.loads = loads
        self.spread = spread
        self.ef1 = ef1
        self.coverage_ok = coverage_ok
        self.reason = reason  # why infeasible, if not feasible
        self.method = method  # "dwec", "ilp", "hybrid"
        self.solve_time = solve_time
        self.stats = stats or {}
    
    def __repr__(self):
        if not self.feasible:
            return f"NRPResult(INFEASIBLE: {self.reason})"
        return (f"NRPResult(feasible, spread={self.spread:.2f}, "
                f"EF1={self.ef1}, coverage={self.coverage_ok}, "
                f"method={self.method}, time={self.solve_time:.2f}s)")


# ============================================================
# Infeasibility detection
# ============================================================

class InfeasibilityDetector:
    """Detect infeasibility upfront before running the algorithm."""
    
    @staticmethod
    def check(instance: NRPInstance) -> Tuple[bool, str]:
        """Returns (feasible, reason). reason is empty if feasible."""
        n = instance.num_nurses
        num_weeks = (instance.num_days + 6) // 7

        # Check 0: Nurses exist
        if n == 0:
            return False, "No nurses"
        if instance.m == 0:
            return False, "No shifts to assign"

        # Check 1: Total capacity vs total demand
        total_demand = len(instance.goods)
        total_capacity = n * instance.max_weekly * num_weeks
        if total_demand > total_capacity:
            return False, (f"Total demand ({total_demand} slots) exceeds total capacity "
                          f"({total_capacity} = {n} nurses × {instance.max_weekly}/week × {num_weeks} weeks)")

        # Check 2: Per-skill capacity vs per-skill demand
        # For each skill level, count nurses who can do it and slots that require it
        all_skill_levels = set(instance.nurse_skills) | set(g[3] for g in instance.goods)
        for skill_level in all_skill_levels:
            nurses_with_skill = sum(1 for sk in instance.nurse_skills if sk >= skill_level)
            slots_requiring_skill = sum(1 for g in instance.goods if g[3] == skill_level)
            if slots_requiring_skill == 0:
                continue
            skill_capacity = nurses_with_skill * instance.max_weekly * num_weeks
            if slots_requiring_skill > skill_capacity:
                return False, (f"Skill {skill_level} demand ({slots_requiring_skill} slots) exceeds "
                              f"capacity ({skill_capacity} = {nurses_with_skill} nurses × "
                              f"{instance.max_weekly}/week × {num_weeks} weeks)")

        # Check 3: Per-day coverage vs available nurses
        for d in range(instance.num_days):
            for s in range(instance.shifts_per_day):
                if (d, s) not in instance.coverage:
                    continue
                req = instance.coverage[(d, s)]
                for req_sk in set(req):
                    count_needed = sum(1 for r in req if r == req_sk)
                    count_available = sum(1 for sk in instance.nurse_skills if sk >= req_sk)
                    if count_available < count_needed:
                        return False, (f"Day {d} shift {s} needs {count_needed} nurses with "
                                      f"skill {req_sk}, but only {count_available} available")

        return True, ""


# ============================================================
# DWEC Algorithm (production version)
# ============================================================

class DWECBackend:
    """DWEC algorithm backend."""
    
    def solve(self, instance: NRPInstance) -> NRPResult:
        t0 = time.time()
        n = instance.num_nurses
        weights = instance.weights
        w_max = instance.w_max
        
        # Sort goods by decreasing weight, then decreasing skill requirement
        sorted_goods = sorted(instance.goods,
                             key=lambda g: (-weights[g], -g[3]))
        
        pi = [set() for _ in range(n)]
        loads = [0.0] * n
        leftover = []
        stats = {"direct": 0, "ejections": 0, "relaxed": 0, "deferred": 0}
        shift_coverage = defaultdict(set)
        
        for s_good in sorted_goods:
            d, s, ci, req_skill = s_good
            min_load = min(loads)
            k = min(range(n), key=lambda i: loads[i])
            
            # Direct placement
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
            
            # Relaxed placement
            feasible_agents = [i for i in range(n)
                             if instance.nurse_skills[i] >= req_skill and
                             instance.is_feasible_for(i, pi[i] | {s_good})]
            if feasible_agents:
                i = min(feasible_agents, key=lambda i: loads[i])
                pi[i] = pi[i] | {s_good}
                loads[i] += weights[s_good]
                shift_coverage[(d, s)].add(ci)
                stats["relaxed"] += 1
            else:
                leftover.append(s_good)
                stats["deferred"] += 1
        
        # Place leftover (no forcing)
        for s_good in leftover:
            d, s, ci, req_skill = s_good
            feasible_agents = [i for i in range(n)
                             if instance.nurse_skills[i] >= req_skill and
                             instance.is_feasible_for(i, pi[i] | {s_good})]
            if feasible_agents:
                i = min(feasible_agents, key=lambda i: loads[i])
                pi[i] = pi[i] | {s_good}
                loads[i] += weights[s_good]
                shift_coverage[(d, s)].add(ci)
        
        # Verify coverage
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
            method="dwec",
            solve_time=t1 - t0,
            stats=stats
        )


# ============================================================
# ILP Backend (for benchmarking and exact solving)
# ============================================================

class ILPBackend:
    """ILP solver backend using PuLP/CBC."""
    
    def __init__(self, time_limit: int = 60):
        self.time_limit = time_limit
    
    def solve(self, instance: NRPInstance) -> NRPResult:
        try:
            from pulp import (LpMinimize, LpProblem, LpVariable, lpSum,
                            PULP_CBC_CMD, LpStatus, value)
        except ImportError:
            return NRPResult(feasible=False, reason="PuLP not installed",
                           method="ilp")
        
        t0 = time.time()
        n = instance.num_nurses
        m = instance.m
        goods = instance.goods
        weights = instance.weights
        w_max = instance.w_max
        
        prob = LpProblem("NRP", LpMinimize)
        
        # Variables: x[i][j] = 1 if nurse i gets good j
        x = {}
        for i in range(n):
            for j in range(m):
                x[(i, j)] = LpVariable(f"x_{i}_{j}", 0, 1, cat='Binary')
        
        T = LpVariable("T", lowBound=0, cat='Continuous')
        L = LpVariable("L", lowBound=0, cat='Continuous')
        
        prob += T
        
        # Coverage: each good assigned to exactly one nurse with right skill
        for j, good in enumerate(goods):
            prob += lpSum(x[(i, j)] for i in range(n)
                         if instance.nurse_skills[i] >= good[3]) == 1
        
        # Per-nurse constraints
        for i in range(n):
            # Weekly cap
            for week_start in range(0, instance.num_days, 7):
                week_end = min(week_start + 7, instance.num_days)
                week_goods = [j for j, g in enumerate(goods) if week_start <= g[0] < week_end]
                prob += lpSum(x[(i, j)] for j in week_goods) <= instance.max_weekly
            
            # Consecutive days (linearized: for each window of K+1 days, at most K)
            for start in range(instance.num_days - instance.max_consecutive):
                window_goods = [j for j, g in enumerate(goods)
                               if start <= g[0] <= start + instance.max_consecutive]
                prob += lpSum(x[(i, j)] for j in window_goods) <= instance.max_consecutive
            
            # One shift per day
            for d in range(instance.num_days):
                day_goods = [j for j, g in enumerate(goods) if g[0] == d]
                if len(day_goods) > 1 and instance.shifts_per_day > 1:
                    # At most one shift per day (but can have multiple slots of same shift)
                    # Group by shift
                    shift_groups = defaultdict(list)
                    for j in day_goods:
                        shift_groups[goods[j][1]].append(j)
                    for s, group in shift_groups.items():
                        # Can take multiple slots of same shift
                        pass
                    # But can't take slots of DIFFERENT shifts same day
                    shifts_in_day = set(goods[j][1] for j in day_goods)
                    if len(shifts_in_day) > 1:
                        # Binary indicator: nurse works shift s on day d
                        # This is complex; simplify: at most max_consecutive_in_day shifts
                        # Actually for standard NRP: at most 1 shift per day
                        prob += lpSum(x[(i, j)] for j in day_goods) <= 1
            
            # Load balance
            load_i = lpSum(weights[goods[j]] * x[(i, j)] for j in range(m))
            prob += load_i >= L
            prob += load_i <= L + T
        
        solver = PULP_CBC_CMD(msg=0, timeLimit=self.time_limit)
        prob.solve(solver)
        
        if prob.status != 1:
            return NRPResult(feasible=False, reason=f"ILP status: {LpStatus[prob.status]}",
                           method="ilp", solve_time=time.time() - t0)
        
        pi = []
        for i in range(n):
            bundle = set()
            for j in range(m):
                if value(x[(i, j)]) > 0.5:
                    bundle.add(goods[j])
            pi.append(bundle)
        
        loads = [sum(weights[g] for g in b) for b in pi]
        spread = float(value(T))
        
        # Verify coverage
        shift_coverage = defaultdict(set)
        for i, b in enumerate(pi):
            for (d, s, ci, sk) in b:
                shift_coverage[(d, s)].add(ci)
        coverage_ok = all(
            len(shift_coverage[(d, s)]) == len(reqs)
            for (d, s), reqs in instance.coverage.items()
        )
        
        t1 = time.time()
        return NRPResult(
            feasible=True,
            allocation=pi, loads=loads, spread=spread,
            ef1=spread <= w_max + 1e-9,
            coverage_ok=coverage_ok,
            method="ilp",
            solve_time=t1 - t0
        )


# ============================================================
# Main solver (hybrid: infeasibility check + DWEC + optional ILP)
# ============================================================

class NRPSolver:
    """Main NRP solver. Auto-detects infeasibility, then runs DWEC."""
    
    def __init__(self, backend: str = "dwec", ilp_time_limit: int = 60):
        """
        Args:
            backend: "dwec" (fast, polynomial) or "ilp" (exact, slower)
            ilp_time_limit: time limit for ILP backend in seconds
        """
        self.backend_name = backend
        self.ilp_time_limit = ilp_time_limit
    
    def solve(self, instance: NRPInstance) -> NRPResult:
        # Step 1: Infeasibility check
        feasible, reason = InfeasibilityDetector.check(instance)
        if not feasible:
            return NRPResult(feasible=False, reason=reason, method="infeasibility_check")
        
        # Step 2: Solve with chosen backend
        if self.backend_name == "dwec":
            return DWECBackend().solve(instance)
        elif self.backend_name == "ilp":
            return ILPBackend(self.ilp_time_limit).solve(instance)
        elif self.backend_name == "hybrid":
            # Run DWEC first, then ILP if DWEC fails or is non-EF1
            dwec_result = DWECBackend().solve(instance)
            if dwec_result.feasible and dwec_result.ef1:
                return dwec_result
            # Try ILP
            ilp_result = ILPBackend(self.ilp_time_limit).solve(instance)
            if ilp_result.feasible and ilp_result.spread < dwec_result.spread:
                return ilp_result
            return dwec_result
        else:
            raise ValueError(f"Unknown backend: {self.backend_name}")


# ============================================================
# Convenience functions
# ============================================================

def solve_nrp(num_days: int, shifts_per_day: int, num_nurses: int,
              coverage: Dict, nurse_skills: List[int],
              max_consecutive: int = 5, max_weekly: int = 5,
              weights: str = "unit", backend: str = "dwec") -> NRPResult:
    """One-shot NRP solver."""
    instance = NRPInstance(num_days, shifts_per_day, num_nurses, coverage,
                          nurse_skills, max_consecutive, max_weekly, weights)
    solver = NRPSolver(backend=backend)
    return solver.solve(instance)


def benchmark_backends(instance: NRPInstance, ilp_time_limit: int = 60) -> Dict:
    """Run both backends and compare."""
    results = {}
    
    # DWEC
    dwec_result = NRPSolver(backend="dwec").solve(instance)
    results["dwec"] = {
        "feasible": dwec_result.feasible,
        "spread": dwec_result.spread,
        "ef1": dwec_result.ef1,
        "coverage_ok": dwec_result.coverage_ok,
        "time": dwec_result.solve_time,
        "stats": dwec_result.stats,
    }
    
    # ILP
    ilp_result = NRPSolver(backend="ilp", ilp_time_limit=ilp_time_limit).solve(instance)
    results["ilp"] = {
        "feasible": ilp_result.feasible,
        "spread": ilp_result.spread if ilp_result.feasible else None,
        "ef1": ilp_result.ef1 if ilp_result.feasible else None,
        "coverage_ok": ilp_result.coverage_ok if ilp_result.feasible else None,
        "time": ilp_result.solve_time,
        "reason": ilp_result.reason if not ilp_result.feasible else "",
    }
    
    # Comparison
    if results["dwec"]["feasible"] and results["ilp"]["feasible"]:
        results["comparison"] = {
            "dwec_spread": results["dwec"]["spread"],
            "ilp_spread": results["ilp"]["spread"],
            "ratio": results["dwec"]["spread"] / max(results["ilp"]["spread"], 0.01),
            "dwec_faster": results["dwec"]["time"] < results["ilp"]["time"],
            "speedup": results["ilp"]["time"] / max(results["dwec"]["time"], 0.001),
        }
    
    return results


# ============================================================
# Demo
# ============================================================

if __name__ == "__main__":
    print("="*70)
    print("NRP Solver Module — Demo")
    print("="*70)
    
    # Demo 1: Simple feasible instance
    print("\n--- Demo 1: 1 week, 1 shift/day, 5 nurses, no skills ---")
    result = solve_nrp(
        num_days=7, shifts_per_day=1, num_nurses=5,
        coverage={(d, 0): [0] for d in range(7)},
        nurse_skills=[0]*5,
        max_consecutive=5, max_weekly=5,
        weights="unit"
    )
    print(result)
    if result.feasible:
        for i, b in enumerate(result.allocation):
            print(f"  Nurse {i}: {len(b)} shifts, load {result.loads[i]:.1f}")
    
    # Demo 2: With coverage and skills
    print("\n--- Demo 2: 2 weeks, 2 shifts/day, 10 nurses, coverage 1S+1J ---")
    result = solve_nrp(
        num_days=14, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
        nurse_skills=[1]*5 + [0]*5,  # 5 senior, 5 junior
        max_consecutive=5, max_weekly=10,
        weights="day_night_weekend"
    )
    print(result)
    if result.feasible:
        for i, b in enumerate(result.allocation):
            sk = "S" if result.allocation and i < 5 else "J"
            print(f"  Nurse {i} ({sk}): {len(b)} shifts, load {result.loads[i]:.1f}")
    
    # Demo 3: Infeasible instance
    print("\n--- Demo 3: Infeasible (not enough seniors) ---")
    result = solve_nrp(
        num_days=7, shifts_per_day=1, num_nurses=7,
        coverage={(d, 0): [1, 0] for d in range(7)},  # 1 senior + 1 junior per shift
        nurse_skills=[1, 0, 0, 0, 0, 0, 0],  # only 1 senior, max_weekly=5
        max_consecutive=5, max_weekly=5,
        weights="unit"
    )
    print(result)
    print(f"  Reason: {result.reason}")
    
    # Demo 4: Benchmark DWEC vs ILP
    print("\n--- Demo 4: Benchmark DWEC vs ILP ---")
    instance = NRPInstance(
        num_days=7, shifts_per_day=2, num_nurses=7,
        coverage={(d, s): [0] for d in range(7) for s in range(2)},
        nurse_skills=[0]*7,
        max_consecutive=5, max_weekly=5,
        weights="day_night_weekend"
    )
    bench = benchmark_backends(instance, ilp_time_limit=30)
    print(f"  DWEC: spread={bench['dwec']['spread']:.2f}, "
          f"EF1={bench['dwec']['ef1']}, time={bench['dwec']['time']:.3f}s")
    if bench['ilp']['feasible']:
        print(f"  ILP:  spread={bench['ilp']['spread']:.2f}, "
              f"EF1={bench['ilp']['ef1']}, time={bench['ilp']['time']:.3f}s")
        c = bench['comparison']
        print(f"  Ratio: {c['ratio']:.2f}, DWEC speedup: {c['speedup']:.1f}x")
