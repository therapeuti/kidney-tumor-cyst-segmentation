import type { CSSProperties } from "react";

type SliceNavigatorProps = {
  sliceIndex: number;
  maxSlice: number;
  onChange: (next: number) => void;
};

export function SliceNavigator({ sliceIndex, maxSlice, onChange }: SliceNavigatorProps) {
  return (
    <div style={styles.wrap}>
      <button style={styles.button} onClick={() => onChange(Math.max(0, sliceIndex - 1))}>
        Prev
      </button>
      <input
        type="range"
        min="0"
        max={Math.max(maxSlice, 0)}
        step="1"
        value={Math.min(sliceIndex, Math.max(maxSlice, 0))}
        onChange={(event) => onChange(Number(event.target.value))}
        style={styles.slider}
      />
      <button style={styles.button} onClick={() => onChange(Math.min(maxSlice, sliceIndex + 1))}>
        Next
      </button>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  wrap: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  button: {
    background: "var(--panel-soft)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "8px 12px",
  },
  slider: {
    flex: 1,
  },
};
