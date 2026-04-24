import type { CSSProperties } from "react";

import { useSessionStore } from "../../stores/sessionStore";

export function PhaseTabs() {
  const selectedCase = useSessionStore((state) =>
    state.cases.find((item) => item.caseId === state.selectedCaseId) ?? null,
  );
  const selectedPhase = useSessionStore((state) => state.selectedPhase);
  const setSelectedPhase = useSessionStore((state) => state.setSelectedPhase);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Phases</h3>
      <div style={styles.row}>
        {(selectedCase?.phases ?? []).map((phase) => (
          <button
            key={phase}
            onClick={() => setSelectedPhase(phase)}
            style={{
              ...styles.tab,
              ...(selectedPhase === phase ? styles.activeTab : {}),
            }}
          >
            {phase}
          </button>
        ))}
        {!selectedCase ? <div style={styles.empty}>Select a case to see phases</div> : null}
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
  row: {
    display: "flex",
    gap: 8,
    flexWrap: "wrap",
  },
  tab: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid transparent",
    borderRadius: 999,
    padding: "8px 12px",
    minWidth: 48,
  },
  activeTab: {
    border: "1px solid var(--accent)",
    color: "#001019",
    background: "var(--accent)",
  },
  empty: {
    color: "var(--text-soft)",
    fontSize: 13,
  },
};
