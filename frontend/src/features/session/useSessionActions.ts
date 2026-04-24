import { useCallback } from "react";

import { redoSession, saveSession, undoSession } from "../../api/session";
import { fetchSlice } from "../../api/viewer";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";

export function useSessionActions() {
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const setSessionStatus = useSessionStore((state) => state.setSessionStatus);
  const setActiveSlice = useSessionStore((state) => state.setActiveSlice);
  const setAxisSlice = useSessionStore((state) => state.setAxisSlice);
  const setStatus = useSessionStore((state) => state.setStatus);
  const clearPreviewMask = useSessionStore((state) => state.clearPreviewMask);
  const axis = useViewerStore((state) => state.axis);
  const axialState = useViewerStore((state) => state.axialState);
  const coronalState = useViewerStore((state) => state.coronalState);
  const sagittalState = useViewerStore((state) => state.sagittalState);
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);

  const refreshAllSlices = useCallback(async () => {
    if (!activeSessionId) return;
    const axes = [
      { axis: "axial" as const, index: axialState.sliceIndex },
      { axis: "coronal" as const, index: coronalState.sliceIndex },
      { axis: "sagittal" as const, index: sagittalState.sliceIndex },
    ];
    const results = await Promise.all(
      axes.map(({ axis: a, index }) => fetchSlice(activeSessionId, a, index, window, level)),
    );
    for (let i = 0; i < axes.length; i++) {
      setAxisSlice(axes[i].axis, results[i]);
      if (axes[i].axis === axis) {
        setActiveSlice(results[i]);
      }
    }
  }, [activeSessionId, axis, axialState.sliceIndex, coronalState.sliceIndex, sagittalState.sliceIndex, window, level, setAxisSlice, setActiveSlice]);

  const handleSave = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    const response = await saveSession(activeSessionId);
    setStatus(response.saved ? "Segmentation saved" : "Save failed");
  }, [activeSessionId, setStatus]);

  const handleUndo = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    const status = await undoSession(activeSessionId);
    setSessionStatus(status);
    clearPreviewMask();
    await refreshAllSlices();
    setStatus("Undo applied");
  }, [activeSessionId, clearPreviewMask, refreshAllSlices, setSessionStatus, setStatus]);

  const handleRedo = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    const status = await redoSession(activeSessionId);
    setSessionStatus(status);
    clearPreviewMask();
    await refreshAllSlices();
    setStatus("Redo applied");
  }, [activeSessionId, clearPreviewMask, refreshAllSlices, setSessionStatus, setStatus]);

  return { handleSave, handleUndo, handleRedo };
}
