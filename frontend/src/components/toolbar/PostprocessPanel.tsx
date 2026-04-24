import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { applyPostprocess, fetchPostprocessFunctions, previewPostprocess } from "../../api/postprocess";
import { fetchSlice } from "../../api/viewer";
import { useSessionStore } from "../../stores/sessionStore";
import { useViewerStore } from "../../stores/viewerStore";
import type { PostprocessFunctionDefinition, PostprocessRequest } from "../../types/api";

function buildInitialParams(definition: PostprocessFunctionDefinition | null) {
  const params: Record<string, string | number | boolean | null> = {};
  for (const param of definition?.params ?? []) {
    params[param.key] = param.default ?? null;
  }
  return params;
}

type SummaryData = {
  operation: string;
  details: Record<string, unknown>;
} | null;

/** Format summary details into readable lines. */
function formatSummaryDetails(details: Record<string, unknown>): string[] {
  const lines: string[] = [];
  const skip = new Set(["target", "empty", "no_selection", "components"]);

  for (const [key, value] of Object.entries(details)) {
    if (skip.has(key)) continue;
    if (value === null || value === undefined) continue;

    const label = key.replace(/_/g, " ");
    if (typeof value === "number") {
      lines.push(`${label}: ${Number.isInteger(value) ? value.toLocaleString() : value.toFixed(2)}`);
    } else if (typeof value === "string") {
      lines.push(`${label}: ${value}`);
    }
  }

  // Component-level details (label_convex)
  const components = details.components;
  if (Array.isArray(components) && components.length > 0) {
    for (let i = 0; i < components.length; i++) {
      const comp = components[i] as Record<string, unknown>;
      if (comp.skipped) {
        lines.push(`  comp ${i + 1}: skipped (${(comp.size as number).toLocaleString()} voxels)`);
      } else {
        const size = comp.size as number;
        const added = comp.added as number;
        lines.push(`  comp ${i + 1}: ${size.toLocaleString()} → ${(size + added).toLocaleString()} (+${added.toLocaleString()})`);
      }
    }
  }

  // Per-label details (remove_isolated, remove_low/high_intensity)
  const labels = details.labels;
  if (Array.isArray(labels)) {
    for (const item of labels) {
      const label = item as Record<string, unknown>;
      const name = label.label_name ?? `label ${label.label}`;
      if (label.removed_voxels !== undefined) {
        lines.push(`  ${name}: -${(label.removed_voxels as number).toLocaleString()} voxels`);
      } else if (label.removed_components !== undefined) {
        lines.push(`  ${name}: ${(label.components as number)} comp → kept ${(label.kept_components as number)}, removed ${(label.removed_components as number)} (${(label.removed_voxels as number).toLocaleString()} vox)`);
      }
    }
  }

  return lines;
}

type RegionConfig = {
  enabled: boolean;
  sliceRange: { enabled: boolean; axis: number; start: number; end: number };
  boundingBox: { enabled: boolean; xStart: number; xEnd: number; yStart: number; yEnd: number; zStart: number; zEnd: number };
  directionCut: { enabled: boolean; axis: number; side: string; cut: number };
};

function defaultRegion(): RegionConfig {
  return {
    enabled: false,
    sliceRange: { enabled: false, axis: 0, start: 0, end: 0 },
    boundingBox: { enabled: false, xStart: 0, xEnd: 0, yStart: 0, yEnd: 0, zStart: 0, zEnd: 0 },
    directionCut: { enabled: false, axis: 0, side: "low", cut: 0 },
  };
}

export function PostprocessPanel() {
  const [functions, setFunctions] = useState<PostprocessFunctionDefinition[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [params, setParams] = useState<Record<string, string | number | boolean | null>>({});
  const [summaryData, setSummaryData] = useState<SummaryData>(null);
  const [changedVoxels, setChangedVoxels] = useState<number | null>(null);
  const [isPreview, setIsPreview] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [region, setRegion] = useState<RegionConfig>(defaultRegion);

  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const setSessionStatus = useSessionStore((state) => state.setSessionStatus);
  const setActiveSlice = useSessionStore((state) => state.setActiveSlice);
  const setAxisSlice = useSessionStore((state) => state.setAxisSlice);
  const setStatus = useSessionStore((state) => state.setStatus);
  const sessionStatus = useSessionStore((state) => state.sessionStatus);
  const bumpPreviewMask = useSessionStore((state) => state.bumpPreviewMask);
  const clearPreviewMask = useSessionStore((state) => state.clearPreviewMask);

  const axis = useViewerStore((state) => state.axis);
  const sliceIndex = useViewerStore((state) => state.sliceIndex);
  const axialState = useViewerStore((state) => state.axialState);
  const coronalState = useViewerStore((state) => state.coronalState);
  const sagittalState = useViewerStore((state) => state.sagittalState);
  const window = useViewerStore((state) => state.window);
  const level = useViewerStore((state) => state.level);

  const shape = sessionStatus?.shape ?? [0, 0, 0];

  const selectedDefinition = useMemo(
    () => functions.find((item) => item.key === selectedKey) ?? null,
    [functions, selectedKey],
  );

  useEffect(() => {
    async function loadFunctions() {
      const items = await fetchPostprocessFunctions();
      setFunctions(items);
      if (items[0]) {
        setSelectedKey(items[0].key);
        setParams(buildInitialParams(items[0]));
      }
    }
    void loadFunctions();
  }, []);

  useEffect(() => {
    setParams(buildInitialParams(selectedDefinition));
    setSummaryData(null);
    setChangedVoxels(null);
    setIsPreview(false);
    clearPreviewMask();
  }, [selectedDefinition]);

  // Reset region bounds when shape changes
  useEffect(() => {
    setRegion((prev) => ({
      ...prev,
      sliceRange: { ...prev.sliceRange, end: Math.max(0, shape[prev.sliceRange.axis] - 1) },
      boundingBox: {
        ...prev.boundingBox,
        xEnd: Math.max(0, shape[0] - 1),
        yEnd: Math.max(0, shape[1] - 1),
        zEnd: Math.max(0, shape[2] - 1),
      },
      directionCut: { ...prev.directionCut, cut: Math.floor(shape[prev.directionCut.axis] / 2) },
    }));
  }, [shape[0], shape[1], shape[2]]);

  async function refreshAllSlices() {
    if (!activeSessionId) {
      return;
    }
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
      if (axes[i].axis === axis) {
        setActiveSlice(results[i]);
      }
    }
  }

  function buildRegionParams(): Record<string, unknown> | null {
    if (!region.enabled) return null;
    const r: Record<string, unknown> = {};
    if (region.sliceRange.enabled) {
      r.slice_range = { axis: region.sliceRange.axis, start: region.sliceRange.start, end: region.sliceRange.end };
    }
    if (region.boundingBox.enabled) {
      r.bounding_box = {
        x_start: region.boundingBox.xStart, x_end: region.boundingBox.xEnd,
        y_start: region.boundingBox.yStart, y_end: region.boundingBox.yEnd,
        z_start: region.boundingBox.zStart, z_end: region.boundingBox.zEnd,
      };
    }
    if (region.directionCut.enabled) {
      r.direction_cut = { axis: region.directionCut.axis, side: region.directionCut.side, cut: region.directionCut.cut };
    }
    return r;
  }

  function makePayload(): PostprocessRequest | null {
    if (!selectedDefinition) {
      return null;
    }
    const regionParams = buildRegionParams();
    return {
      function: selectedDefinition.key,
      params: regionParams ? { ...params, region: regionParams as unknown as string } : params,
    };
  }

  async function handlePreview() {
    if (!activeSessionId) return;
    const payload = makePayload();
    if (!payload) return;
    setIsLoading(true);
    setStatus("Computing preview...");
    try {
      const result = await previewPostprocess(activeSessionId, payload);
      setSummaryData(result.summary);
      setChangedVoxels(result.changedVoxels);
      setIsPreview(true);
      if (result.changedVoxels > 0) bumpPreviewMask();
      setStatus(`Preview: ${result.changedVoxels.toLocaleString()} voxels would change`);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleApply() {
    if (!activeSessionId) return;
    const payload = makePayload();
    if (!payload) return;
    setIsLoading(true);
    setStatus("Applying...");
    try {
      const result = await applyPostprocess(activeSessionId, payload);
      setSessionStatus(result.session);
      clearPreviewMask();
      await refreshAllSlices();
      setSummaryData(result.summary);
      setChangedVoxels(result.changedVoxels);
      setIsPreview(false);
      setStatus(`Postprocess applied: ${result.summary.operation}`);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Postprocess</h3>
      <label style={styles.block}>
        <span>Function</span>
        <select value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
          {functions.map((fn) => (
            <option key={fn.key} value={fn.key}>
              {fn.label}
            </option>
          ))}
        </select>
      </label>
      {selectedDefinition?.params.map((param) => (
        <label key={param.key} style={styles.block}>
          <span>{param.label}</span>
          {param.type === "select" ? (
            <select
              value={String(params[param.key] ?? "")}
              onChange={(event) =>
                setParams((current) => ({
                  ...current,
                  [param.key]: event.target.value,
                }))
              }
            >
              {param.options.map((option) => (
                <option key={String(option.value)} value={String(option.value)}>
                  {option.label}
                </option>
              ))}
            </select>
          ) : param.type === "boolean" ? (
            <input
              type="checkbox"
              checked={Boolean(params[param.key] ?? param.default)}
              onChange={(event) =>
                setParams((current) => ({
                  ...current,
                  [param.key]: event.target.checked,
                }))
              }
            />
          ) : (
            <input
              type="number"
              value={Number(params[param.key] ?? 0)}
              onChange={(event) =>
                setParams((current) => ({
                  ...current,
                  [param.key]: Number(event.target.value),
                }))
              }
            />
          )}
        </label>
      ))}

      {/* Region restriction controls */}
      <div style={styles.regionSection}>
        <label style={styles.checkRow}>
          <input
            type="checkbox"
            checked={region.enabled}
            onChange={(e) => setRegion((r) => ({ ...r, enabled: e.target.checked }))}
          />
          <span style={styles.regionLabel}>Region restriction</span>
        </label>

        {region.enabled && (
          <div style={styles.regionBody}>
            {/* Slice range */}
            <label style={styles.checkRow}>
              <input
                type="checkbox"
                checked={region.sliceRange.enabled}
                onChange={(e) => setRegion((r) => ({ ...r, sliceRange: { ...r.sliceRange, enabled: e.target.checked } }))}
              />
              <span>Slice range</span>
            </label>
            {region.sliceRange.enabled && (
              <div style={styles.regionInputs}>
                <label>
                  Axis
                  <select
                    value={region.sliceRange.axis}
                    onChange={(e) => {
                      const ax = Number(e.target.value);
                      setRegion((r) => ({
                        ...r,
                        sliceRange: { ...r.sliceRange, axis: ax, start: 0, end: Math.max(0, shape[ax] - 1) },
                      }));
                    }}
                  >
                    <option value={0}>0 ({shape[0]})</option>
                    <option value={1}>1 ({shape[1]})</option>
                    <option value={2}>2 ({shape[2]})</option>
                  </select>
                </label>
                <label>
                  Start
                  <input type="number" min={0} max={shape[region.sliceRange.axis] - 1}
                    value={region.sliceRange.start}
                    onChange={(e) => setRegion((r) => ({ ...r, sliceRange: { ...r.sliceRange, start: Number(e.target.value) } }))}
                  />
                </label>
                <label>
                  End
                  <input type="number" min={0} max={shape[region.sliceRange.axis] - 1}
                    value={region.sliceRange.end}
                    onChange={(e) => setRegion((r) => ({ ...r, sliceRange: { ...r.sliceRange, end: Number(e.target.value) } }))}
                  />
                </label>
              </div>
            )}

            {/* Bounding box */}
            <label style={styles.checkRow}>
              <input
                type="checkbox"
                checked={region.boundingBox.enabled}
                onChange={(e) => setRegion((r) => ({ ...r, boundingBox: { ...r.boundingBox, enabled: e.target.checked } }))}
              />
              <span>Bounding box</span>
            </label>
            {region.boundingBox.enabled && (
              <div style={styles.regionInputs}>
                {(["x", "y", "z"] as const).map((dim, ax) => (
                  <div key={dim} style={styles.regionRow}>
                    <span>{dim.toUpperCase()} ({shape[ax]})</span>
                    <input type="number" min={0} max={shape[ax] - 1} style={styles.regionNum}
                      value={region.boundingBox[`${dim}Start` as keyof typeof region.boundingBox] as number}
                      onChange={(e) => setRegion((r) => ({
                        ...r,
                        boundingBox: { ...r.boundingBox, [`${dim}Start`]: Number(e.target.value) },
                      }))}
                    />
                    <span>-</span>
                    <input type="number" min={0} max={shape[ax] - 1} style={styles.regionNum}
                      value={region.boundingBox[`${dim}End` as keyof typeof region.boundingBox] as number}
                      onChange={(e) => setRegion((r) => ({
                        ...r,
                        boundingBox: { ...r.boundingBox, [`${dim}End`]: Number(e.target.value) },
                      }))}
                    />
                  </div>
                ))}
              </div>
            )}

            {/* Direction cut */}
            <label style={styles.checkRow}>
              <input
                type="checkbox"
                checked={region.directionCut.enabled}
                onChange={(e) => setRegion((r) => ({ ...r, directionCut: { ...r.directionCut, enabled: e.target.checked } }))}
              />
              <span>Direction cut</span>
            </label>
            {region.directionCut.enabled && (
              <div style={styles.regionInputs}>
                <label>
                  Axis
                  <select
                    value={region.directionCut.axis}
                    onChange={(e) => {
                      const ax = Number(e.target.value);
                      setRegion((r) => ({
                        ...r,
                        directionCut: { ...r.directionCut, axis: ax, cut: Math.floor(shape[ax] / 2) },
                      }));
                    }}
                  >
                    <option value={0}>0 ({shape[0]})</option>
                    <option value={1}>1 ({shape[1]})</option>
                    <option value={2}>2 ({shape[2]})</option>
                  </select>
                </label>
                <label>
                  Side
                  <select
                    value={region.directionCut.side}
                    onChange={(e) => setRegion((r) => ({ ...r, directionCut: { ...r.directionCut, side: e.target.value } }))}
                  >
                    <option value="low">Low (keep 0..cut)</option>
                    <option value="high">High (keep cut..end)</option>
                  </select>
                </label>
                <label>
                  Cut slice
                  <input type="number" min={0} max={shape[region.directionCut.axis] - 1}
                    value={region.directionCut.cut}
                    onChange={(e) => setRegion((r) => ({ ...r, directionCut: { ...r.directionCut, cut: Number(e.target.value) } }))}
                  />
                </label>
              </div>
            )}
          </div>
        )}
      </div>

      <div style={styles.actions}>
        <button style={styles.button} disabled={!activeSessionId || isLoading} onClick={() => void handlePreview()}>
          {isLoading && isPreview ? "..." : "Preview"}
        </button>
        <button style={styles.button} disabled={!activeSessionId || isLoading} onClick={() => void handleApply()}>
          {isLoading && !isPreview ? "..." : "Apply"}
        </button>
      </div>

      {/* Operation summary display */}
      <OperationSummary summary={summaryData} changedVoxels={changedVoxels} isPreview={isPreview} />
    </section>
  );
}

function OperationSummary({
  summary,
  changedVoxels,
  isPreview,
}: {
  summary: SummaryData;
  changedVoxels: number | null;
  isPreview: boolean;
}) {
  if (!summary || changedVoxels === null) {
    return <div style={styles.preview}>No preview yet</div>;
  }

  const verb = isPreview ? "would change" : "changed";
  const detailLines = formatSummaryDetails(summary.details);

  return (
    <div style={styles.preview}>
      <div style={styles.summaryHeader}>
        {summary.operation}: <strong>{changedVoxels.toLocaleString()}</strong> voxels {verb}
      </div>
      {detailLines.length > 0 && (
        <div style={styles.summaryDetails}>
          {detailLines.map((line, i) => (
            <div key={i} style={line.startsWith("  ") ? styles.summaryIndent : undefined}>
              {line}
            </div>
          ))}
        </div>
      )}
    </div>
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
  actions: {
    display: "flex",
    gap: 8,
  },
  button: {
    flex: 1,
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "10px 12px",
  },
  preview: {
    color: "var(--text-soft)",
    fontSize: 13,
    padding: "10px 12px",
    borderRadius: 12,
    background: "var(--panel-soft)",
  },
  summaryHeader: {
    marginBottom: 4,
  },
  summaryDetails: {
    marginTop: 6,
    fontSize: 12,
    lineHeight: "1.5",
    opacity: 0.85,
  },
  summaryIndent: {
    paddingLeft: 8,
  },
  regionSection: {
    display: "grid",
    gap: 6,
    fontSize: 13,
  },
  regionLabel: {
    fontWeight: 600,
  },
  checkRow: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    color: "var(--text-soft)",
    fontSize: 13,
    cursor: "pointer",
  },
  regionBody: {
    display: "grid",
    gap: 6,
    paddingLeft: 8,
    borderLeft: "2px solid var(--border)",
  },
  regionInputs: {
    display: "grid",
    gap: 4,
    paddingLeft: 8,
    fontSize: 12,
    color: "var(--text-soft)",
  },
  regionRow: {
    display: "flex",
    alignItems: "center",
    gap: 4,
  },
  regionNum: {
    width: 60,
  },
};
