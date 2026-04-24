import type { CSSProperties } from "react";

import { useEditorStore, type EditorTool } from "../../stores/editorStore";

const TOOLS: { value: EditorTool; label: string }[] = [
  { value: "inspect", label: "Inspect" },
  { value: "brush", label: "Brush" },
  { value: "erase", label: "Erase" },
  { value: "polygon", label: "Polygon" },
  { value: "fill", label: "Fill" },
  { value: "relabel", label: "Relabel" },
  { value: "magicWand", label: "Magic Wand" },
];

export function ToolBar() {
  const activeTool = useEditorStore((state) => state.activeTool);
  const setActiveTool = useEditorStore((state) => state.setActiveTool);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Tools</h3>
      <div style={styles.grid}>
        {TOOLS.map((tool) => (
          <button
            key={tool.value}
            onClick={() => setActiveTool(tool.value)}
            style={{
              ...styles.button,
              ...(activeTool === tool.value ? styles.buttonActive : {}),
            }}
          >
            {tool.label}
          </button>
        ))}
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
  },
  heading: {
    margin: "0 0 12px",
    fontSize: 15,
  },
  grid: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 8,
  },
  button: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid transparent",
    borderRadius: 12,
    padding: "10px 12px",
  },
  buttonActive: {
    border: "1px solid var(--accent)",
    background: "rgba(90, 209, 255, 0.1)",
  },
};
