import { apiGet } from "./client";
import type { CaseSummary } from "../types/api";

export function fetchCases(): Promise<CaseSummary[]> {
  return apiGet<CaseSummary[]>("/api/cases");
}
