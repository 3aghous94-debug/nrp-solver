# NRP Solver

**Envy-Free Nurse Rostering with Coverage, Skills, and Availability**

A polynomial-time solver for the Nurse Rostering Problem (NRP) that achieves weighted-EF1 fairness when structurally possible. Handles the full operational feature set: coverage constraints, skill mix, per-nurse availability, pre-assignments, and multi-schedule generation.

## Why this exists

Standard NRP solvers (ILP-based, constraint programming, metaheuristics) optimize for coverage and soft constraints but don't guarantee fairness across nurses. This solver guarantees **weighted-EF1** (Envy-Free up to one good): no nurse envies another nurse's roster by more than the weight of a single shift. The algorithm runs in milliseconds even for 8-week horizons with 20+ nurses.

The core algorithm is **DWEC** (Decreasing-Weight Ejection Chain) — a novel polynomial-time algorithm that processes shifts in decreasing weight order and uses directed ejections (not swaps) to maintain the spread bound. See [`docs/THEORY.md`](docs/THEORY.md) for the full theoretical treatment.

## Features

| Feature | Status |
|---|---|
| Weighted-EF1 guarantee (spread ≤ w_max) | ✅ Proven, verified on 500+ instances |
| Coverage constraints (multiple nurses per shift, per-slot skills) | ✅ |
| Skill mix (senior/junior, per-shift skill requirements) | ✅ |
| Per-nurse availability (days off, no-nights, part-time, vacation) | ✅ |
| Pre-assignments (fix specific shifts to specific nurses) | ✅ With conflict detection |
| Multi-schedule mode (generate N diverse valid schedules) | ✅ |
| Outcome counting (exact for small, upper-bound for large) | ✅ |
| Upfront infeasibility detection | ✅ |
| ILP backend for benchmarking | ✅ |
| Polynomial time: O(m³n) | ✅ |
| Scales to 224+ coverage slots in <0.2s | ✅ |

## Quick start

```bash
pip install -r requirements.txt
```

```python
from nrp_solver import solve_nrp

result = solve_nrp(
    num_days=14, shifts_per_day=2, num_nurses=10,
    coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},  # 1 senior + 1 junior per shift
    nurse_skills=[1]*5 + [0]*5,  # 5 senior, 5 junior
    max_consecutive=5, max_weekly=10,
    weights="day_night_weekend",
)

print(f"Feasible: {result.feasible}")
print(f"Spread: {result.spread:.2f}")
print(f"EF1: {result.ef1}")
print(f"Coverage satisfied: {result.coverage_ok}")
for i, bundle in enumerate(result.allocation):
    print(f"  Nurse {i}: {len(bundle)} shifts, load {result.loads[i]:.1f}")
```

## Feature examples

### Coverage with skill mix

```python
from nrp_solver import solve_nrp

# 2 weeks, 2 shifts/day, 1 senior + 1 junior per shift
result = solve_nrp(
    num_days=14, shifts_per_day=2, num_nurses=10,
    coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
    nurse_skills=[1]*5 + [0]*5,
    max_consecutive=5, max_weekly=10,
    weights="day_night_weekend",
)
```

### Per-nurse availability

```python
from nrp_solver import solve_nrp_with_availability

result = solve_nrp_with_availability(
    num_days=14, shifts_per_day=2, num_nurses=10,
    coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
    nurse_skills=[1]*5 + [0]*5,
    max_consecutive=5, max_weekly=10,
    weights="day_night_weekend",
    available_weekdays={0: {0, 1, 2}},      # nurse 0: Mon-Wed only
    unavailable_shifts={1: {1}},             # nurse 1: no nights
    vacation_periods={2: [(10, 13)]},        # nurse 2: vacation days 10-13
    unavailable_days={5: {5, 6, 12, 13}},    # nurse 5: no weekends
    max_night_shifts={6: 2},                 # nurse 6: max 2 nights
)
```

### Pre-assignments

```python
from nrp_solver import solve_with_preassignment

result = solve_with_preassignment(
    num_days=7, shifts_per_day=1, num_nurses=5,
    coverage={(d, 0): [0] for d in range(7)},
    nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
    weights="unit",
    pre_assignments={0: {(2, 0)}, 2: {(5, 0)}},  # nurse 0→day2, nurse 2→day5
)
# Conflicts are detected upfront:
# "Pre-assignment conflicts detected:
#  Nurse 0 → (day 3, shift 0): nurse 0 unavailable on day 3"
```

### Multi-schedule mode

```python
from nrp_solver import solve_multiple_schedules

results = solve_multiple_schedules(
    num_days=14, shifts_per_day=1, num_nurses=7,
    coverage={(d, 0): [0] for d in range(14)},
    nurse_skills=[0]*7, max_consecutive=5, max_weekly=5,
    weights="unit",
    num_schedules=5,  # request 5 diverse schedules
)
for i, r in enumerate(results):
    if r.feasible:
        print(f"Schedule {i+1}: spread={r.spread:.2f}, EF1={r.ef1}")
```

### Outcome counting (pre-processing)

```python
from nrp_solver import count_possible_outcomes

analysis = count_possible_outcomes(
    num_days=7, shifts_per_day=1, num_nurses=3,
    coverage={(d, 0): [0] for d in range(7)},
    nurse_skills=[0]*3, max_consecutive=5, max_weekly=5,
    weights="unit",
)
# For small instances:
#   analysis["exact_count"] = 2142  (feasible schedules)
#   analysis["ef1_count"] = 630     (EF1 schedules)
# For large instances:
#   analysis["upper_bound"] = 1.27e+43
#   analysis["recommendation"] = "Use multi-schedule mode to sample"
```

## Performance

| Instance | Slots (m) | Nurses (n) | Solve time | EF1 achieved |
|---|---|---|---|---|
| 1 week, 1 shift, 5 nurses | 7 | 5 | <0.001s | ✅ |
| 2 weeks, 2 shifts, 10 nurses, 1S+1J | 56 | 10 | 0.006s | ✅ |
| 4 weeks, 2 shifts, 14 nurses, cov=2 | 112 | 14 | 0.002s | ✅ |
| 8 weeks, 2 shifts, 20 nurses, 1S+1J | 224 | 20 | 0.12s | ✅ |

DWEC is **1000–30000× faster** than ILP on benchmarks, with identical spread.

## Honest limits

- **EF1 is achieved when structurally possible.** When skill concentration or availability makes it impossible (e.g., 4 seniors for 28 senior slots), no algorithm can achieve EF1 — the solver achieves the best possible spread instead.
- **Outcome counting is exact only for small instances** (n^m ≤ 10⁷). For real NRP, you get feasibility + an upper bound + a recommendation to sample.
- **Multi-schedule mode is sampling, not exhaustive enumeration.** You get up to N diverse schedules, not all valid schedules.
- **Soft constraints / preferences** (nurse-specific shift preferences) are not supported — all constraints are hard.

## Repository structure

```
nrp-solver/
├── nrp_solver/              # Main package
│   ├── __init__.py
│   ├── core.py              # NRPInstance, NRPSolver, DWEC backend, ILP backend
│   ├── availability.py      # Per-nurse availability extension
│   ├── extensions.py        # Pre-assignment, multi-schedule, outcome counting
│   └── dwec.py              # DWEC algorithm (theoretical reference)
├── tests/                   # Test suite
│   ├── test_preassignment.py
│   └── test_infeasibility.py
├── benchmarks/              # Performance benchmarks
│   └── benchmark.py
├── theory/                  # Theoretical research scripts
│   ├── local_exchange.py
│   ├── weighted_extension.py
│   ├── formal_proofs.py
│   ├── dwec_verification.py
│   └── ...
├── docs/                    # Documentation
│   ├── THEORY.md
│   ├── ALGORITHMS.md
│   └── API.md
├── examples/                # Usage examples
├── README.md
├── LICENSE
├── requirements.txt
└── setup.py
```

## Theoretical background

The solver is based on three proven results:

1. **Main Theorem (unit weights)**: If F satisfies global local exchange (LE) and an allocation exists, then an EF1 allocation exists. Proven via the swap-cascade algorithm.

2. **Theorem D.1 (weighted r-completeness)**: If F is r-complete with ⌈m/n⌉ ≤ r, then weighted-EF1 is achievable via LPT round-robin. Spread ≤ w_max.

3. **DWEC algorithm**: For weighted non-r-complete families, the Decreasing-Weight Ejection Chain algorithm achieves weighted-EF1 when structurally possible. The ejection mechanism (eject from non-least-loaded agent, send to least-loaded) preserves the spread bound.

See [`docs/THEORY.md`](docs/THEORY.md) for full proofs and [`theory/`](theory/) for the research scripts that verified them.

## License

MIT — see [LICENSE](LICENSE).

## Citation

If you use this solver in research, please cite:

```bibtex
@software{nrp_solver_2026,
  title={NRP Solver: Envy-Free Nurse Rostering with Coverage, Skills, and Availability},
  year={2026},
  url={https://github.com/3aghous94-debug/nrp-solver}
}
```
