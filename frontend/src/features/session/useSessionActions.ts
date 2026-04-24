import { useCallback } from "react";

import { redoSession, saveSession, undoSession } from "../../api/session";
import { fetchSlice } from "../../api/viewer";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";

export function useSessionActions() {
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const setSessionStatus = useSessionStore((state) => state.setSessionStatus);
  const setActiveSlice = useSessionStore((state) => state.setActiveSlice);
  const setStatus = useSessionStore((state) => state.setStatus);
  const clearPreviewMask = useSessionStore((state) => state.clearPreviewMask);
  const axis = useViewerStore((state) => state.axis);
  const sliceIndex = useViewerStore((state) => state.sliceIndex);
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);

  const reloadSlice = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    const slice = await fetchSlice(activeSessionId, axis, sliceIndex, window, level);
    setActiveSlice(slice);
  }, [activeSessionId, axis, level, setActiveSlice, sliceIndex, window]);

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
    await reloadSlice();
    setStatus("Undo applied");
  }, [activeSessionId, clearPreviewMask, reloadSlice, setSessionStatus, setStatus]);

  const handleRedo = useCallback(async () => {
    if (!activeSessionId) {
      return;
    }
    const status = await redoSession(activeSessionId);
    setSessionStatus(status);
    clearPreviewMask();
    await reloadSlice();
    setStatus("Redo applied");
  }, [activeSessionId, clearPreviewMask, reloadSlice, setSessionStatus, setStatus]);

  return { handleSave, handleUndo, handleRedo };
}
