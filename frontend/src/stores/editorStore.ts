import { create } from "zustand";

export type EditorTool = "inspect" | "brush" | "erase" | "polygon" | "fill" | "relabel" | "magicWand";

type Vertex = [number, number];

export type MagicWandPreview = {
  selectedVoxels: number;
  sliceMin: number;
  sliceMax: number;
  seedHU: number;
  meanHU: number;
  minHU: number;
  maxHU: number;
  seedPoint: { x: number; y: number };
  previewAxis: "axial" | "coronal" | "sagittal";
  previewSliceIndex: number;
} | null;

type EditorStore = {
  activeTool: EditorTool;
  activeLabel: number;
  brushRadius: number;
  overwrite: boolean;
  preserveLabels: number[];
  polygonVertices: Vertex[];
  magicWandTolerance: number;
  magicWandMaxVoxels: number;
  magicWandPreview: MagicWandPreview;
  setActiveTool: (tool: EditorTool) => void;
  setActiveLabel: (label: number) => void;
  setBrushRadius: (radius: number) => void;
  setOverwrite: (overwrite: boolean) => void;
  togglePreserveLabel: (label: number) => void;
  addPolygonVertex: (vertex: Vertex) => void;
  clearPolygon: () => void;
  setMagicWandTolerance: (v: number) => void;
  setMagicWandMaxVoxels: (v: number) => void;
  setMagicWandPreview: (preview: MagicWandPreview) => void;
};

export const useEditorStore = create<EditorStore>((set) => ({
  activeTool: "inspect",
  activeLabel: 1,
  brushRadius: 8,
  overwrite: false,
  preserveLabels: [],
  polygonVertices: [],
  magicWandTolerance: 50,
  magicWandMaxVoxels: 500000,
  magicWandPreview: null,
  setActiveTool: (activeTool) => set({ activeTool, magicWandPreview: null }),
  setActiveLabel: (activeLabel) => set({ activeLabel }),
  setBrushRadius: (brushRadius) => set({ brushRadius }),
  setOverwrite: (overwrite) => set({ overwrite }),
  togglePreserveLabel: (label) =>
    set((state) => ({
      preserveLabels: state.preserveLabels.includes(label)
        ? state.preserveLabels.filter((item) => item !== label)
        : [...state.preserveLabels, label],
    })),
  addPolygonVertex: (vertex) =>
    set((state) => ({
      polygonVertices: [...state.polygonVertices, vertex],
    })),
  clearPolygon: () => set({ polygonVertices: [] }),
  setMagicWandTolerance: (magicWandTolerance) => set({ magicWandTolerance, magicWandPreview: null }),
  setMagicWandMaxVoxels: (magicWandMaxVoxels) => set({ magicWandMaxVoxels, magicWandPreview: null }),
  setMagicWandPreview: (magicWandPreview) => set({ magicWandPreview }),
}));
