import { apiPost } from "./client";
import type { EditResponse } from "../types/api";

export type BrushEditPayload = {
  axis: "axial" | "coronal" | "sagittal";
  sliceIndex: number;
  points: Array<[number, number]>;
  radius: number;
  label: number;
  mode: "paint" | "erase";
  overwrite: boolean;
  preserveLabels: number[];
};

export type PolygonEditPayload = {
  axis: "axial" | "coronal" | "sagittal";
  sliceIndex: number;
  vertices: Array<[number, number]>;
  label: number;
  mode: "fill" | "erase";
  overwrite: boolean;
  preserveLabels: number[];
};

export function applyBrushEdit(sessionId: string, payload: BrushEditPayload): Promise<EditResponse> {
  return apiPost<EditResponse, BrushEditPayload>(`/api/sessions/${sessionId}/edit/brush`, payload);
}

export function applyPolygonEdit(sessionId: string, payload: PolygonEditPayload): Promise<EditResponse> {
  return apiPost<EditResponse, PolygonEditPayload>(`/api/sessions/${sessionId}/edit/polygon`, payload);
}

export type FloodFillPayload = {
  axis: "axial" | "coronal" | "sagittal";
  sliceIndex: number;
  x: number;
  y: number;
  label: number;
  overwrite: boolean;
  preserveLabels: number[];
};

export function applyFloodFill(sessionId: string, payload: FloodFillPayload): Promise<EditResponse> {
  return apiPost<EditResponse, FloodFillPayload>(`/api/sessions/${sessionId}/edit/flood-fill`, payload);
}

export type InterpolatePayload = {
  axis: "axial" | "coronal" | "sagittal";
  startSlice: number;
  endSlice: number;
  label: number;
};

export function applyInterpolate(sessionId: string, payload: InterpolatePayload): Promise<EditResponse> {
  return apiPost<EditResponse, InterpolatePayload>(`/api/sessions/${sessionId}/edit/interpolate`, payload);
}

export type RelabelPayload = {
  axis: "axial" | "coronal" | "sagittal";
  sliceIndex: number;
  x: number;
  y: number;
  toLabel: number;
};

export function applyRelabel(sessionId: string, payload: RelabelPayload): Promise<EditResponse> {
  return apiPost<EditResponse, RelabelPayload>(`/api/sessions/${sessionId}/edit/relabel`, payload);
}

export type MagicWandPreviewPayload = {
  axis: "axial" | "coronal" | "sagittal";
  sliceIndex: number;
  x: number;
  y: number;
  tolerance: number;
  maxVoxels: number;
};

export type MagicWandPreviewResponse = {
  ok: boolean;
  selectedVoxels: number;
  sliceMin: number;
  sliceMax: number;
  seedHU: number;
  toleranceHU: number;
  meanHU: number;
  minHU: number;
  maxHU: number;
};

export type MagicWandApplyPayload = Omit<MagicWandPreviewPayload, never> & {
  label: number;
  overwrite: boolean;
  preserveLabels: number[];
};

export function previewMagicWand(sessionId: string, payload: MagicWandPreviewPayload): Promise<MagicWandPreviewResponse> {
  return apiPost<MagicWandPreviewResponse, MagicWandPreviewPayload>(
    `/api/sessions/${sessionId}/edit/magic-wand/preview`, payload,
  );
}

export function applyMagicWand(sessionId: string, payload: MagicWandApplyPayload): Promise<EditResponse> {
  return apiPost<EditResponse, MagicWandApplyPayload>(
    `/api/sessions/${sessionId}/edit/magic-wand/apply`, payload,
  );
}

export function getMagicWandMaskUrl(sessionId: string, axis: string, index: number): string {
  return `/api/sessions/${sessionId}/edit/magic-wand/mask?axis=${axis}&index=${index}`;
}

export function clearMagicWandMask(sessionId: string): Promise<{ ok: boolean }> {
  return apiPost<{ ok: boolean }>(`/api/sessions/${sessionId}/edit/magic-wand/clear`);
}
