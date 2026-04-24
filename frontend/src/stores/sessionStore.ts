import { create } from "zustand";

import type { ViewerAxis } from "./viewerStore";
import type { CaseSummary, SessionMeta, SessionStatus, SlicePayload } from "../types/api";

type AxisSlices = Record<ViewerAxis, SlicePayload | null>;

type LogEntry = {
  timestamp: number;
  message: string;
};

type SessionStore = {
  cases: CaseSummary[];
  selectedCaseId: string | null;
  selectedPhase: string | null;
  activeSessionId: string | null;
  status: string;
  operationLog: LogEntry[];
  sessionStatus: SessionStatus | null;
  sessionMeta: SessionMeta | null;
  activeSlice: SlicePayload | null;
  axisSlices: AxisSlices;
  isLoadingSession: boolean;
  isLoadingSlice: boolean;
  sessionError: string | null;
  previewMaskVersion: number;
  bumpPreviewMask: () => void;
  clearPreviewMask: () => void;
  setCases: (cases: CaseSummary[]) => void;
  setSelectedCaseId: (caseId: string) => void;
  setSelectedPhase: (phase: string) => void;
  setActiveSessionId: (sessionId: string | null) => void;
  setStatus: (status: string) => void;
  setSessionStatus: (sessionStatus: SessionStatus | null) => void;
  setSessionMeta: (sessionMeta: SessionMeta | null) => void;
  setActiveSlice: (slice: SlicePayload | null) => void;
  setAxisSlice: (axis: ViewerAxis, slice: SlicePayload | null) => void;
  setIsLoadingSession: (isLoading: boolean) => void;
  setIsLoadingSlice: (isLoading: boolean) => void;
  setSessionError: (error: string | null) => void;
  appendLog: (message: string) => void;
};

export const useSessionStore = create<SessionStore>((set) => ({
  cases: [],
  selectedCaseId: null,
  selectedPhase: null,
  activeSessionId: null,
  status: "Idle",
  operationLog: [],
  sessionStatus: null,
  sessionMeta: null,
  activeSlice: null,
  axisSlices: { axial: null, coronal: null, sagittal: null },
  isLoadingSession: false,
  isLoadingSlice: false,
  sessionError: null,
  previewMaskVersion: 0,
  bumpPreviewMask: () => set((state) => ({ previewMaskVersion: state.previewMaskVersion + 1 })),
  clearPreviewMask: () => set({ previewMaskVersion: 0 }),
  setCases: (cases) =>
    set((state) => {
      const fallbackCase = cases[0] ?? null;
      const preservedCase =
        cases.find((item) => item.caseId === state.selectedCaseId) ?? fallbackCase;
      const preservedPhase =
        preservedCase?.phases.includes(state.selectedPhase ?? "")
          ? state.selectedPhase
          : preservedCase?.phases[0] ?? null;

      return {
        cases,
        selectedCaseId: preservedCase?.caseId ?? null,
        selectedPhase: preservedPhase,
      };
    }),
  setSelectedCaseId: (caseId) =>
    set((state) => {
      const selectedCase = state.cases.find((item) => item.caseId === caseId) ?? null;
      return {
        selectedCaseId: caseId,
        selectedPhase: selectedCase?.phases[0] ?? null,
        activeSessionId: null,
        sessionStatus: null,
        sessionMeta: null,
        activeSlice: null,
        axisSlices: { axial: null, coronal: null, sagittal: null },
        sessionError: null,
      };
    }),
  setSelectedPhase: (phase) =>
    set({
      selectedPhase: phase,
      activeSessionId: null,
      sessionStatus: null,
      sessionMeta: null,
      activeSlice: null,
      axisSlices: { axial: null, coronal: null, sagittal: null },
      sessionError: null,
    }),
  setActiveSessionId: (sessionId) => set({ activeSessionId: sessionId }),
  setStatus: (status) => set((state) => ({
    status,
    operationLog: [...state.operationLog, { timestamp: Date.now(), message: status }].slice(-50),
  })),
  setSessionStatus: (sessionStatus) => set({ sessionStatus }),
  setSessionMeta: (sessionMeta) => set({ sessionMeta }),
  setActiveSlice: (activeSlice) => set({ activeSlice }),
  setAxisSlice: (axis, slice) => set((state) => ({ axisSlices: { ...state.axisSlices, [axis]: slice } })),
  setIsLoadingSession: (isLoadingSession) => set({ isLoadingSession }),
  setIsLoadingSlice: (isLoadingSlice) => set({ isLoadingSlice }),
  setSessionError: (sessionError) => set({ sessionError }),
  appendLog: (message) => set((state) => ({
    operationLog: [...state.operationLog, { timestamp: Date.now(), message }].slice(-50),
  })),
}));
