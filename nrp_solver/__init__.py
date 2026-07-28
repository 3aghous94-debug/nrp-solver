"""
NRP Solver: Envy-Free Nurse Rostering with Coverage, Skills, and Availability

A polynomial-time solver for nurse rostering that achieves weighted-EF1
fairness when structurally possible, with full support for:
  - Coverage constraints (multiple nurses per shift, per-slot skill requirements)
  - Skill mix (senior/junior nurses, per-shift skill requirements)
  - Per-nurse availability (days off, shift preferences, part-time, vacations)
  - Pre-assignments (fix specific shifts to specific nurses)
  - Multi-schedule mode (generate diverse valid schedules)
  - Outcome counting (feasibility + upper bound + exact count for small instances)

Quick start:
    from nrp_solver import solve_nrp
    
    result = solve_nrp(
        num_days=14, shifts_per_day=2, num_nurses=10,
        coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
        nurse_skills=[1]*5 + [0]*5,
        max_consecutive=5, max_weekly=10,
        weights="day_night_weekend",
    )
    print(f"Feasible: {result.feasible}, Spread: {result.spread}, EF1: {result.ef1}")
"""

from .core import (
    NRPInstance, NRPSolver, NRPResult, InfeasibilityDetector,
    DWECBackend, ILPBackend, solve_nrp, benchmark_backends
)
from .availability import (
    AvailabilityNRPInstance, AvailabilityNRPSolver,
    AvailabilityInfeasibilityDetector,
    solve_nrp_with_availability
)
from .extensions import (
    PreAssignmentNRPInstance, PreAssignmentSolver,
    MultiScheduleSolver, OutcomeCounter,
    solve_with_preassignment, solve_multiple_schedules,
    count_possible_outcomes
)

__version__ = "1.0.0"
__author__ = "NRP Solver Project"

__all__ = [
    # Core
    "NRPInstance", "NRPSolver", "NRPResult", "InfeasibilityDetector",
    "DWECBackend", "ILPBackend", "solve_nrp", "benchmark_backends",
    # Availability
    "AvailabilityNRPInstance", "AvailabilityNRPSolver",
    "AvailabilityInfeasibilityDetector", "solve_nrp_with_availability",
    # Extensions
    "PreAssignmentNRPInstance", "PreAssignmentSolver",
    "MultiScheduleSolver", "OutcomeCounter",
    "solve_with_preassignment", "solve_multiple_schedules",
    "count_possible_outcomes",
]
