# Frontend Integration Architecture

## Goal

This project already has strong segmentation post-processing logic in `segtools.py`. The next stage is to add an interactive frontend that lets users:

- inspect CT and segmentation overlays
- edit segmentation with brush, erase, and polygon tools
- run post-processing functions with parameter controls
- apply operations to selected regions and review the result

The recommended architecture is a React frontend backed by a FastAPI service that wraps the current Python processing code.

## Recommended Stack

- Backend: `FastAPI`
- Frontend: `React + Vite + TypeScript`
- State management: `Zustand`
- Rendering: custom 2D `canvas` viewer for axial/coronal/sagittal slices
- Volume processing: existing `numpy`, `scipy`, `nibabel`

This keeps the system aligned with the current Python-based codebase and avoids over-investing in a heavy medical viewer stack too early.

## High-Level Structure

```text
[React Frontend]
  - Viewer
  - Tool panels
  - Phase/case browser
  - History and save controls

        HTTP / WebSocket (optional later)

[FastAPI Backend]
  - Case/session APIs
  - Slice rendering APIs
  - Editing APIs
  - Post-processing APIs
  - Save/undo/redo APIs

[Core Processing Layer]
  - NIfTI loading
  - Coordinate transforms
  - Slice rendering
  - Mask editing
  - segtools wrappers
  - history management
```

## Suggested Repository Layout

```text
docs/
  frontend-architecture.md
  api-draft.md
  frontend-component-tree.md
  segtools-refactor-plan.md

backend/
  app/
    main.py
    api/
    core/
    services/
    schemas/

frontend/
  src/
    components/
    features/
    stores/
    api/
    types/
```

## Core Responsibilities

### Frontend

- display CT slices and segmentation overlays
- manage tool selection and parameter input
- collect user interactions such as brush strokes, polygon vertices, and seed clicks
- request preview/apply actions from backend
- reflect undo/redo and save state

### Backend

- load CT and segmentation volumes
- maintain working session state
- render requested slices with window/level
- apply editing operations to segmentation masks
- run post-processing functions against the current working mask
- save results back to `.nii.gz`

## Data Model Overview

### Case

- `caseId`
- available phases such as `A`, `D`, `P`
- CT file path
- segmentation file path
- shape, spacing, affine

### Session

- `sessionId`
- selected `caseId` and `phase`
- in-memory CT reference
- working segmentation array
- undo stack
- redo stack
- dirty flag

### Operations

- edit operations: brush, erase, polygon fill, connected fill
- post-processing operations: smoothing, expand, trim, convex hull, region-restricted run

## Phased Implementation Plan

### Phase 1: Viewer + Manual Editing MVP

- case and phase selection
- axial viewer
- CT + segmentation overlay
- label visibility and opacity control
- brush, erase, polygon
- undo/redo
- save

### Phase 2: Post-Processing Integration

- parameter forms for selected functions
- preview/apply split
- slice-range and bounding-box region restriction
- history log

### Phase 3: Advanced Workflow

- coronal and sagittal viewers
- seed-based convex hull workflow
- phase comparison UI
- optional 3D editing helpers

## Key Risks

### Coordinate Consistency

The most important technical risk is mismatch between:

- on-screen coordinates
- slice coordinates
- voxel indices in the stored segmentation
- orientation from affine/axis interpretation

All mapping logic should live in one backend module and one frontend viewer utility layer.

### Performance

Main expected bottlenecks:

- large NIfTI volumes in memory
- repeated slice rendering
- undo/redo snapshot size

Start simple with in-memory session volumes and full snapshots, then optimize if needed.

## Relationship to `segtools.py`

`segtools.py` should remain the source of truth for segmentation operations, but it needs to be refactored so that:

- processing logic is callable without `input()`
- file save/load logic is separated from array processing
- functions can be executed by backend services with structured parameters

See [segtools-refactor-plan.md](./segtools-refactor-plan.md) for the detailed approach.
