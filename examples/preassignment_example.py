"""Pre-assignment: fix specific shifts to specific nurses."""
from nrp_solver import solve_with_preassignment

# Valid pre-assignment
print("=== Valid pre-assignment ===")
result = solve_with_preassignment(
    num_days=7, shifts_per_day=1, num_nurses=5,
    coverage={(d, 0): [0] for d in range(7)},
    nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
    weights="unit",
    pre_assignments={0: {(2, 0)}, 2: {(5, 0)}},
)
print(f"Feasible: {result.feasible}")
if result.feasible:
    for i, b in enumerate(result.allocation):
        print(f"  Nurse {i}: {sorted(b)}")

# Conflicting pre-assignment (nurse unavailable)
print("\n=== Conflicting pre-assignment ===")
result = solve_with_preassignment(
    num_days=7, shifts_per_day=1, num_nurses=5,
    coverage={(d, 0): [0] for d in range(7)},
    nurse_skills=[0]*5, max_consecutive=5, max_weekly=5,
    weights="unit",
    unavailable_days={0: {3}},
    pre_assignments={0: {(3, 0)}},  # conflict!
)
print(f"Feasible: {result.feasible}")
print(f"Reason: {result.reason}")
