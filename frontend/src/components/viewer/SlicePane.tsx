import { useEffect, useRef, useState, type CSSProperties, type PointerEvent as ReactPointerEvent, type MouseEvent as ReactMouseEvent } from "react";

import { getMagicWandMaskUrl } from "../../api/edit";

import { InteractionLayer } from "./InteractionLayer";
import { OverlayCanvas } from "./OverlayCanvas";
import { SliceCanvas } from "./SliceCanvas";
import { SliceNavigator } from "./SliceNavigator";
import { useEditorStore } from "../../stores/editorStore";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore, type ViewerAxis } from "../../stores/viewerStore";

type SlicePaneProps = {
  axis: ViewerAxis;
  isPrimary?: boolean;
  compact?: boolean;
};

function getAxisSize(shape: number[], axis: ViewerAxis): number {
  if (axis === "sagittal") return shape[0] - 1;
  if (axis === "coronal") return shape[1] - 1;
  return shape[2] - 1;
}

/**
 * Display orientation: to_display_orientation = flipud(raw_slice.T)
 *
 * Raw slice extraction per axis:
 *   axial    → vol[:,:,z]  raw (dim0, dim1)  → .T → (dim1, dim0) → flipud → display width=dim1, height=dim0
 *   coronal  → vol[:,y,:]  raw (dim0, dim2)  → .T → (dim2, dim0) → flipud → display width=dim2, height=dim0
 *   sagittal → vol[x,:,:]  raw (dim1, dim2)  → .T → (dim2, dim1) → flipud → display width=dim2, height=dim1
 *
 * 3D volume dims: dim0=sagittal, dim1=coronal, dim2=axial
 */

/**
 * Convert display pixel (px, py) to 3D volume coordinate.
 *
 * to_display_orientation = flipud(raw.T), so the reverse is:
 *   Axial    (vol[:,:,z]): sagittal=px, coronal=displayH-1-py
 *   Coronal  (vol[:,y,:]): sagittal=px, axial=displayH-1-py
 *   Sagittal (vol[x,:,:]): coronal=px,  axial=displayH-1-py
 */
function displayToVolume(
  axis: ViewerAxis,
  px: number,
  py: number,
  _displayWidth: number,
  displayHeight: number,
  _shape: number[],
  currentSliceIndex: number,
): { x: number; y: number; z: number } {
  // volume shape = (S=dim0, C=dim1, A=dim2), S=sagittal, C=coronal, A=axial
  // display = flipud(raw.T)
  //   Axial   vol[:,:,z]: raw(S,C) → display H=C(shape[1]), W=S(shape[0])
  //     display[py,px] = volume[px, H-1-py, z]  → x=px, y=H-1-py, z=slice
  //   Coronal vol[:,y,:]: raw(S,A) → display H=A(shape[2]), W=S(shape[0])
  //     display[py,px] = volume[px, y, H-1-py]  → x=px, y=slice, z=H-1-py
  //   Sagittal vol[x,:,:]: raw(C,A) → display H=A(shape[2]), W=C(shape[1])
  //     display[py,px] = volume[x, px, H-1-py]  → x=slice, y=px, z=H-1-py
  const H = displayHeight;
  const flippedY = Math.round(H - 1 - py);
  const roundedX = Math.round(px);

  if (axis === "axial") {
    return { x: roundedX, y: flippedY, z: currentSliceIndex };
  }
  if (axis === "coronal") {
    return { x: roundedX, y: currentSliceIndex, z: flippedY };
  }
  // sagittal
  return { x: currentSliceIndex, y: roundedX, z: flippedY };
}

/**
 * Convert 3D volume coordinate to display fractional position for crosshair lines.
 *
 * Display dimensions per axis (after to_display_orientation):
 *   Axial:    displayW=shape[0], displayH=shape[1]
 *   Coronal:  displayW=shape[0], displayH=shape[2]
 *   Sagittal: displayW=shape[1], displayH=shape[2]
 */
function volumeToDisplayFrac(
  axis: ViewerAxis,
  vx: number,
  vy: number,
  vz: number,
  shape: number[],
): { hFrac: number; vFrac: number } | null {
  let displayW: number, displayH: number, pxVal: number, pyFlipped: number;

  // display = flipud(raw.T):
  //   Axial:    W=shape[0](S), H=shape[1](C).  px=vx, py=H-1-vy
  //   Coronal:  W=shape[0](S), H=shape[2](A).  px=vx, py=H-1-vz
  //   Sagittal: W=shape[1](C), H=shape[2](A).  px=vy, py=H-1-vz
  if (axis === "axial") {
    displayW = shape[0]; displayH = shape[1];
    pxVal = vx;
    pyFlipped = vy;
  } else if (axis === "coronal") {
    displayW = shape[0]; displayH = shape[2];
    pxVal = vx;
    pyFlipped = vz;
  } else {
    displayW = shape[1]; displayH = shape[2];
    pxVal = vy;
    pyFlipped = vz;
  }

  const hFrac = pxVal / Math.max(displayW - 1, 1);
  const vFrac = (displayH - 1 - pyFlipped) / Math.max(displayH - 1, 1);

  return {
    hFrac: Math.max(0, Math.min(1, hFrac)),
    vFrac: Math.max(0, Math.min(1, vFrac)),
  };
}

function physicalAspect(
  axis: ViewerAxis,
  pixelWidth: number,
  pixelHeight: number,
  spacing: number[],
): { width: number; height: number } {
  const s = spacing.length >= 3 ? spacing : [1, 1, 1];
  // After to_display_orientation (flipud(raw.T)):
  //   axial:    width=dim0 → s[0],  height=dim1 → s[1]
  //   coronal:  width=dim0 → s[0],  height=dim2 → s[2]
  //   sagittal: width=dim1 → s[1],  height=dim2 → s[2]
  let ws: number, hs: number;
  if (axis === "axial") { ws = s[0]; hs = s[1]; }
  else if (axis === "coronal") { ws = s[0]; hs = s[2]; }
  else { ws = s[1]; hs = s[2]; }
  return { width: pixelWidth * ws, height: pixelHeight * hs };
}

export function SlicePane({ axis, isPrimary = false, compact = false }: SlicePaneProps) {
  const perAxisState = useViewerStore((state) =>
    axis === "axial" ? state.axialState : axis === "coronal" ? state.coronalState : state.sagittalState,
  );
  const setAxisSliceIndex = useViewerStore((state) => state.setAxisSliceIndex);
  const adjustAxisZoom = useViewerStore((state) => state.adjustAxisZoom);
  const adjustAxisPan = useViewerStore((state) => state.adjustAxisPan);
  const resetAxisView = useViewerStore((state) => state.resetAxisView);
  const setCrosshair = useViewerStore((state) => state.setCrosshair);
  const primaryAxis = useViewerStore((state) => state.axis);
  const setAxis = useViewerStore((state) => state.setAxis);
  const visibleLabels = useViewerStore((state) => state.visibleLabels);
  const overlayOpacity = useViewerStore((state) => state.overlayOpacity);
  const crosshair = useViewerStore((state) => state.crosshair);

  const sessionStatus = useSessionStore((state) => state.sessionStatus);
  const sessionMeta = useSessionStore((state) => state.sessionMeta);
  const axisSlice = useSessionStore((state) => state.axisSlices[axis]);
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const previewMaskVersion = useSessionStore((state) => state.previewMaskVersion);

  const { sliceIndex, zoom, pan } = perAxisState;
  const maxSlice = sessionStatus ? Math.max(getAxisSize(sessionStatus.shape, axis), 0) : 0;
  const activeTool = useEditorStore((state) => state.activeTool);

  const shape = sessionStatus?.shape ?? [0, 0, 0];

  const isEditingTool = activeTool !== "inspect";
  const showEditor = isPrimary || isEditingTool;

  // Preview mask overlay (shared by postprocess preview & magic wand)
  const magicWandPreview = useEditorStore((state) => state.magicWandPreview);
  const hasPreview = (activeTool === "magicWand" && magicWandPreview) || previewMaskVersion > 0;
  const [previewMaskUrl, setPreviewMaskUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!activeSessionId || !hasPreview) {
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
  }, [activeSessionId, hasPreview, previewMaskVersion, magicWandPreview, axis, sliceIndex]);

  const handleSliceChange = (next: number) => setAxisSliceIndex(axis, next);

  // Wheel zoom: must use non-passive listener to allow preventDefault
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      adjustAxisZoom(axis, e.deltaY < 0 ? 0.1 : -0.1);
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, [axis, adjustAxisZoom]);

  // Pan handling
  const panStartRef = useRef<{ x: number; y: number } | null>(null);
  const didDragRef = useRef(false);
  const viewportRef = useRef<HTMLDivElement>(null);

  function handlePanPointerDown(e: ReactPointerEvent<HTMLDivElement>) {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    panStartRef.current = { x: e.clientX, y: e.clientY };
    didDragRef.current = false;
  }

  function handlePanPointerMove(e: ReactPointerEvent<HTMLDivElement>) {
    if (!panStartRef.current) return;
    const dx = e.clientX - panStartRef.current.x;
    const dy = e.clientY - panStartRef.current.y;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didDragRef.current = true;
    panStartRef.current = { x: e.clientX, y: e.clientY };
    adjustAxisPan(axis, { x: dx, y: dy });
  }

  function handlePanPointerUp(e: ReactPointerEvent<HTMLDivElement>) {
    panStartRef.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) {
      e.currentTarget.releasePointerCapture(e.pointerId);
    }
  }

  /** Click on non-primary pane → crosshair sync */
  function handleCrosshairClick(e: ReactMouseEvent<HTMLDivElement>) {
    if (didDragRef.current) return; // was a drag, not a click
    if (!axisSlice || !sessionStatus) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - rect.left) / rect.width) * axisSlice.width;
    const py = ((e.clientY - rect.top) / rect.height) * axisSlice.height;

    const vol = displayToVolume(axis, px, py, axisSlice.width, axisSlice.height, shape, sliceIndex);

    // Clamp
    vol.x = Math.max(0, Math.min(shape[0] - 1, vol.x));
    vol.y = Math.max(0, Math.min(shape[1] - 1, vol.y));
    vol.z = Math.max(0, Math.min(shape[2] - 1, vol.z));

    setCrosshair(vol);

    // Sync other views' slice indices
    if (axis !== "sagittal") setAxisSliceIndex("sagittal", vol.x);
    if (axis !== "coronal") setAxisSliceIndex("coronal", vol.y);
    if (axis !== "axial") setAxisSliceIndex("axial", vol.z);
  }

  // Crosshair lines
  const crosshairLines = (() => {
    if (!crosshair || !axisSlice || !sessionStatus) return null;
    return volumeToDisplayFrac(axis, crosshair.x, crosshair.y, crosshair.z, shape);
  })();

  return (
    <section style={compact ? styles.paneCompact : styles.pane}>
      <div style={styles.paneHeader} onClick={() => setAxis(axis)}>
        <span style={{
          ...styles.paneTitle,
          ...(axis === primaryAxis ? { color: "var(--accent, #58a6ff)" } : {}),
        }}>
          {axis.charAt(0).toUpperCase() + axis.slice(1)}
        </span>
        <span style={styles.paneMeta}>
          {sliceIndex}/{maxSlice}
        </span>
        {!compact && (
          <button type="button" style={styles.resetBtn} onClick={() => resetAxisView(axis)}>
            Reset
          </button>
        )}
      </div>
      <div
        ref={viewportRef}
        style={styles.paneViewport}
      >
        {axisSlice ? (
          <div
            style={{
              ...styles.canvasStack,
              width: `min(100%, ${axisSlice.width}px)`,
              aspectRatio: (() => {
                const sp = sessionMeta?.spacing;
                if (!sp || sp.length < 3) return `${axisSlice.width} / ${axisSlice.height}`;
                const pa = physicalAspect(axis, axisSlice.width, axisSlice.height, sp);
                return `${pa.width} / ${pa.height}`;
              })(),
              transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            }}
          >
            <SliceCanvas src={axisSlice.ctImageUrl} alt={`CT ${axis} ${sliceIndex}`} />
            <OverlayCanvas
              slice={axisSlice}
              sessionMeta={sessionMeta}
              visibleLabels={visibleLabels}
              overlayOpacity={overlayOpacity}
            />
            {showEditor ? (
              <InteractionLayer width={axisSlice.width} height={axisSlice.height} paneAxis={axis} />
            ) : (
              <div
                style={styles.panOverlay}
                onPointerDown={handlePanPointerDown}
                onPointerMove={handlePanPointerMove}
                onPointerUp={handlePanPointerUp}
                onClick={handleCrosshairClick}
              />
            )}
            {previewMaskUrl && (
              <img src={previewMaskUrl} alt="" style={styles.previewMask} />
            )}
            {crosshairLines && (
              <svg style={styles.crosshairSvg} viewBox={`0 0 ${axisSlice.width} ${axisSlice.height}`}>
                <line
                  x1={crosshairLines.hFrac * axisSlice.width} y1={0}
                  x2={crosshairLines.hFrac * axisSlice.width} y2={axisSlice.height}
                  stroke="rgba(255,255,0,0.6)" strokeWidth={1}
                />
                <line
                  x1={0} y1={crosshairLines.vFrac * axisSlice.height}
                  x2={axisSlice.width} y2={crosshairLines.vFrac * axisSlice.height}
                  stroke="rgba(255,255,0,0.6)" strokeWidth={1}
                />
              </svg>
            )}
          </div>
        ) : (
          <div style={styles.placeholder}>Loading...</div>
        )}
      </div>
      <SliceNavigator sliceIndex={sliceIndex} maxSlice={maxSlice} onChange={handleSliceChange} />
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  pane: {
    display: "grid",
    gridTemplateRows: "auto 1fr auto",
    gap: 6,
    minHeight: 0,
    overflow: "hidden",
  },
  paneCompact: {
    display: "grid",
    gridTemplateRows: "auto 1fr auto",
    gap: 4,
    minHeight: 0,
    overflow: "hidden",
  },
  paneHeader: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: 13,
    cursor: "pointer",
  },
  paneTitle: {
    fontWeight: 700,
    fontSize: 14,
  },
  paneMeta: {
    color: "var(--text-soft)",
    fontSize: 12,
  },
  resetBtn: {
    marginLeft: "auto",
    background: "var(--panel-soft)",
    color: "var(--text-soft)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: "2px 8px",
    fontSize: 11,
    cursor: "pointer",
  },
  paneViewport: {
    minHeight: 0,
    display: "grid",
    placeItems: "center",
    overflow: "hidden",
    borderRadius: 8,
    border: "1px solid var(--border)",
    background: "#0b1724",
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
  panOverlay: {
    position: "absolute",
    inset: 0,
    zIndex: 3,
    cursor: "crosshair",
  },
  crosshairSvg: {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    pointerEvents: "none",
    zIndex: 4,
  },
  placeholder: {
    color: "var(--text-soft)",
    fontSize: 12,
  },
};
