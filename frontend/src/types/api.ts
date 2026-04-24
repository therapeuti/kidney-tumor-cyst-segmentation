export type CaseSummary = {
  caseId: string;
  phases: string[];
};

export type SessionCreatePayload = {
  caseId: string;
  phase: string;
};

export type SessionSummary = {
  sessionId: string;
  caseId: string;
  phase: string;
  dirty: boolean;
  canUndo: boolean;
  canRedo: boolean;
};

export type SessionStatus = SessionSummary & {
  shape: number[];
  spacing: number[];
  labels: number[];
};

export type SessionMeta = {
  shape: number[];
  spacing: number[];
  labels: Array<{
    id: number;
    key: string;
    name: string;
    color: number[];
  }>;
};

export type SlicePayload = {
  axis: "axial" | "coronal" | "sagittal";
  index: number;
  width: number;
  height: number;
  ctImageUrl: string | null;
  mask: {
    encoding: "raw";
    labels: number[];
    data: number[][];
  };
};

export type EditResponse = {
  ok: boolean;
  changedVoxels: number;
  session: SessionStatus;
};

export type SaveSessionResponse = {
  saved: boolean;
  dirty: boolean;
  backupPath: string;
};

export type PostprocessFunctionDefinition = {
  key: string;
  label: string;
  requiresCt: boolean;
  params: Array<{
    key: string;
    label: string;
    type: string;
    required: boolean;
    default: string | number | null;
    options: Array<{
      label: string;
      value: string | number;
    }>;
  }>;
};

export type PostprocessRequest = {
  function: string;
  params: Record<string, string | number | boolean | null>;
};

export type PostprocessPreviewResponse = {
  ok: boolean;
  changedVoxels: number;
  summary: {
    operation: string;
    details: Record<string, unknown>;
  };
};

export type PostprocessApplyResponse = {
  ok: boolean;
  changedVoxels: number;
  summary: {
    operation: string;
    details: Record<string, unknown>;
  };
  session: SessionStatus;
};
