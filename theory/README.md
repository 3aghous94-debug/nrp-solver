# Theory Scripts

This directory contains the research scripts used to develop and verify the
theoretical results in `docs/PROOFS.md`, `docs/REFUTATIONS.md`, and
`docs/EXPERIMENTAL_RESULTS.md`.

## ⚠️ Reproducibility note

Several scripts in this directory import modules that are **not included** in
the public release:

- `local_exchange_ef1.py` (the swap-cascade algorithm and LE verification)
- `bfp_solver_toolkit.py` (ILP-based BFP solver)
- `weighted_extension.py` (LPT round-robin and weighted LE)
- `dwec_algorithm.py` (the original DWEC implementation)
- `fixed_le_algorithm.py` (the fixed LE algorithm with envy-cycle rotation)

These modules were part of an earlier development branch and were consolidated
into the `nrp_solver/` package during the productionisation process. The
verification scripts in `theory/` still reference them by their original names.

**What this means:**

- The "56/56 verified", "256/256 verified", "31/31 verified" numbers in
  `docs/EXPERIMENTAL_RESULTS.md` are **not reproducible** from the public
  release without reconstructing the missing modules.
- The "359/359 verified" number IS reproducible via `theory/dwec_verification.py`
  after vendoring the missing modules (see below).
- The production solver in `nrp_solver/core.py` is the consolidated, tested
  version of these research scripts.

## How to reproduce the verification numbers

### Option A: Vendor the missing modules (recommended for researchers)

The missing modules can be reconstructed from the algorithm descriptions in
`docs/PROOFS.md` and `docs/ALGORITHM_DEVELOPMENT.md`. The key modules are:

1. **`local_exchange_ef1.py`**: Implements the swap-cascade algorithm
   (Section 11 of RESEARCH.md, Section 1 of PROOFS.md). Contains:
   - `FeasibilityFamily` (abstract base class)
   - `UniformMatroid`, `GraphicMatroid`, `PartitionMatroid`
   - `BridgeFamily`, `ConsecutiveDaysFamily`
   - `local_exchange_ef1()` (the algorithm)
   - `brute_force_min_spread()`

2. **`bfp_solver_toolkit.py`**: ILP-based BFP solver using PuLP/CBC.
   Contains `ilp_min_spread()`.

3. **`weighted_extension.py`**: LPT round-robin and weighted LE.
   Contains `lpt_round_robin()`, `brute_force_min_weighted_spread()`.

4. **`dwec_algorithm.py`**: The original DWEC implementation (now in
   `nrp_solver/core.py:DWECBackend`).

### Option B: Use the production solver

The production `nrp_solver` package includes all the algorithms. To verify
the spread bound on random instances:

```python
from nrp_solver.core import NRPInstance, DWECBackend
import random

random.seed(42)
violations = 0
tested = 0
for trial in range(200):
    # ... construct random instance ...
    result = DWECBackend().solve(instance)
    if result.feasible and result.coverage_ok:
        tested += 1
        if result.spread > instance.w_max + 1e-9:
            violations += 1
print(f"{tested} feasible, {violations} spread violations")
```

## Scripts in this directory

| Script | Purpose | Reproducible? |
|---|---|---|
| `local_exchange_ef1.py` | Swap-cascade algorithm, LE verification | ✅ (standalone) |
| `weighted_extension.py` | LPT round-robin, Theorem D.1 | ⚠️ (imports `local_exchange_ef1`) |
| `weighted_verification.py` | Theorem D.1 stress test (256 instances) | ⚠️ (imports `weighted_extension`) |
| `formal_proofs.py` | Formal proofs with computational checks | ⚠️ (imports multiple modules) |
| `test_aa_conjecture.py` | AA conjecture refutation | ⚠️ (imports `local_exchange_ef1`) |
| `refined_conjecture.py` | LE + feasibility ⟹ EF1, Hajnal–Szemerédi | ⚠️ (imports multiple modules) |
| `dwec_verification.py` | DWEC stress test (359 instances) | ⚠️ (imports `dwec_algorithm`) |
| `per_agent_dwec.py` | Per-agent (skill mix) extension | ⚠️ (imports `local_exchange_ef1`) |
| `coverage_dwec.py` | Coverage constraints extension | ⚠️ (imports `local_exchange_ef1`) |
| `nsplib_validation.py` | NSPLib-style benchmark validation | ⚠️ (imports `local_exchange_ef1`) |
| `separator_analysis.py` | Separator imbalance refutation | ⚠️ (imports `local_exchange_ef1`) |
| `we_equivalence.py` | Weight-exchange vacuousness | ⚠️ (imports multiple modules) |

The standalone scripts (`local_exchange_ef1.py`) can be run directly. The
others require the missing modules to be vendored or reconstructed.

## Relationship to the production solver

The production solver (`nrp_solver/core.py`) is the consolidated version of
these research scripts, with:

- Bug fixes from the peer review process (see git history)
- Production-quality error handling and infeasibility detection
- Coverage constraints, skill mix, and availability extensions
- A clean public API

The research scripts are preserved here for historical reference and to
document the algorithmic development process described in
`docs/ALGORITHM_DEVELOPMENT.md`.
