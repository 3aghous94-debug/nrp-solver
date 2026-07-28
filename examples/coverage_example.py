"""Coverage with skill mix: 2 weeks, 1 senior + 1 junior per shift."""
from nrp_solver import solve_nrp

result = solve_nrp(
    num_days=14, shifts_per_day=2, num_nurses=10,
    coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
    nurse_skills=[1]*5 + [0]*5,  # 5 senior, 5 junior
    max_consecutive=5, max_weekly=10,
    weights="day_night_weekend",
)

print(f"Feasible: {result.feasible}")
print(f"Spread: {result.spread:.2f}, EF1: {result.ef1}")
print(f"Coverage OK: {result.coverage_ok}")
print()
for i, bundle in enumerate(result.allocation):
    skill = "S" if i < 5 else "J"
    nights = sum(1 for g in bundle if g[1] == 1)
    print(f"  Nurse {i} ({skill}): {len(bundle)} shifts, {nights} nights, "
          f"load {result.loads[i]:.1f}")
