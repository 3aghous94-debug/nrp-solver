# API Reference

## Core classes

### `NRPInstance`

```python
NRPInstance(
    num_days: int,
    shifts_per_day: int,
    num_nurses: int,
    coverage: Dict[Tuple[int, int], List[int]],
    nurse_skills: List[int],
    max_consecutive: int = 5,
    max_weekly: int = 5,
    weights: str = "unit",
)
```

**Parameters:**
- `num_days`: planning horizon in days
- `shifts_per_day`: shifts per day (1 or 2)
- `num_nurses`: number of nurses
- `coverage`: dict `(day, shift) -> list of required skills`. E.g., `{(0, 0): [1, 0]}` means day 0 shift 0 needs 1 senior (skill 1) and 1 junior (skill 0).
- `nurse_skills`: list of skill levels, one per nurse
- `max_consecutive`: max consecutive working days (default 5)
- `max_weekly`: max shifts per week per nurse (default 5)
- `weights`: weight scheme — `"unit"`, `"day_night"`, `"weekend"`, `"day_night_weekend"`, or a custom dict

### `NRPResult`

```python
NRPResult(
    feasible: bool,
    allocation: Optional[List[Set]],
    loads: Optional[List[float]],
    spread: float,
    ef1: bool,
    coverage_ok: bool,
    reason: str,
    method: str,
    solve_time: float,
    stats: Dict,
)
```

**Attributes:**
- `feasible`: whether a valid allocation was found
- `allocation`: list of n sets, each containing the shifts assigned to that nurse
- `loads`: list of n floats, the weighted load per nurse
- `spread`: max load − min load
- `ef1`: whether spread ≤ w_max (weighted-EF1 achieved)
- `coverage_ok`: whether all coverage requirements are met
- `reason`: if infeasible, why
- `method`: which backend was used (`"dwec"`, `"ilp"`, `"infeasibility_check"`, etc.)
- `solve_time`: wall-clock time in seconds
- `stats`: backend-specific stats (direct placements, ejections, etc.)

### `NRPSolver`

```python
NRPSolver(backend: str = "dwec", ilp_time_limit: int = 60)
solver.solve(instance: NRPInstance) -> NRPResult
```

**Backends:**
- `"dwec"` — polynomial, milliseconds, proven EF1 when structurally possible
- `"ilp"` — exact, slower, for benchmarking
- `"hybrid"` — DWEC first, ILP fallback if non-EF1

## Availability extension

### `solve_nrp_with_availability(...)`

Same parameters as `solve_nrp`, plus:

```python
unavailable_days: Optional[Dict[int, Set[int]]] = None,        # {nurse: {days}}
unavailable_shifts: Optional[Dict[int, Set[int]]] = None,      # {nurse: {shift_indices}}
available_weekdays: Optional[Dict[int, Set[int]]] = None,      # {nurse: {0=Mon..6=Sun}}
vacation_periods: Optional[Dict[int, List[Tuple[int, int]]]] = None,  # {nurse: [(start, end)]}
max_night_shifts: Optional[Dict[int, int]] = None,             # {nurse: max_nights}
```

## Pre-assignment

### `solve_with_preassignment(...)`

Same parameters as `solve_nrp_with_availability`, plus:

```python
pre_assignments: Optional[Dict[int, Set[Tuple[int, int]]]] = None,
# {nurse_idx: {(day, shift), ...}}
```

Conflicts are detected upfront and reported in `result.reason`.

## Multi-schedule mode

### `solve_multiple_schedules(...)`

Same parameters as `solve_nrp_with_availability`, plus:

```python
num_schedules: int = 5,
seed: int = 42,
```

Returns `List[NRPResult]` — up to `num_schedules` diverse valid schedules.

## Outcome counting

### `count_possible_outcomes(...)`

Same parameters as `solve_nrp_with_availability`. Returns a dict:

```python
{
    "feasible": bool,
    "exact_count": Optional[int],      # only for small instances
    "ef1_count": Optional[int],        # only for small instances
    "upper_bound": int,                # rough upper bound
    "enumerable": bool,                # can exact count be computed?
    "recommendation": str,             # guidance
    "analysis_time": float,
}
```

## Convenience functions

```python
# One-shot solve (basic)
from nrp_solver import solve_nrp
result = solve_nrp(num_days=7, shifts_per_day=1, num_nurses=5, ...)

# One-shot solve (with availability)
from nrp_solver import solve_nrp_with_availability
result = solve_nrp_with_availability(..., unavailable_days={0: {3}})

# One-shot solve (with pre-assignment)
from nrp_solver import solve_with_preassignment
result = solve_with_preassignment(..., pre_assignments={0: {(2, 0)}})

# Multi-schedule
from nrp_solver import solve_multiple_schedules
results = solve_multiple_schedules(..., num_schedules=5)

# Outcome counting
from nrp_solver import count_possible_outcomes
analysis = count_possible_outcomes(...)

# Benchmark DWEC vs ILP
from nrp_solver import benchmark_backends
bench = benchmark_backends(instance, ilp_time_limit=30)
```
