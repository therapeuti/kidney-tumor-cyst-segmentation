import { useState, type CSSProperties } from "react";

import { applyInterpolate } from "../../api/edit";
import { fetchSlice } from "../../api/viewer";
import { useEditorStore } from "../../stores/editorStore";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";

export function InterpolatePanel() {
  const [startSlice, setStartSlice] = useState(0);
  const [endSlice, setEndSlice] = useState(10);
  const [status, setLocalStatus] = useState("");

  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const setSessionStatus = useSessionStore((state) => state.setSessionStatus);
  const setActiveSlice = useSessionStore((state) => state.setActiveSlice);
  const setStatus = useSessionStore((state) => state.setStatus);

  const axis = useViewerStore((state) => state.axis);
  const sliceIndex = useViewerStore((state) => state.sliceIndex);
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);
  const activeLabel = useEditorStore((state) => state.activeLabel);

  async function handleApply() {
    if (!activeSessionId) return;
    try {
      const response = await applyInterpolate(activeSessionId, {
        axis,
        startSlice,
        endSlice,
        label: activeLabel,
      });
      setSessionStatus(response.session);
      setLocalStatus(`Interpolated: ${response.changedVoxels} voxels`);
      setStatus(`Interpolation applied (${response.changedVoxels} voxels)`);
      const slice = await fetchSlice(activeSessionId, axis, sliceIndex, window, level);
      setActiveSlice(slice);
    } catch (error) {
      setLocalStatus(error instanceof Error ? error.message : "Interpolation failed");
    }
  }

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Slice Interpolation</h3>
      <div style={styles.hint}>
        Fill label {activeLabel} between two slices ({axis} axis)
      </div>
      <label style={styles.block}>
        <span>Start slice</span>
        <input type="number" min={0} value={startSlice} onChange={(e) => setStartSlice(Number(e.target.value))} />
      </label>
      <label style={styles.block}>
        <span>End slice</span>
        <input type="number" min={0} value={endSlice} onChange={(e) => setEndSlice(Number(e.target.value))} />
      </label>
      <button style={styles.button} disabled={!activeSessionId} onClick={() => void handleApply()}>
        Interpolate
      </button>
      {status && <div style={styles.status}>{status}</div>}
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
  hint: {
    color: "var(--text-soft)",
    fontSize: 12,
  },
  block: {
    display: "grid",
    gap: 4,
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
  status: {
    color: "var(--text-soft)",
    fontSize: 12,
  },
};
