import { apiGet } from "./client";

export type PhaseLabelStats = {
  phase: string;
  label: number;
  labelName: string;
  voxelCount: number;
};

export type PhasePairDice = {
  phaseA: string;
  phaseB: string;
  label: number;
  labelName: string;
  dice: number;
};

export type ComparisonData = {
  caseId: string;
  phases: string[];
  labelStats: PhaseLabelStats[];
  diceScores: PhasePairDice[];
};

export function fetchPhaseComparison(caseId: string): Promise<ComparisonData> {
  return apiGet<ComparisonData>(`/api/cases/${caseId}/compare`);
}
