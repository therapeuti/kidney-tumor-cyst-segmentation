import { apiGet, apiPost } from "./client";
import type {
  PostprocessApplyResponse,
  PostprocessFunctionDefinition,
  PostprocessPreviewResponse,
  PostprocessRequest,
} from "../types/api";

export function fetchPostprocessFunctions(): Promise<PostprocessFunctionDefinition[]> {
  return apiGet<PostprocessFunctionDefinition[]>("/api/postprocess/functions");
}

export function previewPostprocess(
  sessionId: string,
  payload: PostprocessRequest,
): Promise<PostprocessPreviewResponse> {
  return apiPost<PostprocessPreviewResponse, PostprocessRequest>(
    `/api/sessions/${sessionId}/postprocess/preview`,
    payload,
  );
}

export function applyPostprocess(
  sessionId: string,
  payload: PostprocessRequest,
): Promise<PostprocessApplyResponse> {
  return apiPost<PostprocessApplyResponse, PostprocessRequest>(
    `/api/sessions/${sessionId}/postprocess/apply`,
    payload,
  );
}
