import type { CSSProperties } from "react";

import { useEditorStore } from "../../stores/editorStore";

export function PolygonPanel() {
  const polygonVertexCount = useEditorStore((state) => state.polygonVertices.length);
  const clearPolygon = useEditorStore((state) => state.clearPolygon);
  const overwrite = useEditorStore((state) => state.overwrite);
  const setOverwrite = useEditorStore((state) => state.setOverwrite);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Polygon</h3>
      <div style={styles.text}>Vertices: {polygonVertexCount}</div>
      <label style={styles.row}>
        <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
        <span>Overwrite other labels</span>
      </label>
      <button style={styles.button} onClick={clearPolygon}>
        Clear polygon
      </button>
      <div style={styles.text}>Fill and erase actions will be connected after viewer interaction lands.</div>
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
  text: {
    color: "var(--text-soft)",
    fontSize: 13,
  },
  row: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    color: "var(--text-soft)",
    fontSize: 13,
  },
  button: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "10px 12px",
  },
};
