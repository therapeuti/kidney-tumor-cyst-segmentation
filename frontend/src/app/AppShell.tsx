import { useEffect, useRef, type CSSProperties } from "react";

import { CaseBrowser } from "../components/sidebar/CaseBrowser";
import { LabelPanel } from "../components/sidebar/LabelPanel";
import { PhaseTabs } from "../components/sidebar/PhaseTabs";
import { ViewerControlsPanel } from "../components/sidebar/ViewerControlsPanel";
import { ComparisonPanel } from "../components/panels/ComparisonPanel";
import { HistoryPanel } from "../components/panels/HistoryPanel";
import { Viewer2D } from "../components/viewer/Viewer2D";
import { ToolBar } from "../components/toolbar/ToolBar";
import { BrushPanel } from "../components/toolbar/BrushPanel";
import { PostprocessPanel } from "../components/toolbar/PostprocessPanel";
import { MagicWandPanel } from "../components/toolbar/MagicWandPanel";
import { RelabelPanel } from "../components/toolbar/RelabelPanel";
import { InterpolatePanel } from "../components/toolbar/InterpolatePanel";
import { PolygonPanel } from "../components/toolbar/PolygonPanel";
import { useActiveSession } from "../features/session/useActiveSession";
import { useSessionActions } from "../features/session/useSessionActions";
import { useSessionBootstrap } from "../features/session/useSessionBootstrap";
import { useEditorStore } from "../stores/editorStore";
import { useSessionStore } from "../stores/sessionStore";
import { useViewerStore } from "../stores/viewerStore";

export function AppShell() {
  const { loadCases } = useSessionBootstrap();
  useActiveSession();
  const { handleRedo, handleSave, handleUndo } = useSessionActions();
  const activeTool = useEditorStore((state) => state.activeTool);
  const status = useSessionStore((state) => state.status);
  const sessionError = useSessionStore((state) => state.sessionError);
  const isLoadingSession = useSessionStore((state) => state.isLoadingSession);
  const isLoadingSlice = useSessionStore((state) => state.isLoadingSlice);
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const overlayOpacity = useViewerStore((state) => state.overlayOpacity);
  const setOverlayOpacity = useViewerStore((state) => state.setOverlayOpacity);
  const prevOpacityRef = useRef(0.55);
  const isOverlayVisible = overlayOpacity > 0;

  function handleToggleOverlay() {
    if (isOverlayVisible) {
      prevOpacityRef.current = overlayOpacity;
      setOverlayOpacity(0);
    } else {
      setOverlayOpacity(prevOpacityRef.current || 0.55);
    }
  }

  useEffect(() => {
    void loadCases();
  }, [loadCases]);

  return (
    <div style={styles.shell}>
      <header style={styles.topBar}>
        <div>
          <strong>Kidney Segmentation Viewer</strong>
          <div style={styles.subtleText}>{status}</div>
          {sessionError ? <div style={styles.errorText}>{sessionError}</div> : null}
          {isLoadingSession ? <div style={styles.loadingText}>Loading active session...</div> : null}
          {!isLoadingSession && isLoadingSlice ? <div style={styles.loadingText}>Loading slice...</div> : null}
        </div>
        <div style={styles.topActions}>
          <button
            style={{
              ...styles.ghostButton,
              ...(isOverlayVisible ? {} : { background: "var(--danger, #c44)", color: "#fff" }),
            }}
            onClick={handleToggleOverlay}
          >
            {isOverlayVisible ? "Seg ON" : "Seg OFF"}
          </button>
          <button style={styles.ghostButton} disabled={!activeSessionId} onClick={() => void handleSave()}>
            Save
          </button>
          <button style={styles.ghostButton} disabled={!activeSessionId} onClick={() => void handleUndo()}>
            Undo
          </button>
          <button style={styles.ghostButton} disabled={!activeSessionId} onClick={() => void handleRedo()}>
            Redo
          </button>
        </div>
      </header>
      <div style={styles.body}>
        <aside style={styles.leftSidebar}>
          <CaseBrowser />
          <PhaseTabs />
          <LabelPanel />
          <ViewerControlsPanel />
          <ComparisonPanel />
          <HistoryPanel />
        </aside>
        <main style={styles.main}>
          <Viewer2D />
        </main>
        <aside style={styles.rightSidebar}>
          <ToolBar />
          {activeTool === "brush" || activeTool === "erase" ? <BrushPanel /> : null}
          {activeTool === "polygon" ? <PolygonPanel /> : null}
          {activeTool === "relabel" ? <RelabelPanel /> : null}
          {activeTool === "magicWand" ? <MagicWandPanel /> : null}
          <InterpolatePanel />
          <PostprocessPanel />
        </aside>
      </div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  shell: {
    display: "grid",
    gridTemplateRows: "72px 1fr",
    height: "100vh",
    overflow: "hidden",
  },
  topBar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "16px 20px",
    borderBottom: "1px solid var(--border)",
    background: "rgba(10, 20, 30, 0.84)",
    backdropFilter: "blur(16px)",
  },
  topActions: {
    display: "flex",
    gap: 10,
  },
  body: {
    display: "grid",
    gridTemplateColumns: "340px minmax(0, 1fr) 300px",
    minHeight: 0,
    overflow: "hidden",
  },
  leftSidebar: {
    borderRight: "1px solid var(--border)",
    padding: 12,
    display: "flex",
    flexDirection: "column",
    gap: 12,
    minHeight: 0,
    overflowY: "auto",
    background: "rgba(13, 26, 38, 0.9)",
  },
  rightSidebar: {
    borderLeft: "1px solid var(--border)",
    padding: 12,
    display: "flex",
    flexDirection: "column",
    gap: 12,
    minHeight: 0,
    overflowY: "auto",
    background: "rgba(13, 26, 38, 0.9)",
  },
  main: {
    display: "grid",
    gridTemplateRows: "1fr",
    minHeight: 0,
    padding: 12,
    gap: 12,
    overflow: "hidden",
  },
  subtleText: {
    color: "var(--text-soft)",
    fontSize: 13,
  },
  errorText: {
    color: "var(--danger)",
    fontSize: 12,
    marginTop: 4,
  },
  loadingText: {
    color: "var(--accent)",
    fontSize: 12,
    marginTop: 4,
  },
  ghostButton: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 12px",
  },
};
