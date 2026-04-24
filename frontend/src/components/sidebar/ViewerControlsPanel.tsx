import type { CSSProperties } from "react";

import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";

export function ViewerControlsPanel() {
  const zoom = useViewerStore((state) => state.zoom);
  const setZoom = useViewerStore((state) => state.setZoom);
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);
  const setWindow = useViewerStore((state) => state.setWindow);
  const setLevel = useViewerStore((state) => state.setLevel);
  const hoverPoint = useViewerStore((state) => state.hoverPoint);
  const clickedVoxel = useViewerStore((state) => state.clickedVoxel);
  const activeSlice = useSessionStore((state) => state.activeSlice);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Viewer Controls</h3>
      <label style={styles.block}>
        <span>Zoom</span>
        <input
          type="range"
          min="0.5"
          max="6"
          step="0.1"
          value={zoom}
          onChange={(event) => setZoom(Number(event.target.value))}
        />
        <strong style={styles.value}>{zoom.toFixed(2)}x</strong>
      </label>
      <label style={styles.block}>
        <span>Window</span>
        <input
          type="range"
          min="50"
          max="2000"
          step="10"
          value={window}
          onChange={(event) => setWindow(Number(event.target.value))}
        />
        <strong style={styles.value}>{window}</strong>
      </label>
      <label style={styles.block}>
        <span>Level</span>
        <input
          type="range"
          min="-200"
          max="400"
          step="5"
          value={level}
          onChange={(event) => setLevel(Number(event.target.value))}
        />
        <strong style={styles.value}>{level}</strong>
      </label>
      <div style={styles.statsGrid}>
        <div style={styles.statCard}>
          <span>Mask Labels</span>
          <strong>{activeSlice?.mask.labels.join(", ") ?? "-"}</strong>
        </div>
        <div style={styles.statCard}>
          <span>Mask Size</span>
          <strong>{activeSlice ? `${activeSlice.width} x ${activeSlice.height}` : "-"}</strong>
        </div>
        <div style={styles.statCard}>
          <span>Cursor</span>
          <strong>{hoverPoint ? `${hoverPoint.x}, ${hoverPoint.y}` : "-"}</strong>
        </div>
        <div style={styles.statCard}>
          <span>HU</span>
          <strong>{clickedVoxel?.hu != null ? clickedVoxel.hu : "-"}</strong>
        </div>
        <div style={styles.statCard}>
          <span>Label</span>
          <strong>{clickedVoxel ? clickedVoxel.label : "-"}</strong>
        </div>
      </div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--panel)",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: 14,
    display: "grid",
    gap: 10,
  },
  heading: {
    margin: 0,
    fontSize: 15,
  },
  block: {
    display: "grid",
    gap: 6,
    color: "var(--text-soft)",
    fontSize: 12,
  },
  value: {
    color: "var(--text)",
    fontSize: 12,
  },
  statsGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
    gap: 8,
  },
  statCard: {
    display: "grid",
    gap: 4,
    padding: "8px 10px",
    borderRadius: 12,
    background: "var(--panel-soft)",
    color: "var(--text-soft)",
    fontSize: 11,
  },
};
