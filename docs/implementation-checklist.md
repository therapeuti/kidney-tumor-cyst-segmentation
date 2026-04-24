# Implementation Checklist

## How to Use This Document

- This is the working checklist for the frontend + backend integration project.
- Items should be checked as implementation progresses.
- The order here is the recommended execution order unless a specific task needs to be pulled forward.

## Current Status

- [x] Initial architecture design documented
- [x] API draft documented
- [x] Frontend component tree documented
- [x] `segtools.py` refactor plan documented
- [x] First reusable post-processing functions extracted
- [x] Backend skeleton created
- [x] Frontend skeleton created
- [x] Viewer MVP working
- [x] Manual editing MVP working
- [x] Post-processing UI connected

## Phase 0. Planning and Baseline

### Documentation

- [x] Create architecture overview document
- [x] Create backend API draft
- [x] Create frontend component tree design
- [x] Create `segtools.py` refactor plan
- [x] Create implementation checklist

### Baseline Review

- [x] Confirm target folder structure for `backend/` and `frontend/`
- [x] Confirm Python dependency strategy for backend
- [x] Confirm Node package strategy for frontend
- [x] Identify one sample case for regression testing during refactor

## Phase 1. `segtools.py` First Refactor Pass

Goal: unlock backend reuse without breaking the current CLI workflow.

### 1.1 Shared Types and Constants

- [x] Extract label metadata into reusable constants
- [x] Extract function registry metadata into reusable constants
- [x] Define reusable operation summary shape
- [x] Add parameter models for first-pass operations

### 1.2 Extract First Pure Functions

- [x] Extract `remove_isolated` pure processing function
- [x] Extract `remove_low_intensity` pure processing function
- [x] Extract `remove_high_intensity` pure processing function
- [x] Extract `fill_holes` pure processing function
- [x] Keep existing CLI wrappers working

### 1.3 Transitional Structure

- [x] Create `segtools_core.py` or equivalent processing module
- [x] Move first-pass pure functions into the core module
- [x] Update `segtools.py` to call extracted functions
- [x] Keep output behavior functionally equivalent for CLI use

### 1.4 Initial Tests

- [x] Add tests for output shape preservation
- [x] Add tests for no-CT-required and CT-required operations
- [x] Add tests for changed voxel counts or equivalent summaries
- [x] Run first regression pass on at least one sample case

## Phase 2. Backend Skeleton

Goal: make the extracted processing logic callable through API endpoints.

### 2.1 Project Structure

- [x] Create `backend/app/`
- [x] Create `backend/app/api/`
- [x] Create `backend/app/core/`
- [x] Create `backend/app/services/`
- [x] Create `backend/app/schemas/`
- [x] Add backend dependency file

### 2.2 Core Backend Utilities

- [x] Implement case discovery utility
- [x] Implement NIfTI load/save helper
- [x] Implement session store
- [x] Implement history manager
- [x] Implement label metadata module

### 2.3 First API Endpoints

- [x] Implement `GET /api/cases`
- [x] Implement `GET /api/cases/{caseId}`
- [x] Implement `POST /api/sessions`
- [x] Implement `GET /api/sessions/{sessionId}`
- [x] Implement `POST /api/sessions/{sessionId}/save`
- [x] Implement `POST /api/sessions/{sessionId}/undo`
- [x] Implement `POST /api/sessions/{sessionId}/redo`

### 2.4 Backend Validation

- [x] Verify a session can open one case and one phase
- [x] Verify save keeps existing backup behavior
- [x] Verify undo/redo works with full snapshots

## Phase 3. Viewer APIs

Goal: provide enough slice-level data for a frontend viewer.

### 3.1 Metadata and Slice Endpoints

- [x] Implement `GET /api/sessions/{sessionId}/meta`
- [x] Implement `GET /api/sessions/{sessionId}/slice`
- [x] Implement `GET /api/sessions/{sessionId}/slice-image`

### 3.2 Slice Rendering

- [x] Implement window/level rendering for CT slices
- [x] Implement mask slice extraction
- [x] Decide initial mask transport format
- [x] Validate axial view rendering on a real case

### 3.3 Coordinate Utilities

- [x] Add backend axis/slice coordinate mapping helpers
- [x] Validate slice indexing consistency across planes
- [x] Document current orientation assumptions in code comments

## Phase 4. Frontend Skeleton

Goal: establish the UI shell and data flow for one working viewer.

### 4.1 Project Bootstrap

- [x] Create `frontend/` app
- [x] Add TypeScript configuration
- [x] Add API client layer
- [x] Add Zustand stores
- [x] Add base layout and styling setup

### 4.2 Initial Layout

- [x] Implement `AppShell`
- [x] Implement `TopBar`
- [x] Implement `CaseBrowser`
- [x] Implement `PhaseTabs`
- [x] Implement `LabelPanel`
- [x] Implement empty `Viewer2D` shell
- [x] Implement `HistoryPanel`

### 4.3 Frontend API Wiring

- [x] Load case list from backend
- [x] Create and hold active session
- [x] Load session metadata
- [x] Request slice data from backend

## Phase 5. Viewer MVP

Goal: inspect CT and segmentation overlays before editing.

### 5.1 Viewer Rendering

- [x] Implement `SliceCanvas`
- [x] Implement `OverlayCanvas`
- [x] Implement `SliceNavigator`
- [x] Implement label visibility toggles
- [x] Implement overlay opacity control

### 5.2 Viewer Interaction

- [x] Implement mouse coordinate tracking
- [x] Implement slice slider / next-prev navigation
- [x] Implement zoom
- [x] Implement pan
- [x] Implement window/level controls

### 5.3 Viewer Validation

- [x] Verify CT and mask alignment on sample case
- [x] Verify active slice updates correctly
- [x] Verify visible label filtering works

## Phase 6. Manual Editing MVP

Goal: enable practical segmentation correction from the frontend.

### 6.1 Editing Backend

- [x] Implement `/edit/brush`
- [x] Implement `/edit/polygon`
- [x] Add backend edit summaries
- [x] Push undo snapshot on committed edit

### 6.2 Editing Frontend

- [x] Implement `ToolBar`
- [x] Implement `InteractionLayer`
- [x] Implement `BrushPanel`
- [x] Implement `PolygonPanel`
- [x] Implement local brush cursor preview
- [x] Implement polygon outline preview

### 6.3 Editing Features

- [x] Brush paint
- [x] Brush erase
- [x] Polygon fill
- [x] Polygon erase
- [x] Active label selection
- [x] Overwrite toggle
- [x] Preserve-label option

### 6.4 Manual Editing Validation

- [x] Verify edits affect the intended slice only
- [x] Verify undo/redo across edit operations
- [x] Verify save persists edited segmentation

## Phase 7. Post-Processing Integration

Goal: run existing segmentation post-processing from the UI.

### 7.1 Backend Integration

- [x] Implement post-processing function registry for API use
- [x] Implement `GET /api/postprocess/functions`
- [x] Implement `/postprocess/preview`
- [x] Implement `/postprocess/apply`

### 7.2 Refactor Additional Functions

- [x] Extract `smooth`
- [x] Extract `expand`
- [x] Extract `trim_boundary`
- [x] Extract `label_convex`
- [x] Extract region restriction helpers

### 7.3 Frontend Integration

- [x] Implement `PostprocessPanel`
- [x] Render dynamic parameter form from backend metadata
- [x] Add preview/apply flow
- [x] Add operation summary display

### 7.4 Region Tools

- [x] Add slice-range region controls
- [x] Add bounding-box region controls
- [x] Add directional cut region controls

## Phase 8. Advanced Workflow

Goal: move beyond MVP into a stronger annotation workflow.

### Advanced Viewer

- [x] Add coronal view
- [x] Add sagittal view
- [x] Add crosshair synchronization

### Advanced Editing

- [x] Add connected fill tool
- [x] Add slice interpolation helper
- [ ] Evaluate 3D brush support

### Advanced Analysis

- [x] Add phase comparison UI
- [ ] Add seed-based convex hull workflow UI
- [x] Add richer operation history/log panel

## Rules for Updating This Checklist

- Check items only when code or docs are actually added and verified.
- If a task is split further during implementation, add new child tasks near the original item.
- If implementation order changes, keep the checklist updated rather than relying on memory.
