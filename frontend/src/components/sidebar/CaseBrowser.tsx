import type { CSSProperties } from "react";

import { useSessionStore } from "../../stores/sessionStore";

export function CaseBrowser() {
  const cases = useSessionStore((state) => state.cases);
  const selectedCaseId = useSessionStore((state) => state.selectedCaseId);
  const setSelectedCaseId = useSessionStore((state) => state.setSelectedCaseId);

  return (
    <section style={styles.panel}>
      <h3 style={styles.heading}>Cases</h3>
      <div style={styles.list}>
        {cases.length === 0 ? <div style={styles.empty}>No cases found</div> : null}
        {cases.map((item) => (
          <button
            key={item.caseId}
            onClick={() => setSelectedCaseId(item.caseId)}
            style={{
              ...styles.caseButton,
              ...(selectedCaseId === item.caseId ? styles.caseButtonActive : {}),
            }}
          >
            <span>{item.caseId}</span>
            <span style={styles.badge}>{item.phases.join(", ")}</span>
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
  list: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  empty: {
    color: "var(--text-soft)",
    fontSize: 13,
  },
  caseButton: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    width: "100%",
    background: "var(--panel-soft)",
    border: "1px solid transparent",
    color: "var(--text)",
    borderRadius: 12,
    padding: "10px 12px",
  },
  caseButtonActive: {
    border: "1px solid var(--accent)",
    boxShadow: "0 0 0 1px rgba(90, 209, 255, 0.15) inset",
  },
  badge: {
    color: "var(--text-soft)",
    fontSize: 12,
  },
};
