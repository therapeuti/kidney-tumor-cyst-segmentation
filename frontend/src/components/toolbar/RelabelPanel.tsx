import type { CSSProperties } from "react";

import { useEditorStore } from "../../stores/editorStore";

export function RelabelPanel() {
  const activeLabel = useEditorStore((state) => state.activeLabel);
  const setActiveLabel = useEditorStore((state) => state.setActiveLabel);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Relabel</h3>
      <label style={styles.block}>
        <span>Change to</span>
        <select value={activeLabel} onChange={(event) => setActiveLabel(Number(event.target.value))}>
          <option value={1}>Kidney</option>
          <option value={2}>Tumor</option>
          <option value={3}>Cyst</option>
        </select>
      </label>
      <p style={styles.hint}>
        Click a component in the viewer to relabel the entire 3D connected component to the selected label.
      </p>
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
  hint: {
    margin: 0,
    color: "var(--text-soft)",
    fontSize: 12,
    lineHeight: "1.5",
    opacity: 0.7,
  },
};
