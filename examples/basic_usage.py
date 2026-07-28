"""Basic usage: simple NRP instance."""
from nrp_solver import solve_nrp

# 1 week, 1 shift/day, 5 nurses, no skills
result = solve_nrp(
    num_days=7, shifts_per_day=1, num_nurses=5,
    coverage={(d, 0): [0] for d in range(7)},
    nurse_skills=[0]*5,
    max_consecutive=5, max_weekly=5,
    weights="unit",
)

print(f"Feasible: {result.feasible}")
print(f"Spread: {result.spread:.2f}, EF1: {result.ef1}")
print(f"Coverage OK: {result.coverage_ok}")
print(f"Solve time: {result.solve_time:.4f}s")
print()
for i, bundle in enumerate(result.allocation):
    print(f"  Nurse {i}: {len(bundle)} shifts, load {result.loads[i]:.1f}")
