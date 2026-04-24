import { apiGet } from "./client";
import type { SessionMeta, SlicePayload } from "../types/api";

export function fetchSessionMeta(sessionId: string): Promise<SessionMeta> {
  return apiGet<SessionMeta>(`/api/sessions/${sessionId}/meta`);
}

export function fetchVoxelInfo(
  sessionId: string,
  axis: "axial" | "coronal" | "sagittal",
  sliceIndex: number,
  x: number,
  y: number,
): Promise<{ label: number; hu: number | null }> {
  const query = new URLSearchParams({
    axis,
    sliceIndex: String(sliceIndex),
    x: String(x),
    y: String(y),
  });
  return apiGet<{ label: number; hu: number | null }>(`/api/sessions/${sessionId}/voxel?${query.toString()}`);
}

export function fetchSlice(
  sessionId: string,
  axis: "axial" | "coronal" | "sagittal",
  index: number,
  window: number,
  level: number,
): Promise<SlicePayload> {
  const query = new URLSearchParams({
    axis,
    index: String(index),
    window: String(window),
    level: String(level),
  });
  return apiGet<SlicePayload>(`/api/sessions/${sessionId}/slice?${query.toString()}`);
}
