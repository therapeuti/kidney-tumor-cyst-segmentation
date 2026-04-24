# API Draft

## Scope

This document defines the first backend API draft for the interactive CT viewer and segmentation editor.

The API is designed around session-based editing. A session holds an in-memory working segmentation for one case and one phase.

## Conventions

- Base path: `/api`
- Format: JSON unless noted otherwise
- Authentication: not included in MVP
- Session persistence: in-memory during MVP

## 1. Cases

### `GET /api/cases`

Returns the list of available case folders.

Response:

```json
[
  {
    "caseId": "S004",
    "phases": ["A", "D", "P"]
  }
]
```

### `GET /api/cases/{caseId}`

Returns metadata for a case.

Response:

```json
{
  "caseId": "S004",
  "phases": [
    {
      "phase": "A",
      "hasCt": true,
      "shape": [512, 512, 180],
      "spacing": [0.78, 0.78, 3.0],
      "labels": [0, 1, 2, 3]
    }
  ]
}
```

## 2. Sessions

### `POST /api/sessions`

Creates a working session.

Request:

```json
{
  "caseId": "S004",
  "phase": "A"
}
```

Response:

```json
{
  "sessionId": "sess_01",
  "caseId": "S004",
  "phase": "A",
  "dirty": false,
  "canUndo": false,
  "canRedo": false
}
```

### `GET /api/sessions/{sessionId}`

Returns current session status.

### `POST /api/sessions/{sessionId}/save`

Saves the current segmentation to the phase segmentation file, keeping the existing backup behavior.

Response:

```json
{
  "saved": true,
  "dirty": false
}
```

### `POST /api/sessions/{sessionId}/undo`

### `POST /api/sessions/{sessionId}/redo`

Response for both:

```json
{
  "ok": true,
  "dirty": true,
  "canUndo": true,
  "canRedo": false
}
```

## 3. Viewer / Volume Metadata

### `GET /api/sessions/{sessionId}/meta`

Returns volume metadata needed by the viewer.

Response:

```json
{
  "shape": [512, 512, 180],
  "spacing": [0.78, 0.78, 3.0],
  "labels": [
    { "id": 0, "name": "Background", "color": [0, 0, 0, 0] },
    { "id": 1, "name": "Kidney", "color": [80, 170, 255, 180] },
    { "id": 2, "name": "Tumor", "color": [255, 80, 80, 180] },
    { "id": 3, "name": "Cyst", "color": [255, 210, 80, 180] }
  ]
}
```

### `GET /api/sessions/{sessionId}/slice`

Returns CT render and current segmentation slice for one plane.

Query params:

- `axis`: `axial | coronal | sagittal`
- `index`: integer
- `window`: integer
- `level`: integer

Response:

```json
{
  "axis": "axial",
  "index": 120,
  "width": 512,
  "height": 512,
  "ctImageUrl": "/api/sessions/sess_01/slice-image?axis=axial&index=120&window=350&level=40",
  "mask": {
    "encoding": "rle",
    "labels": [0, 1, 2, 3],
    "data": "..."
  }
}
```

Notes:

- MVP can return PNG for CT and raw 2D label arrays for mask if simpler.
- Later optimization can switch mask transport to RLE or PNG overlay.

### `GET /api/sessions/{sessionId}/slice-image`

Returns rendered CT slice image as `image/png`.

## 4. Editing

### `POST /api/sessions/{sessionId}/edit/brush`

Applies one committed brush stroke on a 2D slice.

Request:

```json
{
  "axis": "axial",
  "sliceIndex": 120,
  "points": [[120, 85], [121, 86], [123, 88]],
  "radius": 8,
  "label": 2,
  "mode": "paint",
  "overwrite": false,
  "preserveLabels": [3]
}
```

Response:

```json
{
  "ok": true,
  "changedVoxels": 142,
  "dirty": true,
  "canUndo": true
}
```

### `POST /api/sessions/{sessionId}/edit/polygon`

Fills or erases a polygon on a slice.

Request:

```json
{
  "axis": "axial",
  "sliceIndex": 120,
  "vertices": [[100, 80], [140, 82], [145, 110], [102, 120]],
  "label": 2,
  "mode": "fill",
  "overwrite": false,
  "preserveLabels": [3]
}
```

### `POST /api/sessions/{sessionId}/edit/fill-connected`

Optional next-step endpoint for flood fill / connected fill from a clicked point.

## 5. Post-Processing

### `GET /api/postprocess/functions`

Returns the list of supported functions and their parameter schema.

Response:

```json
[
  {
    "key": "expand",
    "label": "Boundary Expansion",
    "requiresCt": true,
    "supportsRegion": true,
    "params": [
      { "key": "targetLabel", "type": "select", "options": [1, 2, 3] },
      { "key": "mode", "type": "select", "options": ["lower", "range"] },
      { "key": "iterations", "type": "number", "default": 5 }
    ]
  }
]
```

### `POST /api/sessions/{sessionId}/postprocess/preview`

Runs a function against the current session and returns a non-saved preview summary.

Request:

```json
{
  "function": "expand",
  "params": {
    "targetLabel": 2,
    "mode": "range",
    "tolerance": 25,
    "iterations": 3
  },
  "region": {
    "type": "slice_range",
    "axis": "axial",
    "start": 90,
    "end": 130
  }
}
```

Response:

```json
{
  "ok": true,
  "changedVoxels": 482,
  "previewSlices": [101, 102, 103, 104],
  "boundingBox": {
    "min": [120, 80, 101],
    "max": [180, 140, 104]
  }
}
```

### `POST /api/sessions/{sessionId}/postprocess/apply`

Applies the same payload to the working segmentation and pushes undo history.

## 6. Region Selection Payloads

Supported region payloads for editing/post-processing:

### Slice Range

```json
{
  "type": "slice_range",
  "axis": "axial",
  "start": 90,
  "end": 130
}
```

### Bounding Box

```json
{
  "type": "bbox",
  "x": [100, 220],
  "y": [80, 180],
  "z": [90, 130]
}
```

### Half-Space / Directional Cut

```json
{
  "type": "half_space",
  "axis": "sagittal",
  "direction": "negative",
  "cut": 180
}
```

## 7. Error Shape

Recommended error format:

```json
{
  "error": {
    "code": "CT_REQUIRED",
    "message": "This operation requires a CT image for the selected phase."
  }
}
```

## Notes for MVP

- Keep session management simple and in-memory.
- Use full segmentation snapshots for undo/redo first.
- Prefer a small stable API over a larger speculative one.
- If preview is expensive, preview can initially return metadata only instead of a full temp volume.
