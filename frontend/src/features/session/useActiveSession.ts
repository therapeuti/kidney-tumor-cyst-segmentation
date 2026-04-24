import { useCallback, useEffect, useRef } from "react";

import { createSession, fetchSession } from "../../api/session";
import { fetchSessionMeta, fetchSlice } from "../../api/viewer";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore, type ViewerAxis } from "../../stores/viewerStore";

function preloadImage(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve();
    image.onerror = () => reject(new Error(`Failed to load CT image: ${src}`));
    image.src = src;
  });
}

async function safeLoadSlice(
  sessionId: string,
  axis: ViewerAxis,
  index: number,
  w: number,
  l: number,
) {
  const slice = await fetchSlice(sessionId, axis, index, w, l);
  if (slice.ctImageUrl) {
    try { await preloadImage(slice.ctImageUrl); } catch { /* ok */ }
  }
  return slice;
}

/**
 * Independent loader for a single axis.
 * Only fires when its own sliceIndex changes (or sessionId/window/level).
 */
function useAxisSliceLoader(axis: ViewerAxis) {
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setAxisSlice = useSessionStore((s) => s.setAxisSlice);
  const setActiveSlice = useSessionStore((s) => s.setActiveSlice);
  const layout = useViewerStore((s) => s.layout);
  const primaryAxis = useViewerStore((s) => s.axis);
  const sliceIndex = useViewerStore((s) =>
    axis === "axial" ? s.axialState.sliceIndex
      : axis === "coronal" ? s.coronalState.sliceIndex
        : s.sagittalState.sliceIndex,
  );
  const window = useViewerStore((s) => s.window);
  const level = useViewerStore((s) => s.level);
  const requestRef = useRef(0);

  useEffect(() => {
    if (!activeSessionId) return;
    if (layout === "single" && axis !== primaryAxis) return;

    const id = ++requestRef.current;

    void (async () => {
      try {
        const slice = await safeLoadSlice(activeSessionId, axis, sliceIndex, window, level);
        if (requestRef.current !== id) return;
        setAxisSlice(axis, slice);
        if (axis === primaryAxis) {
          setActiveSlice(slice);
        }
      } catch {
        // slice load failed — leave as loading
      }
    })();
  }, [activeSessionId, axis, sliceIndex, window, level, layout, primaryAxis, setAxisSlice, setActiveSlice]);
}

export function useActiveSession() {
  const selectedCaseId = useSessionStore((s) => s.selectedCaseId);
  const selectedPhase = useSessionStore((s) => s.selectedPhase);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSessionId = useSessionStore((s) => s.setActiveSessionId);
  const setSessionStatus = useSessionStore((s) => s.setSessionStatus);
  const setSessionMeta = useSessionStore((s) => s.setSessionMeta);
  const setStatus = useSessionStore((s) => s.setStatus);
  const setSessionError = useSessionStore((s) => s.setSessionError);
  const setIsLoadingSession = useSessionStore((s) => s.setIsLoadingSession);
  const setAxisSliceIndex = useViewerStore((s) => s.setAxisSliceIndex);

  // Independent per-axis loaders
  useAxisSliceLoader("axial");
  useAxisSliceLoader("coronal");
  useAxisSliceLoader("sagittal");

  const openSession = useCallback(async () => {
    if (!selectedCaseId || !selectedPhase) return;

    setIsLoadingSession(true);
    setSessionError(null);
    setStatus(`Opening ${selectedCaseId} ${selectedPhase}...`);

    try {
      const summary = await createSession({ caseId: selectedCaseId, phase: selectedPhase });
      setActiveSessionId(summary.sessionId);

      const [sessionStatus, sessionMeta] = await Promise.all([
        fetchSession(summary.sessionId),
        fetchSessionMeta(summary.sessionId),
      ]);

      setSessionStatus(sessionStatus);
      setSessionMeta(sessionMeta);

      // Initialize all axes to volume center
      const shape = sessionStatus.shape;
      if (shape.length >= 3) {
        setAxisSliceIndex("sagittal", Math.floor(shape[0] / 2));
        setAxisSliceIndex("coronal", Math.floor(shape[1] / 2));
        setAxisSliceIndex("axial", Math.floor(shape[2] / 2));
      }
      setStatus(`Session ready: ${summary.caseId} ${summary.phase}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to open session";
      setSessionError(message);
      setStatus(message);
    } finally {
      setIsLoadingSession(false);
    }
  }, [
    selectedCaseId, selectedPhase, setActiveSessionId, setAxisSliceIndex,
    setIsLoadingSession, setSessionError, setSessionMeta, setSessionStatus, setStatus,
  ]);

  // Open session when case/phase changes, or when activeSessionId is cleared (re-select same case)
  const prevKeyRef = useRef("");
  useEffect(() => {
    const key = `${selectedCaseId}|${selectedPhase}`;
    if (!selectedCaseId || !selectedPhase) return;
    if (activeSessionId && key === prevKeyRef.current) return;
    prevKeyRef.current = key;
    void openSession();
  }, [selectedCaseId, selectedPhase, activeSessionId, openSession]);

  return { openSession };
}
