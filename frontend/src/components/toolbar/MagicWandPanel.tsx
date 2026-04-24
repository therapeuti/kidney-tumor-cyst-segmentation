import { type CSSProperties } from "react";

import { applyMagicWand, clearMagicWandMask } from "../../api/edit";
import { fetchSlice } from "../../api/viewer";
import { useEditorStore } from "../../stores/editorStore";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";

export function MagicWandPanel() {
  const activeLabel = useEditorStore((state) => state.activeLabel);
  const setActiveLabel = useEditorStore((state) => state.setActiveLabel);
  const overwrite = useEditorStore((state) => state.overwrite);
  const setOverwrite = useEditorStore((state) => state.setOverwrite);
  const preserveLabels = useEditorStore((state) => state.preserveLabels);

  const tolerance = useEditorStore((state) => state.magicWandTolerance);
  const setTolerance = useEditorStore((state) => state.setMagicWandTolerance);
  const maxVoxels = useEditorStore((state) => state.magicWandMaxVoxels);
  const setMaxVoxels = useEditorStore((state) => state.setMagicWandMaxVoxels);
  const preview = useEditorStore((state) => state.magicWandPreview);
  const setPreview = useEditorStore((state) => state.setMagicWandPreview);

  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const setSessionStatus = useSessionStore((state) => state.setSessionStatus);
  const setActiveSlice = useSessionStore((state) => state.setActiveSlice);
  const setAxisSlice = useSessionStore((state) => state.setAxisSlice);
  const setStatus = useSessionStore((state) => state.setStatus);

  const axis = useViewerStore((state) => state.axis);
  const sliceIndex = useViewerStore((state) => state.sliceIndex);
  const axialState = useViewerStore((state) => state.axialState);
  const coronalState = useViewerStore((state) => state.coronalState);
  const sagittalState = useViewerStore((state) => state.sagittalState);
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);

  async function handleApply() {
    if (!activeSessionId || !preview) return;
    try {
      setStatus("Applying magic wand...");
      const response = await applyMagicWand(activeSessionId, {
        axis,
        sliceIndex,
        x: preview.seedPoint.x,
        y: preview.seedPoint.y,
        tolerance,
        maxVoxels,
        label: activeLabel,
        overwrite,
        preserveLabels,
      });
      setSessionStatus(response.session);
      setPreview(null);

      // Refresh all axes
      const axes = [
        { axis: "axial" as const, index: axialState.sliceIndex },
        { axis: "coronal" as const, index: coronalState.sliceIndex },
        { axis: "sagittal" as const, index: sagittalState.sliceIndex },
      ];
      const results = await Promise.all(
        axes.map(({ axis: a, index }) => fetchSlice(activeSessionId, a, index, window, level)),
      );
      for (let i = 0; i < axes.length; i++) {
        setAxisSlice(axes[i].axis, results[i]);
        if (axes[i].axis === axis) setActiveSlice(results[i]);
      }

      setStatus(`Magic wand applied: ${response.changedVoxels.toLocaleString()} voxels`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Magic wand apply failed");
    }
  }

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Magic Wand</h3>

      <label style={styles.block}>
        <span>Label</span>
        <select value={activeLabel} onChange={(e) => setActiveLabel(Number(e.target.value))}>
          <option value={1}>Kidney</option>
          <option value={2}>Tumor</option>
          <option value={3}>Cyst</option>
        </select>
      </label>

      <label style={styles.block}>
        <span>Tolerance: ±{tolerance} HU</span>
        <input type="range" min="5" max="200" step="5" value={tolerance}
          onChange={(e) => setTolerance(Number(e.target.value))} />
      </label>

      <label style={styles.block}>
        <span>Max voxels: {maxVoxels.toLocaleString()}</span>
        <input type="range" min="1000" max="2000000" step="1000" value={maxVoxels}
          onChange={(e) => setMaxVoxels(Number(e.target.value))} />
      </label>

      <label style={styles.checkboxRow}>
        <input type="checkbox" checked={overwrite} onChange={(e) => setOverwrite(e.target.checked)} />
        <span>Overwrite other labels</span>
      </label>

      {preview ? (
        <div style={styles.previewBox}>
          <div style={styles.previewHeader}>Preview</div>
          <div>Selected: <strong>{preview.selectedVoxels.toLocaleString()}</strong> voxels</div>
          <div>Slices: {preview.sliceMin} – {preview.sliceMax}</div>
          <div>Seed HU: {preview.seedHU}</div>
          <div>HU range: {preview.minHU} ~ {preview.maxHU} (mean {preview.meanHU})</div>
          <div style={styles.actions}>
            <button style={styles.applyBtn} onClick={() => void handleApply()}>Apply</button>
            <button style={styles.cancelBtn} onClick={() => {
              setPreview(null);
              if (activeSessionId) void clearMagicWandMask(activeSessionId);
            }}>Cancel</button>
          </div>
        </div>
      ) : (
        <p style={styles.hint}>Click on the CT image to preview region selection.</p>
      )}
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
  heading: { margin: 0, fontSize: 15 },
  block: {
    display: "grid",
    gap: 6,
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
  previewBox: {
    background: "var(--panel-soft)",
    borderRadius: 12,
    padding: "10px 12px",
    fontSize: 13,
    color: "var(--text-soft)",
    display: "grid",
    gap: 4,
  },
  previewHeader: {
    fontWeight: 700,
    fontSize: 13,
    color: "var(--text)",
  },
  actions: {
    display: "flex",
    gap: 8,
    marginTop: 6,
  },
  applyBtn: {
    flex: 1,
    background: "var(--accent, #58a6ff)",
    color: "#fff",
    border: "none",
    borderRadius: 10,
    padding: "8px 12px",
    cursor: "pointer",
  },
  cancelBtn: {
    flex: 1,
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 12px",
    cursor: "pointer",
  },
  hint: {
    margin: 0,
    color: "var(--text-soft)",
    fontSize: 12,
    lineHeight: "1.5",
    opacity: 0.7,
  },
};
