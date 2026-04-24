import { apiGet, apiPost } from "./client";
import type { SessionCreatePayload, SessionStatus, SessionSummary, SaveSessionResponse } from "../types/api";

export function createSession(payload: SessionCreatePayload): Promise<SessionSummary> {
  return apiPost<SessionSummary, SessionCreatePayload>("/api/sessions", payload);
}

export function fetchSession(sessionId: string): Promise<SessionStatus> {
  return apiGet<SessionStatus>(`/api/sessions/${sessionId}`);
}

export function saveSession(sessionId: string): Promise<SaveSessionResponse> {
  return apiPost<SaveSessionResponse>(`/api/sessions/${sessionId}/save`);
}

export function undoSession(sessionId: string): Promise<SessionStatus> {
  return apiPost<SessionStatus>(`/api/sessions/${sessionId}/undo`);
}

export function redoSession(sessionId: string): Promise<SessionStatus> {
  return apiPost<SessionStatus>(`/api/sessions/${sessionId}/redo`);
}
