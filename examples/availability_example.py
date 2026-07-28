"""Per-nurse availability: part-time, no-nights, vacation, etc."""
from nrp_solver import solve_nrp_with_availability

result = solve_nrp_with_availability(
    num_days=14, shifts_per_day=2, num_nurses=10,
    coverage={(d, s): [1, 0] for d in range(14) for s in range(2)},
    nurse_skills=[1]*5 + [0]*5,
    max_consecutive=5, max_weekly=10,
    weights="day_night_weekend",
    # Availability constraints:
    available_weekdays={0: {0, 1, 2}},      # nurse 0: Mon-Wed only
    unavailable_shifts={1: {1}},             # nurse 1: no nights
    vacation_periods={2: [(10, 13)]},        # nurse 2: vacation days 10-13
    unavailable_days={5: {5, 6, 12, 13}},    # nurse 5: no weekends
    max_night_shifts={6: 2},                 # nurse 6: max 2 nights
)

print(f"Feasible: {result.feasible}")
print(f"Spread: {result.spread:.2f}, EF1: {result.ef1}")
print()

# Verify all constraints
violations = []
for i, bundle in enumerate(result.allocation):
    for (d, s, ci, sk) in bundle:
        if i == 0 and d % 7 not in {0, 1, 2}:
            violations.append(f"Nurse 0 works wrong weekday (day {d})")
        if i == 1 and s == 1:
            violations.append(f"Nurse 1 works night (day {d})")
        if i == 2 and 10 <= d <= 13:
            violations.append(f"Nurse 2 works during vacation (day {d})")
        if i == 5 and d % 7 >= 5:
            violations.append(f"Nurse 5 works weekend (day {d})")

nights_6 = sum(1 for g in result.allocation[6] if g[1] == 1)
if nights_6 > 2:
    violations.append(f"Nurse 6 has {nights_6} nights (> 2)")

if violations:
    print(f"VIOLATIONS ({len(violations)}):")
    for v in violations[:5]:
        print(f"  {v}")
else:
    print("✓ All availability constraints satisfied!")
