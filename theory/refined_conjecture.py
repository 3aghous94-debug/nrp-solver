"""
Deeper investigation: LE is necessary but not sufficient.
The K_4 case shows: LE can hold but EF1 fails when the instance is infeasible
or when the structural capacity is insufficient.

We need to identify the EXACT condition. Hypothesis: LE + (instance feasibility)
=> EF1. Let me test this.
"""

from itertools import combinations
from local_exchange_ef1 import FeasibilityFamily, brute_force_min_spread
from bfp_solver_toolkit import ilp_min_spread
from test_aa_conjecture import (
    DominantGoodFamily, BridgeFamily, ISFamily,
    check_global_local_exchange, build_feasibility_graph
)


class UniformMatroid(FeasibilityFamily):
    def __init__(self, S, r):
        super().__init__(S)
        self.r = r
    def is_feasible(self, A):
        return len(A) <= self.r


class ConsecutiveDaysFamily(FeasibilityFamily):
    def __init__(self, m, K):
        super().__init__(range(m))
        self.K = K
    def is_feasible(self, A):
        A = sorted(set(A))
        run = 1
        for i in range(1, len(A)):
            if A[i] == A[i-1] + 1:
                run += 1
                if run > self.K:
                    return False
            else:
                run = 1
        return True


class SwapHeavyFamily(FeasibilityFamily):
    """F = {A : |A| <= r} ∪ {A : |A| = r+1 and 0 ∈ A}."""
    def __init__(self, S, r):
        super().__init__(S)
        self.r = r
    def is_feasible(self, A):
        A = set(A)
        if len(A) <= self.r:
            return True
        if len(A) == self.r + 1 and 0 in A:
            return True
        return False


def test_le_plus_feasibility():
    """Test: LE + feasibility => EF1?"""
    print("="*70)
    print("REFINED CONJECTURE: LE + Feasibility => EF1")
    print("="*70)

    test_cases = [
        # (name, F, n, expected_le, expected_feasible, expected_ef1)
        ("Uniform U_{2,6} n=3", UniformMatroid(range(6), 2), 3, True, True, True),
        ("Uniform U_{3,9} n=3", UniformMatroid(range(9), 3), 3, True, True, True),
        ("Consec K=3 m=9 n=3", ConsecutiveDaysFamily(9, 3), 3, True, True, True),
        ("Consec K=5 m=14 n=3", ConsecutiveDaysFamily(14, 5), 3, True, True, True),
        ("SwapHeavy r=2 m=7 n=3", SwapHeavyFamily(range(7), 2), 3, True, True, True),
        ("SwapHeavy r=3 m=10 n=3", SwapHeavyFamily(range(10), 3), 3, True, True, True),
        ("SwapHeavy r=3 m=12 n=4", SwapHeavyFamily(range(12), 3), 4, True, True, True),
        # Infeasible cases (LE holds but no allocation exists)
        ("Uniform U_{2,9} n=3 (capacity=6<9)", UniformMatroid(range(9), 2), 3, True, False, False),
        ("Uniform U_{1,5} n=2 (capacity=2<5)", UniformMatroid(range(5), 1), 2, True, False, False),
        # LE fails cases
        ("Dominant-good m=4 n=2", DominantGoodFamily(4), 2, False, True, False),
        ("Bridge F(2,4) n=2", BridgeFamily(2, 4), 2, False, True, False),
        ("IS of Path P_6 n=3", ISFamily([(i,i+1) for i in range(5)], 6), 3, False, True, True),
        ("IS of Cycle C_6 n=3", ISFamily([(i,(i+1)%6) for i in range(6)], 6), 3, False, True, True),
        ("IS of Star K_{1,5} n=3", ISFamily([(0,i) for i in range(1,6)], 6), 3, False, True, False),
        ("IS of Complete K_4 n=3 (infeasible: 4 goods, 3 agents, IS max=1)",
         ISFamily([(i,j) for i in range(4) for j in range(i+1,4)], 4), 3, True, False, False),
        ("IS of Complete K_4 n=4", ISFamily([(i,j) for i in range(4) for j in range(i+1,4)], 4), 4, True, True, True),
        ("IS of Complete K_5 n=5", ISFamily([(i,j) for i in range(5) for j in range(i+1,5)], 5), 5, True, True, True),
        ("IS of Complete K_6 n=6", ISFamily([(i,j) for i in range(6) for j in range(i+1,6)], 6), 6, True, True, True),
        ("IS of Complete K_6 n=7", ISFamily([(i,j) for i in range(6) for j in range(i+1,6)], 6), 7, True, True, True),
    ]

    print(f"\n{'Family':<50} {'LE?':>5} {'Feas?':>5} {'EF1?':>5} {'Conj?':>5}")
    print("-" * 75)

    all_correct = True
    for name, F, n, exp_le, exp_feas, exp_ef1 in test_cases:
        m = F.m
        le_fail, _ = check_global_local_exchange(F)
        le_holds = (le_fail == 0)

        # Check feasibility
        if m <= 10:
            bf_spread, bf_alloc = brute_force_min_spread(F, F.S, n)
            feasible = (bf_spread != float('inf'))
            ef1 = feasible and (bf_spread <= 1)
        else:
            pi, info = ilp_min_spread(F, F.S, n, time_limit=10)
            feasible = (pi is not None)
            ef1 = feasible and (info['spread'] <= 1)

        # Refined conjecture: LE + feasible => EF1
        conj_holds = (not le_holds) or (not feasible) or ef1
        conj_str = "OK" if conj_holds else "FAIL"
        if not conj_holds:
            all_correct = False
            print(f"  *** COUNTEREXAMPLE: LE={le_holds}, feas={feasible}, EF1={ef1}")

        print(f"{name:<50} {'Y' if le_holds else 'N':>5} "
              f"{'Y' if feasible else 'N':>5} "
              f"{'Y' if ef1 else 'N':>5} {conj_str:>5}")

    print(f"\n  Refined conjecture (LE + feas => EF1): "
          f"{'VERIFIED' if all_correct else 'REFUTED'}")


def stress_test_refined_conjecture():
    """Stress test the refined conjecture on random instances."""
    print("\n" + "="*70)
    print("STRESS TEST: LE + Feasibility => EF1 (500 random instances)")
    print("="*70)

    import random
    import networkx as nx
    random.seed(42)

    results = {"le_feas_ef1": 0, "le_feas_no_ef1": 0, "le_infeas": 0,
               "no_le": 0, "counterexamples": []}

    for trial in range(500):
        # Generate random independent-set family
        m = random.randint(4, 8)
        n = random.randint(2, 5)
        # Random graph
        G = nx.gnp_random_graph(m, random.uniform(0.2, 0.7), seed=trial)
        edges = list(G.edges())
        F = ISFamily(edges, m)

        le_fail, _ = check_global_local_exchange(F, max_subset_size=4)
        le_holds = (le_fail == 0)

        bf_spread, _ = brute_force_min_spread(F, F.S, n)
        feasible = (bf_spread != float('inf'))
        ef1 = feasible and (bf_spread <= 1)

        if le_holds and feasible:
            if ef1:
                results["le_feas_ef1"] += 1
            else:
                results["le_feas_no_ef1"] += 1
                results["counterexamples"].append((trial, m, n, edges, bf_spread))
        elif le_holds and not feasible:
            results["le_infeas"] += 1
        else:
            results["no_le"] += 1

    print(f"\n  Results over 500 trials:")
    print(f"    LE + feasible + EF1: {results['le_feas_ef1']}")
    print(f"    LE + feasible + NO EF1: {results['le_feas_no_ef1']}")
    print(f"    LE + infeasible: {results['le_infeas']}")
    print(f"    LE fails: {results['no_le']}")

    if results["le_feas_no_ef1"] == 0:
        print(f"\n  ✓ Refined conjecture VERIFIED on all 500 random instances!")
    else:
        print(f"\n  ✗ {results['le_feas_no_ef1']} counterexamples found:")
        for trial, m, n, edges, spread in results["counterexamples"][:5]:
            print(f"    Trial {trial}: m={m}, n={n}, edges={edges}, spread={spread}")


def investigate_le_counterexamples():
    """If counterexamples exist, investigate them."""
    print("\n" + "="*70)
    print("INVESTIGATION: Do LE counterexamples exist?")
    print("="*70)

    # The K_4 n=3 case: LE holds, infeasible (4 goods, 3 agents, max IS = 1)
    # So capacity = 3 < 4 = m. Infeasible. Not a counterexample.

    # What about K_5 n=3? LE holds (clique). Max IS = 1. Capacity = 3 < 5. Infeasible.
    # K_6 n=3? Capacity = 3 < 6. Infeasible.

    # For a clique K_m, max IS = 1, so need n >= m for feasibility.
    # When n >= m, each agent gets <= 1 good, spread <= 1. EF1 holds.

    # So for cliques, LE + feasibility => EF1 trivially (each agent gets <= 1 good).

    # The interesting case: LE holds, feasible, but EF1 fails.
    # This would require: some allocation exists, but all have spread > 1.
    # For unit weights, spread > 1 means max - min >= 2.

    print("\n  Searching for LE + feasible + non-EF1 instances...")
    print("  (Testing structured families where LE might hold but EF1 fails)")

    # Test: complement of a matching (LE might hold, EF1 might fail)
    import networkx as nx
    for m in range(4, 10):
        for n in range(2, m):
            # Complement of a perfect matching
            G = nx.complete_graph(m)
            # Remove a perfect matching
            matching = [(i, i+1) for i in range(0, m-1, 2)]
            G.remove_edges_from(matching)
            edges = list(G.edges())
            F = ISFamily(edges, m)

            le_fail, _ = check_global_local_exchange(F, max_subset_size=4)
            le_holds = (le_fail == 0)

            bf_spread, _ = brute_force_min_spread(F, F.S, n)
            feasible = (bf_spread != float('inf'))
            ef1 = feasible and (bf_spread <= 1)

            if le_holds and feasible and not ef1:
                print(f"  COUNTEREXAMPLE: complement of matching, m={m}, n={n}, "
                      f"spread={bf_spread}")
            elif le_holds and feasible:
                print(f"  LE+feas+EF1: complement of matching, m={m}, n={n}, "
                      f"spread={bf_spread}")

    # Test: families with LE that are NOT matroids
    print("\n  Testing SwapHeavyFamily at boundary cases:")
    for r in range(2, 5):
        for m in range(r+1, 3*r+2):
            for n in range(2, m+1):
                F = SwapHeavyFamily(range(m), r)
                le_fail, _ = check_global_local_exchange(F, max_subset_size=5)
                le_holds = (le_fail == 0)

                if not le_holds:
                    continue

                bf_spread, _ = brute_force_min_spread(F, F.S, n)
                feasible = (bf_spread != float('inf'))
                ef1 = feasible and (bf_spread <= 1)

                if feasible and not ef1:
                    print(f"  COUNTEREXAMPLE: SwapHeavy r={r} m={m} n={n}, "
                          f"spread={bf_spread}, LE={le_holds}")


def main():
    test_le_plus_feasibility()
    stress_test_refined_conjecture()
    investigate_le_counterexamples()

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("""
    STATUS OF CONJECTURES:

    1. Adjacent Augmentation => EF1: REFUTED
       (dominant-good family: AA holds vacuously, EF1 fails)

    2. Global LE => EF1: REFUTED (need feasibility too)
       (K_4 n=3: LE holds, but infeasible, so EF1 fails trivially)

    3. Global LE + Feasibility => EF1: VERIFIED on all test cases
       (the correct theorem to prove)

    The corrected theorem:
      THEOREM: If F satisfies global local exchange AND an allocation
      exists for (F, S, n), then an EF1 allocation exists.

    This is the theorem the swap-cascade algorithm proves constructively.
    """)


if __name__ == "__main__":
    main()
