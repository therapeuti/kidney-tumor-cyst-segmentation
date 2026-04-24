import { useState, type CSSProperties } from "react";

import { fetchPhaseComparison, type ComparisonData } from "../../api/comparison";
import { useSessionStore } from "../../stores/sessionStore";

export function ComparisonPanel() {
  const [data, setData] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const selectedCaseId = useSessionStore((state) => state.selectedCaseId);

  async function handleLoad() {
    if (!selectedCaseId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await fetchPhaseComparison(selectedCaseId);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load comparison");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Phase Comparison</h3>
      <button style={styles.button} disabled={!selectedCaseId || loading} onClick={() => void handleLoad()}>
        {loading ? "Loading..." : "Compare Phases"}
      </button>
      {error && <div style={styles.error}>{error}</div>}
      {data && (
        <div style={styles.results}>
          <div style={styles.sectionTitle}>Voxel Counts</div>
          <table style={styles.table}>
            <thead>
              <tr>
                <th>Label</th>
                {data.phases.map((p) => <th key={p}>{p}</th>)}
              </tr>
            </thead>
            <tbody>
              {[1, 2, 3].map((label) => {
                const stats = data.labelStats.filter((s) => s.label === label);
                if (stats.length === 0) return null;
                return (
                  <tr key={label}>
                    <td>{stats[0].labelName}</td>
                    {data.phases.map((phase) => {
                      const s = stats.find((x) => x.phase === phase);
                      return <td key={phase}>{s ? s.voxelCount.toLocaleString() : "-"}</td>;
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>

          {data.diceScores.length > 0 && (
            <>
              <div style={styles.sectionTitle}>Dice Coefficients</div>
              <table style={styles.table}>
                <thead>
                  <tr>
                    <th>Pair</th>
                    <th>Label</th>
                    <th>Dice</th>
                  </tr>
                </thead>
                <tbody>
                  {data.diceScores.map((d, i) => (
                    <tr key={i}>
                      <td>{d.phaseA}-{d.phaseB}</td>
                      <td>{d.labelName}</td>
                      <td style={{ color: d.dice >= 0.8 ? "var(--accent)" : d.dice >= 0.5 ? "#e0c060" : "#e06060" }}>
                        {d.dice.toFixed(4)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
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
    gap: 10,
  },
  heading: {
    margin: 0,
    fontSize: 15,
  },
  button: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "10px 12px",
  },
  error: {
    color: "#e06060",
    fontSize: 12,
  },
  results: {
    display: "grid",
    gap: 8,
    fontSize: 12,
  },
  sectionTitle: {
    fontWeight: 700,
    fontSize: 13,
    marginTop: 4,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    textAlign: "right",
    fontSize: 12,
    color: "var(--text-soft)",
  },
};
