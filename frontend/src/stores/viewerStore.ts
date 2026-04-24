import { create } from "zustand";

export type ViewerAxis = "axial" | "coronal" | "sagittal";
export type ViewLayout = "single" | "multi";

type PerAxisState = {
  sliceIndex: number;
  zoom: number;
  pan: { x: number; y: number };
};

type ViewerStore = {
  // Layout mode
  layout: ViewLayout;
  setLayout: (layout: ViewLayout) => void;

  // Active axis (used in single-view mode and as "primary" in multi-view)
  axis: ViewerAxis;
  setAxis: (axis: ViewerAxis) => void;

  // Per-axis slice indices (used in multi-view)
  axialState: PerAxisState;
  coronalState: PerAxisState;
  sagittalState: PerAxisState;

  // Convenience: get/set sliceIndex for current axis (single-view compat)
  sliceIndex: number;
  setSliceIndex: (sliceIndex: number) => void;

  // Set slice index for a specific axis
  setAxisSliceIndex: (axis: ViewerAxis, sliceIndex: number) => void;

  // Zoom/pan for current axis in single mode
  zoom: number;
  pan: { x: number; y: number };
  setZoom: (zoom: number) => void;
  adjustZoom: (delta: number) => void;
  setPan: (pan: { x: number; y: number }) => void;
  adjustPan: (delta: { x: number; y: number }) => void;
  resetView: () => void;

  // Per-axis zoom/pan
  setAxisZoom: (axis: ViewerAxis, zoom: number) => void;
  adjustAxisZoom: (axis: ViewerAxis, delta: number) => void;
  setAxisPan: (axis: ViewerAxis, pan: { x: number; y: number }) => void;
  adjustAxisPan: (axis: ViewerAxis, delta: { x: number; y: number }) => void;
  resetAxisView: (axis: ViewerAxis) => void;

  // Crosshair: 3D voxel coordinate synced across views
  crosshair: { x: number; y: number; z: number } | null;
  setCrosshair: (point: { x: number; y: number; z: number } | null) => void;

  // Shared state
  hoverPoint: { x: number; y: number } | null;
  setHoverPoint: (point: { x: number; y: number } | null) => void;
  clickedVoxel: { label: number; hu: number | null } | null;
  setClickedVoxel: (voxel: { label: number; hu: number | null } | null) => void;
  window: number;
  level: number;
  setWindow: (window: number) => void;
  setLevel: (level: number) => void;
  overlayOpacity: number;
  setOverlayOpacity: (opacity: number) => void;
  visibleLabels: number[];
  toggleVisibleLabel: (label: number) => void;
};

function axisStateKey(axis: ViewerAxis): "axialState" | "coronalState" | "sagittalState" {
  if (axis === "axial") return "axialState";
  if (axis === "coronal") return "coronalState";
  return "sagittalState";
}

function getAxisState(state: ViewerStore, axis: ViewerAxis): PerAxisState {
  return state[axisStateKey(axis)];
}

const defaultPerAxis: PerAxisState = { sliceIndex: 0, zoom: 1, pan: { x: 0, y: 0 } };

export const useViewerStore = create<ViewerStore>((set, get) => ({
  layout: "single",
  setLayout: (layout) => set({ layout }),

  axis: "axial",
  setAxis: (axis) => {
    const s = getAxisState(get(), axis);
    set({ axis, sliceIndex: s.sliceIndex, zoom: s.zoom, pan: s.pan });
  },

  axialState: { ...defaultPerAxis },
  coronalState: { ...defaultPerAxis },
  sagittalState: { ...defaultPerAxis },

  sliceIndex: 0,
  setSliceIndex: (sliceIndex) => {
    const axis = get().axis;
    set({ sliceIndex, [axisStateKey(axis)]: { ...getAxisState(get(), axis), sliceIndex } });
  },

  setAxisSliceIndex: (axis, sliceIndex) => {
    const update: Partial<ViewerStore> = { [axisStateKey(axis)]: { ...getAxisState(get(), axis), sliceIndex } };
    if (axis === get().axis) {
      update.sliceIndex = sliceIndex;
    }
    set(update as Partial<ViewerStore>);
  },

  zoom: 1,
  pan: { x: 0, y: 0 },
  setZoom: (zoom) => {
    const axis = get().axis;
    set({ zoom, [axisStateKey(axis)]: { ...getAxisState(get(), axis), zoom } });
  },
  adjustZoom: (delta) => {
    const state = get();
    const zoom = Math.max(0.5, Math.min(6, Number((state.zoom + delta).toFixed(2))));
    set({ zoom, [axisStateKey(state.axis)]: { ...getAxisState(state, state.axis), zoom } });
  },
  setPan: (pan) => {
    const axis = get().axis;
    set({ pan, [axisStateKey(axis)]: { ...getAxisState(get(), axis), pan } });
  },
  adjustPan: (delta) => {
    const state = get();
    const pan = { x: state.pan.x + delta.x, y: state.pan.y + delta.y };
    set({ pan, [axisStateKey(state.axis)]: { ...getAxisState(state, state.axis), pan } });
  },
  resetView: () => {
    const axis = get().axis;
    set({ zoom: 1, pan: { x: 0, y: 0 }, [axisStateKey(axis)]: { ...getAxisState(get(), axis), zoom: 1, pan: { x: 0, y: 0 } } });
  },

  setAxisZoom: (axis, zoom) => {
    const clamped = Math.max(0.5, Math.min(6, zoom));
    const update: Partial<ViewerStore> = { [axisStateKey(axis)]: { ...getAxisState(get(), axis), zoom: clamped } };
    if (axis === get().axis) update.zoom = clamped;
    set(update as Partial<ViewerStore>);
  },
  adjustAxisZoom: (axis, delta) => {
    const cur = getAxisState(get(), axis).zoom;
    const clamped = Math.max(0.5, Math.min(6, Number((cur + delta).toFixed(2))));
    const update: Partial<ViewerStore> = { [axisStateKey(axis)]: { ...getAxisState(get(), axis), zoom: clamped } };
    if (axis === get().axis) update.zoom = clamped;
    set(update as Partial<ViewerStore>);
  },
  setAxisPan: (axis, pan) => {
    const update: Partial<ViewerStore> = { [axisStateKey(axis)]: { ...getAxisState(get(), axis), pan } };
    if (axis === get().axis) update.pan = pan;
    set(update as Partial<ViewerStore>);
  },
  adjustAxisPan: (axis, delta) => {
    const cur = getAxisState(get(), axis).pan;
    const pan = { x: cur.x + delta.x, y: cur.y + delta.y };
    const update: Partial<ViewerStore> = { [axisStateKey(axis)]: { ...getAxisState(get(), axis), pan } };
    if (axis === get().axis) update.pan = pan;
    set(update as Partial<ViewerStore>);
  },
  resetAxisView: (axis) => {
    const update: Partial<ViewerStore> = { [axisStateKey(axis)]: { ...getAxisState(get(), axis), zoom: 1, pan: { x: 0, y: 0 } } };
    if (axis === get().axis) { update.zoom = 1; update.pan = { x: 0, y: 0 }; }
    set(update as Partial<ViewerStore>);
  },

  crosshair: null,
  setCrosshair: (crosshair) => set({ crosshair }),

  hoverPoint: null,
  setHoverPoint: (hoverPoint) => set({ hoverPoint }),
  clickedVoxel: null,
  setClickedVoxel: (clickedVoxel) => set({ clickedVoxel }),
  window: 350,
  level: 40,
  setWindow: (window) => set({ window }),
  setLevel: (level) => set({ level }),
  overlayOpacity: 0.55,
  setOverlayOpacity: (overlayOpacity) => set({ overlayOpacity }),
  visibleLabels: [1, 2, 3],
  toggleVisibleLabel: (label) =>
    set((state) => ({
      visibleLabels: state.visibleLabels.includes(label)
        ? state.visibleLabels.filter((item) => item !== label)
        : [...state.visibleLabels, label],
    })),
}));
