import { useEffect, useState, type CSSProperties } from "react";

import { getMagicWandMaskUrl } from "../../api/edit";
import { InteractionLayer } from "./InteractionLayer";
import { OverlayCanvas } from "./OverlayCanvas";
import { SliceCanvas } from "./SliceCanvas";
import { SliceNavigator } from "./SliceNavigator";
import { SlicePane } from "./SlicePane";
import { useEditorStore } from "../../stores/editorStore";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore, type ViewerAxis } from "../../stores/viewerStore";

function physicalAspect(
  axis: ViewerAxis,
  pixelWidth: number,
  pixelHeight: number,
  spacing: number[],
): string {
  const s = spacing.length >= 3 ? spacing : [1, 1, 1];
  // After to_display_orientation (flipud(raw.T)):
  //   axial:    width=dim0 → s[0],  height=dim1 → s[1]
  //   coronal:  width=dim0 → s[0],  height=dim2 → s[2]
  //   sagittal: width=dim1 → s[1],  height=dim2 → s[2]
  let ws: number, hs: number;
  if (axis === "axial") { ws = s[0]; hs = s[1]; }
  else if (axis === "coronal") { ws = s[0]; hs = s[2]; }
  else { ws = s[1]; hs = s[2]; }
  return `${pixelWidth * ws} / ${pixelHeight * hs}`;
}

export function Viewer2D() {
  const layout = useViewerStore((state) => state.layout);
  const axis = useViewerStore((state) => state.axis);
  const sliceIndex = useViewerStore((state) => state.sliceIndex);
  const zoom = useViewerStore((state) => state.zoom);
  const pan = useViewerStore((state) => state.pan);
  const hoverPoint = useViewerStore((state) => state.hoverPoint);
  const setAxis = useViewerStore((state) => state.setAxis);
  const setSliceIndex = useViewerStore((state) => state.setSliceIndex);
  const setLayout = useViewerStore((state) => state.setLayout);
  const adjustZoom = useViewerStore((state) => state.adjustZoom);
  const resetView = useViewerStore((state) => state.resetView);
  const visibleLabels = useViewerStore((state) => state.visibleLabels);
  const overlayOpacity = useViewerStore((state) => state.overlayOpacity);
  const sessionStatus = useSessionStore((state) => state.sessionStatus);
  const sessionMeta = useSessionStore((state) => state.sessionMeta);
  const activeSlice = useSessionStore((state) => state.activeSlice);
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const previewMaskVersion = useSessionStore((state) => state.previewMaskVersion);
  const activeTool = useEditorStore((state) => state.activeTool);
  const magicWandPreview = useEditorStore((state) => state.magicWandPreview);

  // Preview mask overlay for single-view mode
  const hasPreview = (activeTool === "magicWand" && magicWandPreview) || previewMaskVersion > 0;
  const [previewMaskUrl, setPreviewMaskUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!activeSessionId || !hasPreview || layout !== "single") {
      setPreviewMaskUrl(null);
      return;
    }
    let cancelled = false;
    const url = getMagicWandMaskUrl(activeSessionId, axis, sliceIndex);
    fetch(url).then((res) => {
      if (cancelled) return;
      if (res.status === 204 || !res.ok) { setPreviewMaskUrl(null); return; }
      return res.blob();
    }).then((blob) => {
      if (cancelled || !blob) return;
      setPreviewMaskUrl(URL.createObjectURL(blob));
    }).catch(() => { if (!cancelled) setPreviewMaskUrl(null); });
    return () => {
      cancelled = true;
      setPreviewMaskUrl((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    };
  }, [activeSessionId, hasPreview, previewMaskVersion, magicWandPreview, layout, axis, sliceIndex]);

  const maxSlice =
    sessionStatus == null
      ? 0
      : axis === "sagittal"
        ? sessionStatus.shape[0] - 1
        : axis === "coronal"
          ? sessionStatus.shape[1] - 1
          : sessionStatus.shape[2] - 1;

  if (layout === "multi") {
    return (
      <section style={styles.panel}>
        <div style={styles.header}>
          <div>
            <h2 style={styles.title}>Viewer</h2>
            <div style={styles.meta}>
              Multi-plane view | Hover: {hoverPoint ? `${Math.round(hoverPoint.x)},${Math.round(hoverPoint.y)}` : "-"}
            </div>
          </div>
          <div style={styles.controlGroup}>
            <select value={layout} onChange={(event) => setLayout(event.target.value as "single" | "multi")} style={styles.select}>
              <option value="single">Single</option>
              <option value="multi">Multi-plane</option>
            </select>
          </div>
        </div>
        <div style={styles.multiGrid}>
          <SlicePane axis="axial" compact />
          <SlicePane axis="coronal" compact />
          <SlicePane axis="sagittal" compact />
          <div style={styles.infoPane}>
            <div style={styles.infoPaneContent}>
              <strong>Active: {axis}</strong>
              <div style={styles.infoRow}>Click a pane header to set active axis for editing</div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Single-view mode (original behavior)
  return (
    <section style={styles.panel}>
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Viewer</h2>
          <div style={styles.meta}>
            Axis: {axis} | Slice: {sliceIndex} | Zoom: {zoom.toFixed(2)}x | Pan: {Math.round(pan.x)},{Math.round(pan.y)}
          </div>
        </div>
        <div style={styles.controlGroup}>
          <select value={layout} onChange={(event) => setLayout(event.target.value as "single" | "multi")} style={styles.select}>
            <option value="single">Single</option>
            <option value="multi">Multi-plane</option>
          </select>
          <select value={axis} onChange={(event) => setAxis(event.target.value as typeof axis)} style={styles.select}>
            <option value="axial">Axial</option>
            <option value="coronal">Coronal</option>
            <option value="sagittal">Sagittal</option>
          </select>
          <input
            type="number"
            min={0}
            max={Math.max(maxSlice, 0)}
            value={sliceIndex}
            onChange={(event) => setSliceIndex(Number(event.target.value))}
            style={styles.numberInput}
          />
          <button type="button" style={styles.actionButton} onClick={resetView}>
            Reset view
          </button>
        </div>
      </div>
      <div
        style={styles.viewport}
        onWheel={(event) => {
          event.preventDefault();
          adjustZoom(event.deltaY < 0 ? 0.1 : -0.1);
        }}
      >
        {activeSlice ? (
          <div
            style={{
              ...styles.canvasStack,
              width: `min(100%, ${activeSlice.width}px)`,
              aspectRatio: physicalAspect(axis, activeSlice.width, activeSlice.height, sessionMeta?.spacing ?? [1, 1, 1]),
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            }}
          >
            <SliceCanvas src={activeSlice.ctImageUrl} alt={`CT ${axis} slice ${sliceIndex}`} />
            <OverlayCanvas
              slice={activeSlice}
              sessionMeta={sessionMeta}
              visibleLabels={visibleLabels}
              overlayOpacity={overlayOpacity}
            />
            <InteractionLayer width={activeSlice.width} height={activeSlice.height} />
            {previewMaskUrl && (
              <img src={previewMaskUrl} alt="" style={styles.previewMask} />
            )}
          </div>
        ) : (
          <div style={styles.canvasPlaceholder}>
            {activeSessionId
              ? "This phase has no CT image. Segmentation-only view will be added next."
              : "Select a case and phase to load a session."}
          </div>
        )}
      </div>
      <div style={styles.footerNavigator}>
        <span>Slice Navigation</span>
        <SliceNavigator sliceIndex={sliceIndex} maxSlice={Math.max(maxSlice, 0)} onChange={setSliceIndex} />
      </div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--panel)",
    border: "1px solid var(--border)",
    borderRadius: 22,
    padding: 14,
    minHeight: 0,
    display: "grid",
    gridTemplateRows: "auto 1fr auto",
    gap: 12,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 16,
  },
  title: {
    margin: 0,
    fontSize: 18,
  },
  meta: {
    color: "var(--text-soft)",
    fontSize: 13,
    marginTop: 4,
  },
  viewport: {
    minHeight: 0,
    display: "grid",
    placeItems: "center",
    overflow: "hidden",
    borderRadius: 18,
    border: "1px dashed var(--border)",
    background:
      "radial-gradient(circle at center, rgba(90, 209, 255, 0.08), transparent 45%), #0b1724",
  },
  canvasPlaceholder: {
    color: "var(--text-soft)",
    textAlign: "center",
    maxWidth: 320,
  },
  canvasStack: {
    position: "relative",
    transformOrigin: "center center",
  },
  previewMask: {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    zIndex: 2,
  },
  controlGroup: {
    display: "flex",
    gap: 8,
    alignItems: "center",
  },
  select: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 10px",
  },
  numberInput: {
    width: 88,
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 10px",
  },
  actionButton: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 10px",
  },
  footerNavigator: {
    display: "grid",
    gap: 8,
    padding: "10px 12px",
    borderRadius: 12,
    background: "var(--panel-soft)",
    color: "var(--text-soft)",
    fontSize: 13,
  },
  multiGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gridTemplateRows: "1fr 1fr",
    gap: 8,
    minHeight: 0,
    overflow: "hidden",
  },
  infoPane: {
    display: "grid",
    placeItems: "center",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "var(--panel-soft)",
  },
  infoPaneContent: {
    textAlign: "center",
    fontSize: 13,
    color: "var(--text-soft)",
  },
  infoRow: {
    marginTop: 4,
    fontSize: 11,
    opacity: 0.7,
  },
};
