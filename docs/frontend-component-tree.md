# Frontend Component Tree

## Goal

This document defines the recommended frontend component structure for the CT viewer and segmentation editor.

The design assumes:

- React + TypeScript
- a session-oriented API
- initial focus on 2D slice editing

## App Structure

```text
App
  AppShell
    TopBar
    LeftSidebar
      CaseBrowser
      PhaseTabs
      LabelPanel
    MainWorkspace
      ViewerWorkspace
        ViewerHeader
        Viewer2D
          SliceCanvas
          OverlayCanvas
          InteractionLayer
          Crosshair
        SliceNavigator
      BottomPanel
        HistoryPanel
        StatusBar
    RightSidebar
      ToolBar
      ToolOptionsPanel
        BrushPanel
        PolygonPanel
        InspectPanel
      PostprocessPanel
```

## Component Responsibilities

### `App`

- bootstraps stores
- loads route-level state if routing is added later

### `AppShell`

- overall desktop layout
- responsive behavior for narrow screens

### `TopBar`

- current case and phase
- session save state
- undo / redo
- window / level controls
- future settings entry point

### `CaseBrowser`

- list available cases
- open selected case

### `PhaseTabs`

- switch among `A`, `D`, `P`
- show CT availability status

### `LabelPanel`

- label visibility toggles
- label color chips
- overlay opacity
- active editing label

### `ViewerWorkspace`

- central viewing area
- owns active axis and slice controls

### `Viewer2D`

- composes CT render and segmentation overlay
- handles zoom, pan, hover, click, drag
- dispatches edit actions based on active tool

### `SliceCanvas`

- renders CT slice image only

### `OverlayCanvas`

- renders segmentation colors
- displays temporary edit preview

### `InteractionLayer`

- mouse and pointer event layer
- brush cursor
- polygon points and outline
- hover coordinate display

### `SliceNavigator`

- previous/next slice controls
- slider input
- slice index readout

### `HistoryPanel`

- operation list
- changed voxel counts
- session messages such as save complete

### `StatusBar`

- voxel coordinate under cursor
- current HU estimate if available
- active label and active tool

### `ToolBar`

- pan
- zoom
- inspect
- brush
- erase
- polygon

### `ToolOptionsPanel`

Shows the option panel matching the active tool.

### `BrushPanel`

- brush size
- paint vs erase
- overwrite toggle
- preserve-label selection
- future 2D/3D brush switch

### `PolygonPanel`

- close polygon
- fill vs erase
- overwrite toggle
- preserve-label selection

### `InspectPanel`

- read-only voxel/label/CT value display

### `PostprocessPanel`

- function selector
- dynamic parameter form
- optional region controls
- preview and apply buttons

## Feature-Level Organization

Recommended source layout:

```text
frontend/src/
  app/
    App.tsx
    AppShell.tsx
  components/
    viewer/
    sidebar/
    toolbar/
    panels/
  features/
    cases/
    session/
    viewer/
    editor/
    postprocess/
  stores/
    viewerStore.ts
    editorStore.ts
    sessionStore.ts
  api/
    client.ts
    cases.ts
    session.ts
    viewer.ts
    edit.ts
    postprocess.ts
  types/
    api.ts
    viewer.ts
    editor.ts
```

## Store Design

### `viewerStore`

- `axis`
- `sliceIndex`
- `zoom`
- `pan`
- `window`
- `level`
- `overlayOpacity`
- `visibleLabels`

### `editorStore`

- `activeTool`
- `activeLabel`
- `brushRadius`
- `polygonVertices`
- `overwrite`
- `preserveLabels`
- `isDrawing`

### `sessionStore`

- `sessionId`
- `caseId`
- `phase`
- `dirty`
- `canUndo`
- `canRedo`
- `lastOperationSummary`

## Interaction Flows

### Brush

1. User selects `Brush`
2. User presses and drags on the viewer
3. `InteractionLayer` collects points
4. Local preview is drawn on overlay
5. On pointer up, stroke is committed through `/edit/brush`
6. Viewer refreshes the current slice

### Polygon

1. User selects `Polygon`
2. User clicks vertices
3. Preview outline is rendered
4. User closes polygon with double-click or explicit action
5. Polygon is sent to `/edit/polygon`
6. Viewer refreshes the current slice

### Post-Processing

1. User selects a function
2. UI renders function-specific parameters
3. User optionally defines a region
4. Preview request is sent
5. User reviews summary
6. User applies the operation

## MVP Component Cut

The first implementation should include:

- `AppShell`
- `TopBar`
- `CaseBrowser`
- `PhaseTabs`
- `LabelPanel`
- `Viewer2D`
- `SliceCanvas`
- `OverlayCanvas`
- `InteractionLayer`
- `SliceNavigator`
- `ToolBar`
- `BrushPanel`
- `PolygonPanel`
- `HistoryPanel`

`PostprocessPanel` can arrive in the second pass after manual editing is stable.
