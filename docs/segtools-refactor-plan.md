# `segtools.py` Refactor Plan

## Goal

`segtools.py` currently mixes:

- CLI interaction
- array processing logic
- file loading/saving
- rollback state

That is acceptable for a terminal workflow, but it blocks clean API integration. This document defines how to refactor the file so its core processing becomes reusable from a backend service.

## Current Constraints

Observed patterns in the current file:

- many functions prompt users with `input_choice`, `input_int`, `input_float`
- execution flow and menu logic live in the same file as image processing functions
- saving and backup behavior is triggered directly inside the CLI workflow
- rollback is held in a global in-memory structure

These patterns make it hard to:

- call functions from HTTP endpoints
- preview operations without saving
- validate parameters structurally
- reuse logic in tests

## Refactor Target

Split the current script into four layers.

## 1. Pure Processing Layer

This layer should only operate on arrays and typed parameters.

Characteristics:

- no `input()`
- no `print()` except maybe optional debug hooks
- no file I/O
- input: `numpy` arrays and explicit parameter objects
- output: result array plus operation summary

Examples of target signatures:

```python
def remove_isolated(data: np.ndarray, target: str) -> tuple[np.ndarray, dict]:
    ...

def smooth_label(
    data: np.ndarray,
    target: int,
    zooms: tuple[float, float, float],
    sigma: float,
    close_iter: int,
    open_iter: int,
    keep_n: int | None = None,
) -> tuple[np.ndarray, dict]:
    ...
```

## 2. Parameter Schema Layer

Introduce structured parameter models for each operation.

Recommended options:

- plain `dataclass`
- `pydantic` models once FastAPI is added

Examples:

```python
@dataclass
class ExpandParams:
    target_label: int
    mode: str
    threshold: float | None = None
    tolerance: float | None = None
    iterations: int = 5
```

Benefits:

- removes ad hoc parsing
- enables API validation
- makes defaults explicit

## 3. Service Layer

This layer adapts pure processing functions to session-oriented backend use.

Responsibilities:

- fetch current session volume
- load CT when needed
- apply optional region restriction
- push undo history
- store operation summary
- return changed voxel count and metadata

This becomes the main backend entry point for post-processing.

## 4. CLI Layer

Keep the terminal workflow, but move it to a thinner wrapper.

Responsibilities:

- prompt users
- convert prompt results into structured params
- call service or pure processing layer
- print summaries
- save files

This preserves current usability while removing backend blockers.

## Recommended Module Split

Instead of keeping everything in one file, move logic into modules such as:

```text
backend/app/core/
  labels.py
  coordinate.py
  history.py

backend/app/services/
  postprocess_service.py

backend/app/processing/
  analyze.py
  cleanup.py
  smooth.py
  expand.py
  trim.py
  fill.py
  merge.py
  compare.py
  region.py
```

If a full module split is too large for the first pass, an intermediate step is acceptable:

- keep `segtools.py`
- extract reusable processing functions into `segtools_core.py`
- keep CLI prompts in `segtools.py`

## Concrete Refactor Steps

### Step 1: Extract Common Types and Constants

Pull out:

- label metadata
- function registry metadata
- operation names
- reusable summaries

This avoids repeated dictionaries inside individual functions.

### Step 2: Separate Input Parsing from Processing

For each function:

- keep the current prompt logic temporarily in wrapper functions
- create a new pure function that accepts validated parameters

Pattern:

```python
def func_remove_high_intensity(data, ct_data=None, **kwargs):
    threshold = input_int(...)
    return remove_high_intensity(data, ct_data, threshold=threshold)

def remove_high_intensity(data, ct_data, threshold):
    ...
```

### Step 3: Return Structured Summaries

Processing functions should return:

- result array
- changed voxel count
- optional label stats
- optional bounding box

This is important for API responses and UI history.

### Step 4: Isolate File I/O

Move these concerns into dedicated helpers:

- case loading
- backup creation
- NIfTI save
- CT lazy loading

The core processing functions should never call `nib.load` or `nib.save`.

### Step 5: Replace Global Rollback with History Object

Current global:

- `rollback_history = {}`

Target:

- session-specific history stack object
- explicit push/pop behavior
- no implicit global state

## Priority Order

The best order for extraction is:

1. `func_remove_isolated`
2. `func_remove_low_intensity`
3. `func_remove_high_intensity`
4. `func_fill_holes`
5. `func_smooth`
6. `func_expand`
7. `func_trim_boundary`
8. `func_label_convex`
9. region-restricted execution helpers

Reason:

- early functions are simpler and good for establishing the pattern
- later functions depend more on CT, zooms, or region handling

## Compatibility Strategy

During transition:

- keep the current CLI behavior working
- avoid changing algorithm semantics unless necessary
- compare old and new outputs on a sample case when possible

Suggested transitional structure:

```text
segtools.py
segtools_core.py
```

Where:

- `segtools.py` remains the interactive menu entrypoint
- `segtools_core.py` becomes reusable by FastAPI services

## Testing Recommendations

When refactoring, add tests for:

- output shape preservation
- unchanged behavior when parameters match current defaults
- label protection rules
- region-restricted application boundaries
- undo stack behavior at service level

Even a small fixture-based test set will greatly reduce risk.

## Deliverables for the First Refactor Pass

- extract at least 3 to 5 simple operations into pure functions
- define parameter models for those operations
- define a reusable operation summary shape
- keep the current CLI entrypoint functional

That first pass is enough to unlock the FastAPI backend skeleton.

## Working Checklist Reference

For day-to-day implementation tracking, use [implementation-checklist.md](./implementation-checklist.md).

Recommended immediate execution order:

1. shared types/constants
2. first-pass pure function extraction
3. transitional `segtools_core.py` structure
4. initial regression tests
5. backend skeleton
