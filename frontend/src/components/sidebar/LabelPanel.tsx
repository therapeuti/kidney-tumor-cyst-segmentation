import type { CSSProperties } from "react";

import { useViewerStore } from "../../stores/viewerStore";

const LABELS = [
  { id: 1, name: "Kidney", color: "var(--label-kidney)" },
  { id: 2, name: "Tumor", color: "var(--label-tumor)" },
  { id: 3, name: "Cyst", color: "var(--label-cyst)" },
];

export function LabelPanel() {
  const visibleLabels = useViewerStore((state) => state.visibleLabels);
  const overlayOpacity = useViewerStore((state) => state.overlayOpacity);
  const toggleVisibleLabel = useViewerStore((state) => state.toggleVisibleLabel);
  const setOverlayOpacity = useViewerStore((state) => state.setOverlayOpacity);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Labels</h3>
      <div style={styles.list}>
        {LABELS.map((label) => (
          <label key={label.id} style={styles.row}>
            <span style={{ ...styles.swatch, background: label.color }} />
            <span style={styles.labelName}>{label.name}</span>
            <input
              type="checkbox"
              checked={visibleLabels.includes(label.id)}
              onChange={() => toggleVisibleLabel(label.id)}
            />
          </label>
        ))}
      </div>
      <label style={styles.opacityBlock}>
        <span>Overlay opacity: {Math.round(overlayOpacity * 100)}%</span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.05"
          value={overlayOpacity}
          onChange={(event) => setOverlayOpacity(Number(event.target.value))}
        />
      </label>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--panel)",
    border: "1px solid var(--border)",
    borderRadius: 16,
    padding: 14,
  },
  heading: {
    margin: "0 0 12px",
    fontSize: 15,
  },
  list: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  row: {
    display: "grid",
    gridTemplateColumns: "16px 1fr auto",
    alignItems: "center",
    gap: 10,
  },
  swatch: {
    width: 12,
    height: 12,
    borderRadius: 999,
  },
  labelName: {
    fontSize: 14,
  },
  opacityBlock: {
    display: "grid",
    gap: 8,
    marginTop: 14,
    color: "var(--text-soft)",
    fontSize: 13,
  },
};
