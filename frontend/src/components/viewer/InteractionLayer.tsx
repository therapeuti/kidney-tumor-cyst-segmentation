import {
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type MouseEvent as ReactMouseEvent,
} from "react";

import { applyBrushEdit, applyFloodFill, applyPolygonEdit, applyRelabel, previewMagicWand } from "../../api/edit";
import { fetchSlice, fetchVoxelInfo } from "../../api/viewer";
import { useEditorStore } from "../../stores/editorStore";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";
import type { SlicePayload } from "../../types/api";

import type { ViewerAxis } from "../../stores/viewerStore";

/** Convert display pixel (px, py) to 3D volume coordinate (same as SlicePane). */
function displayToVolume(
  axis: ViewerAxis, px: number, py: number,
  displayHeight: number, currentSliceIndex: number,
): { x: number; y: number; z: number } {
  const flippedY = Math.round(displayHeight - 1 - py);
  const roundedX = Math.round(px);
  if (axis === "axial") return { x: roundedX, y: flippedY, z: currentSliceIndex };
  if (axis === "coronal") return { x: roundedX, y: currentSliceIndex, z: flippedY };
  return { x: currentSliceIndex, y: roundedX, z: flippedY };
}

type InteractionLayerProps = {
  width: number;
  height: number;
  /** Override axis for multi-view panes. If omitted, uses viewerStore.axis. */
  paneAxis?: ViewerAxis;
};

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function createBooleanMask(width: number, height: number): boolean[][] {
  return Array.from({ length: height }, () => Array.from({ length: width }, () => false));
}

function buildBrushMask(
  width: number,
  height: number,
  points: Array<[number, number]>,
  radius: number,
): boolean[][] {
  const mask = createBooleanMask(width, height);
  const radiusSquared = radius * radius;

  function stamp(cx: number, cy: number) {
    const minX = Math.max(0, Math.floor(cx - radius));
    const maxX = Math.min(width - 1, Math.ceil(cx + radius));
    const minY = Math.max(0, Math.floor(cy - radius));
    const maxY = Math.min(height - 1, Math.ceil(cy + radius));

    for (let y = minY; y <= maxY; y += 1) {
      for (let x = minX; x <= maxX; x += 1) {
        const dx = x - cx;
        const dy = y - cy;
        if (dx * dx + dy * dy <= radiusSquared) {
          mask[y][x] = true;
        }
      }
    }
  }

  if (points.length === 1) {
    stamp(points[0][0], points[0][1]);
    return mask;
  }

  for (let index = 0; index < points.length - 1; index += 1) {
    const [x0, y0] = points[index];
    const [x1, y1] = points[index + 1];
    const distance = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0), 1);
    const steps = Math.max(1, Math.ceil(distance));
    for (let step = 0; step <= steps; step += 1) {
      const t = step / steps;
      stamp(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t);
    }
  }

  return mask;
}

function buildPolygonMask(
  width: number,
  height: number,
  vertices: Array<[number, number]>,
): boolean[][] {
  const mask = createBooleanMask(width, height);
  if (vertices.length < 3) {
    return mask;
  }

  for (let y = 0; y < height; y += 1) {
    const scanY = y + 0.5;
    const intersections: number[] = [];

    for (let index = 0; index < vertices.length; index += 1) {
      const [x1, y1] = vertices[index];
      const [x2, y2] = vertices[(index + 1) % vertices.length];
      const crosses = (y1 <= scanY && y2 > scanY) || (y2 <= scanY && y1 > scanY);
      if (!crosses) {
        continue;
      }
      const t = (scanY - y1) / (y2 - y1);
      intersections.push(x1 + t * (x2 - x1));
    }

    intersections.sort((a, b) => a - b);
    for (let index = 0; index < intersections.length - 1; index += 2) {
      const startX = Math.max(0, Math.ceil(intersections[index]));
      const endX = Math.min(width - 1, Math.floor(intersections[index + 1]));
      for (let x = startX; x <= endX; x += 1) {
        mask[y][x] = true;
      }
    }
  }

  return mask;
}

function applyMaskToSlice(
  slice: SlicePayload,
  editMask: boolean[][],
  label: number,
  mode: "paint" | "fill" | "erase",
  overwrite: boolean,
  preserveLabels: number[],
): { slice: SlicePayload; changedVoxels: number } {
  const nextData = slice.mask.data.map((row) => row.slice());
  const preserve = new Set(preserveLabels);
  let changedVoxels = 0;

  for (let y = 0; y < slice.height; y += 1) {
    for (let x = 0; x < slice.width; x += 1) {
      if (!editMask[y]?.[x]) {
        continue;
      }

      const current = nextData[y][x];
      if (preserve.has(current)) {
        continue;
      }

      if (mode === "erase") {
        if (current !== 0) {
          nextData[y][x] = 0;
          changedVoxels += 1;
        }
        continue;
      }

      if (!overwrite && current !== 0 && current !== label) {
        continue;
      }

      if (current !== label) {
        nextData[y][x] = label;
        changedVoxels += 1;
      }
    }
  }

  const labels = Array.from(new Set(nextData.flat())).sort((a, b) => a - b);

  return {
    slice: {
      ...slice,
      mask: {
        ...slice.mask,
        labels,
        data: nextData,
      },
    },
    changedVoxels,
  };
}

export function InteractionLayer({ width, height, paneAxis }: InteractionLayerProps) {
  const layerRef = useRef<HTMLDivElement | null>(null);
  const panStartRef = useRef<{ x: number; y: number } | null>(null);
  const didDragRef = useRef(false);
  const [strokePoints, setStrokePoints] = useState<Array<[number, number]>>([]);
  const [cursor, setCursor] = useState<[number, number] | null>(null);

  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const activeSlice = useSessionStore((state) => state.activeSlice);
  const axisSlice = useSessionStore((state) => state.axisSlices[paneAxis ?? "axial"]);
  const setSessionStatus = useSessionStore((state) => state.setSessionStatus);
  const setActiveSlice = useSessionStore((state) => state.setActiveSlice);
  const setStatus = useSessionStore((state) => state.setStatus);
  const primaryAxis = useViewerStore((state) => state.axis);
  const axis = paneAxis ?? primaryAxis;
  const sliceIndex = useViewerStore((state) =>
    paneAxis
      ? (paneAxis === "axial" ? state.axialState.sliceIndex
        : paneAxis === "coronal" ? state.coronalState.sliceIndex
        : state.sagittalState.sliceIndex)
      : state.sliceIndex,
  );
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);
  const setHoverPoint = useViewerStore((state) => state.setHoverPoint);
  const adjustPanSingle = useViewerStore((state) => state.adjustPan);
  const adjustAxisPan = useViewerStore((state) => state.adjustAxisPan);
  const setCrosshair = useViewerStore((state) => state.setCrosshair);
  const setAxisSliceIndex = useViewerStore((state) => state.setAxisSliceIndex);
  const setClickedVoxel = useViewerStore((state) => state.setClickedVoxel);
  const sessionStatus = useSessionStore((state) => state.sessionStatus);
  const adjustPan = paneAxis
    ? (delta: { x: number; y: number }) => adjustAxisPan(paneAxis, delta)
    : adjustPanSingle;

  const activeTool = useEditorStore((state) => state.activeTool);
  const activeLabel = useEditorStore((state) => state.activeLabel);
  const brushRadius = useEditorStore((state) => state.brushRadius);
  const overwrite = useEditorStore((state) => state.overwrite);
  const preserveLabels = useEditorStore((state) => state.preserveLabels);
  const polygonVertices = useEditorStore((state) => state.polygonVertices);
  const addPolygonVertex = useEditorStore((state) => state.addPolygonVertex);
  const clearPolygon = useEditorStore((state) => state.clearPolygon);
  const magicWandTolerance = useEditorStore((state) => state.magicWandTolerance);
  const magicWandMaxVoxels = useEditorStore((state) => state.magicWandMaxVoxels);
  const magicWandPreview = useEditorStore((state) => state.magicWandPreview);
  const setMagicWandPreview = useEditorStore((state) => state.setMagicWandPreview);


  const polygonPath = useMemo(
    () => polygonVertices.map(([x, y]) => `${x},${y}`).join(" "),
    [polygonVertices],
  );

  function toSlicePoint(event: ReactPointerEvent<HTMLDivElement> | ReactMouseEvent<HTMLDivElement>): [number, number] {
    const rect = layerRef.current?.getBoundingClientRect();
    if (!rect) {
      return [0, 0];
    }
    const x = clamp(((event.clientX - rect.left) / rect.width) * width, 0, width - 1);
    const y = clamp(((event.clientY - rect.top) / rect.height) * height, 0, height - 1);
    return [x, y];
  }

  const setAxisSlice = useSessionStore((state) => state.setAxisSlice);
  const currentSlice = paneAxis ? axisSlice : activeSlice;

  async function refreshSlice() {
    if (!activeSessionId) {
      return;
    }
    const slice = await fetchSlice(activeSessionId, axis, sliceIndex, window, level);
    setActiveSlice(slice);
    setAxisSlice(axis, slice);
  }

  async function commitBrush(points: Array<[number, number]>) {
    if (!activeSessionId || !currentSlice || points.length === 0) {
      return;
    }
    const mode = activeTool === "erase" ? "erase" : "paint";
    const localResult = applyMaskToSlice(
      currentSlice,
      buildBrushMask(currentSlice.width, currentSlice.height, points, brushRadius),
      activeLabel,
      mode,
      overwrite,
      preserveLabels,
    );

    if (localResult.changedVoxels > 0) {
      setActiveSlice(localResult.slice);
      setAxisSlice(axis, localResult.slice);
      setStatus(`Applying brush... (${localResult.changedVoxels} voxels preview)`);
    }

    try {
      const response = await applyBrushEdit(activeSessionId, {
        axis,
        sliceIndex,
        points,
        radius: brushRadius,
        label: activeLabel,
        mode,
        overwrite,
        preserveLabels,
      });
      setSessionStatus(response.session);
      if (response.changedVoxels > 0) {
        setStatus(`Brush edit applied (${response.changedVoxels} voxels)`);
        void refreshSlice();
      } else {
        setStatus("Brush edit made no visible change. Try painting background or enable overwrite.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Brush edit failed");
      void refreshSlice();
    }
  }

  async function commitPolygon() {
    if (!activeSessionId || !currentSlice || polygonVertices.length < 3) {
      return;
    }
    const localResult = applyMaskToSlice(
      currentSlice,
      buildPolygonMask(currentSlice.width, currentSlice.height, polygonVertices),
      activeLabel,
      activeTool === "erase" ? "erase" : "fill",
      overwrite,
      preserveLabels,
    );
    clearPolygon();
    if (localResult.changedVoxels > 0) {
      setActiveSlice(localResult.slice);
      setAxisSlice(axis, localResult.slice);
      setStatus(`Applying polygon... (${localResult.changedVoxels} voxels preview)`);
    }
    try {
      const response = await applyPolygonEdit(activeSessionId, {
        axis,
        sliceIndex,
        vertices: polygonVertices,
        label: activeLabel,
        mode: activeTool === "erase" ? "erase" : "fill",
        overwrite,
        preserveLabels,
      });
      setSessionStatus(response.session);
      if (response.changedVoxels > 0) {
        setStatus(`Polygon edit applied (${response.changedVoxels} voxels)`);
        void refreshSlice();
      } else {
        setStatus("Polygon edit made no visible change. Try a different region or enable overwrite.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Polygon edit failed");
      void refreshSlice();
    }
  }

  function handlePointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    didDragRef.current = false;
    if (activeTool === "inspect") {
      panStartRef.current = { x: event.clientX, y: event.clientY };
      return;
    }
    if (activeTool !== "brush" && activeTool !== "erase") {
      return;
    }
    const point = toSlicePoint(event);
    setStrokePoints([point]);
  }

  function handlePointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    const point = toSlicePoint(event);
    setCursor(point);
    setHoverPoint({ x: Math.round(point[0]), y: Math.round(point[1]) });
    if (activeTool === "inspect" && panStartRef.current) {
      const next = { x: event.clientX, y: event.clientY };
      const dx = next.x - panStartRef.current.x;
      const dy = next.y - panStartRef.current.y;
      if (Math.abs(dx) > 2 || Math.abs(dy) > 2) didDragRef.current = true;
      adjustPan({ x: dx, y: dy });
      panStartRef.current = next;
      return;
    }
    if (activeTool !== "brush" && activeTool !== "erase") {
      return;
    }
    if (strokePoints.length === 0) {
      return;
    }
    setStrokePoints((current) => [...current, point]);
  }

  async function handlePointerUp() {
    panStartRef.current = null;
    if (strokePoints.length > 0) {
      const points = strokePoints.slice();
      setStrokePoints([]);
      await commitBrush(points);
    }
  }

  async function handleDoubleClick() {
    if (activeTool === "polygon") {
      await commitPolygon();
    }
  }

  async function commitFloodFill(point: [number, number]) {
    if (!activeSessionId || !currentSlice) {
      return;
    }
    try {
      const response = await applyFloodFill(activeSessionId, {
        axis,
        sliceIndex,
        x: Math.round(point[0]),
        y: Math.round(point[1]),
        label: activeLabel,
        overwrite,
        preserveLabels,
      });
      setSessionStatus(response.session);
      if (response.changedVoxels > 0) {
        setStatus(`Fill applied (${response.changedVoxels} voxels)`);
        void refreshSlice();
      } else {
        setStatus("Fill made no change. The region may already have this label.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Fill failed");
      void refreshSlice();
    }
  }

  async function commitMagicWandPreview(point: [number, number]) {
    if (!activeSessionId) return;
    try {
      setStatus("Computing magic wand preview...");
      const response = await previewMagicWand(activeSessionId, {
        axis,
        sliceIndex,
        x: Math.round(point[0]),
        y: Math.round(point[1]),
        tolerance: magicWandTolerance,
        maxVoxels: magicWandMaxVoxels,
      });
      setMagicWandPreview({
        selectedVoxels: response.selectedVoxels,
        sliceMin: response.sliceMin,
        sliceMax: response.sliceMax,
        seedHU: response.seedHU,
        meanHU: response.meanHU,
        minHU: response.minHU,
        maxHU: response.maxHU,
        seedPoint: { x: Math.round(point[0]), y: Math.round(point[1]) },
        previewAxis: axis,
        previewSliceIndex: sliceIndex,
      });
      if (response.selectedVoxels > 0) {
        setStatus(`Preview: ${response.selectedVoxels.toLocaleString()} voxels (mean ${response.meanHU} HU, std ${response.stdHU} HU)`);
      } else {
        setStatus("No voxels selected. Try increasing tolerance.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Magic wand preview failed");
    }
  }

  async function commitRelabel(point: [number, number]) {
    if (!activeSessionId) {
      return;
    }
    try {
      setStatus("Relabeling component...");
      const response = await applyRelabel(activeSessionId, {
        axis,
        sliceIndex,
        x: Math.round(point[0]),
        y: Math.round(point[1]),
        toLabel: activeLabel,
      });
      setSessionStatus(response.session);
      if (response.changedVoxels > 0) {
        setStatus(`Relabeled ${response.changedVoxels.toLocaleString()} voxels`);
        void refreshSlice();
      } else {
        setStatus("No change — clicked on background or same label.");
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Relabel failed");
      void refreshSlice();
    }
  }

  function handleClick(event: ReactMouseEvent<HTMLDivElement>) {
    if (activeTool === "inspect") {
      if (didDragRef.current) return;
      const point = toSlicePoint(event);
      const shape = sessionStatus?.shape ?? [0, 0, 0];
      const vol = displayToVolume(axis, point[0], point[1], height, sliceIndex);
      vol.x = Math.max(0, Math.min(shape[0] - 1, vol.x));
      vol.y = Math.max(0, Math.min(shape[1] - 1, vol.y));
      vol.z = Math.max(0, Math.min(shape[2] - 1, vol.z));
      setCrosshair(vol);
      if (axis !== "sagittal") setAxisSliceIndex("sagittal", vol.x);
      if (axis !== "coronal") setAxisSliceIndex("coronal", vol.y);
      if (axis !== "axial") setAxisSliceIndex("axial", vol.z);
      // Fetch HU value
      if (activeSessionId) {
        void fetchVoxelInfo(activeSessionId, axis, sliceIndex, Math.round(point[0]), Math.round(point[1]))
          .then((info) => setClickedVoxel(info))
          .catch(() => setClickedVoxel(null));
      }
      return;
    }
    if (activeTool === "fill") {
      const point = toSlicePoint(event);
      void commitFloodFill(point);
      return;
    }
    if (activeTool === "relabel") {
      const point = toSlicePoint(event);
      void commitRelabel(point);
      return;
    }
    if (activeTool === "magicWand") {
      const point = toSlicePoint(event);
      void commitMagicWandPreview(point);
      return;
    }
    if (activeTool !== "polygon") {
      return;
    }
    addPolygonVertex(toSlicePoint(event));
  }

  return (
    <div
      ref={layerRef}
      style={styles.layer}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={(event) => {
        if (event.currentTarget.hasPointerCapture(event.pointerId)) {
          event.currentTarget.releasePointerCapture(event.pointerId);
        }
        void handlePointerUp();
      }}
      onPointerLeave={() => {
        setCursor(null);
        panStartRef.current = null;
        setHoverPoint(null);
      }}
      onDoubleClick={() => void handleDoubleClick()}
      onClick={handleClick}
    >
      {cursor && (activeTool === "brush" || activeTool === "erase") ? (
        <div
          style={{
            ...styles.cursor,
            width: brushRadius * 2,
            height: brushRadius * 2,
            left: `${(cursor[0] / width) * 100}%`,
            top: `${(cursor[1] / height) * 100}%`,
          }}
        />
      ) : null}
      {strokePoints.length > 1 ? (
        <svg viewBox={`0 0 ${width} ${height}`} style={styles.svg}>
          <polyline
            points={strokePoints.map(([x, y]) => `${x},${y}`).join(" ")}
            fill="none"
            stroke="rgba(90, 209, 255, 0.9)"
            strokeWidth={Math.max(1, brushRadius * 2)}
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : null}
      {polygonVertices.length > 0 ? (
        <svg viewBox={`0 0 ${width} ${height}`} style={styles.svg}>
          <polyline
            points={polygonPath}
            fill="rgba(90, 209, 255, 0.18)"
            stroke="rgba(90, 209, 255, 0.95)"
            strokeWidth={2}
          />
        </svg>
      ) : null}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  layer: {
    position: "absolute",
    inset: 0,
    zIndex: 3,
    touchAction: "none",
    cursor: "crosshair",
  },
  cursor: {
    position: "absolute",
    border: "1px solid rgba(255,255,255,0.95)",
    borderRadius: "50%",
    transform: "translate(-50%, -50%)",
    pointerEvents: "none",
    boxShadow: "0 0 0 9999px rgba(255,255,255,0.02)",
  },
  svg: {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    pointerEvents: "none",
  },
};
