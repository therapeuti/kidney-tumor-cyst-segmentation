import type { CSSProperties } from "react";

import { useEditorStore } from "../../stores/editorStore";

export function BrushPanel() {
  const brushRadius = useEditorStore((state) => state.brushRadius);
  const setBrushRadius = useEditorStore((state) => state.setBrushRadius);
  const activeLabel = useEditorStore((state) => state.activeLabel);
  const setActiveLabel = useEditorStore((state) => state.setActiveLabel);
  const overwrite = useEditorStore((state) => state.overwrite);
  const setOverwrite = useEditorStore((state) => state.setOverwrite);
  const preserveLabels = useEditorStore((state) => state.preserveLabels);
  const togglePreserveLabel = useEditorStore((state) => state.togglePreserveLabel);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Brush</h3>
      <label style={styles.block}>
        <span>Label</span>
        <select value={activeLabel} onChange={(event) => setActiveLabel(Number(event.target.value))}>
          <option value={1}>Kidney</option>
          <option value={2}>Tumor</option>
          <option value={3}>Cyst</option>
        </select>
      </label>
      <label style={styles.block}>
        <span>Radius: {brushRadius}</span>
        <input
          type="range"
          min="1"
          max="40"
          step="1"
          value={brushRadius}
          onChange={(event) => setBrushRadius(Number(event.target.value))}
        />
      </label>
      <label style={styles.checkboxRow}>
        <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
        <span>Overwrite other labels</span>
      </label>
      <div style={styles.block}>
        <span>Preserve labels</span>
        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={preserveLabels.includes(2)}
            onChange={() => togglePreserveLabel(2)}
          />
          <span>Tumor</span>
        </label>
        <label style={styles.checkboxRow}>
          <input
            type="checkbox"
            checked={preserveLabels.includes(3)}
            onChange={() => togglePreserveLabel(3)}
          />
          <span>Cyst</span>
        </label>
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
    gap: 12,
  },
  heading: {
    margin: 0,
    fontSize: 15,
  },
  block: {
    display: "grid",
    gap: 8,
    color: "var(--text-soft)",
    fontSize: 13,
  },
  checkboxRow: {
    display: "flex",
    gap: 8,
    alignItems: "center",
    color: "var(--text-soft)",
    fontSize: 13,
  },
};
