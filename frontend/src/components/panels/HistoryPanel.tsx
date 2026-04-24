import { useRef, useEffect, type CSSProperties } from "react";

import { useSessionStore } from "../../stores/sessionStore";

function formatTime(ts: number): string {
  const d = new Date(ts);
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
}

export function HistoryPanel() {
  const activeSessionId = useSessionStore((state) => state.activeSessionId);
  const sessionStatus = useSessionStore((state) => state.sessionStatus);
  const operationLog = useSessionStore((state) => state.operationLog);
  const logEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [operationLog.length]);

  return (
    <section style={styles.panel}>
      <div style={styles.header}>
        <h3 style={styles.heading}>History</h3>
        <span style={styles.subtle}>
          {sessionStatus
            ? `Undo: ${sessionStatus.canUndo ? "Y" : "N"} | Redo: ${sessionStatus.canRedo ? "Y" : "N"} | ${sessionStatus.dirty ? "Unsaved" : "Saved"}`
            : "No session"}
        </span>
      </div>
      <div style={styles.log}>
        {operationLog.length === 0 ? (
          <div style={styles.item}>No operations yet.</div>
        ) : (
          operationLog.map((entry, i) => (
            <div key={i} style={styles.item}>
              <span style={styles.time}>{formatTime(entry.timestamp)}</span> {entry.message}
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </section>
  );
}

const styles: Record<string, CSSProperties> = {
  panel: {
    background: "var(--panel)",
    border: "1px solid var(--border)",
    borderRadius: 18,
    padding: 14,
    minHeight: 0,
    display: "grid",
    gridTemplateRows: "auto 1fr",
    gap: 8,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    gap: 12,
  },
  heading: {
    margin: 0,
    fontSize: 15,
  },
  subtle: {
    color: "var(--text-soft)",
    fontSize: 11,
  },
  log: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
    overflow: "auto",
    maxHeight: 220,
  },
  item: {
    padding: "6px 10px",
    borderRadius: 10,
    background: "var(--panel-soft)",
    color: "var(--text-soft)",
    fontSize: 11,
    lineHeight: "1.4",
  },
  time: {
    opacity: 0.5,
    marginRight: 4,
  },
};
