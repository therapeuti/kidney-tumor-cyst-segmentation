import { useEffect, useMemo, useRef, type CSSProperties } from "react";

import type { SessionMeta, SlicePayload } from "../../types/api";

type OverlayCanvasProps = {
  slice: SlicePayload | null;
  sessionMeta: SessionMeta | null;
  visibleLabels: number[];
  overlayOpacity: number;
};

function colorMapFromMeta(sessionMeta: SessionMeta | null) {
  const map = new Map<number, number[]>();
  for (const item of sessionMeta?.labels ?? []) {
    map.set(item.id, item.color);
  }
  return map;
}

export function OverlayCanvas({
  slice,
  sessionMeta,
  visibleLabels,
  overlayOpacity,
}: OverlayCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const colorMap = useMemo(() => colorMapFromMeta(sessionMeta), [sessionMeta]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !slice) {
      return;
    }

    const width = slice.width;
    const height = slice.height;
    canvas.width = width;
    canvas.height = height;

    const context = canvas.getContext("2d");
    if (!context) {
      return;
    }

    const imageData = context.createImageData(width, height);
    const visible = new Set(visibleLabels);

    for (let y = 0; y < height; y += 1) {
      const row = slice.mask.data[y] ?? [];
      for (let x = 0; x < width; x += 1) {
        const label = row[x] ?? 0;
        const idx = (y * width + x) * 4;
        if (label === 0 || !visible.has(label)) {
          imageData.data[idx + 3] = 0;
          continue;
        }

        const color = colorMap.get(label) ?? [255, 255, 255, 180];
        imageData.data[idx] = color[0];
        imageData.data[idx + 1] = color[1];
        imageData.data[idx + 2] = color[2];
        imageData.data[idx + 3] = Math.round((color[3] ?? 180) * overlayOpacity);
      }
    }

    context.clearRect(0, 0, width, height);
    context.putImageData(imageData, 0, 0);
  }, [colorMap, overlayOpacity, slice, visibleLabels]);

  if (!slice) {
    return null;
  }

  return <canvas ref={canvasRef} style={styles.canvas} />;
}

const styles: Record<string, CSSProperties> = {
  canvas: {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    imageRendering: "pixelated",
    pointerEvents: "none",
    borderRadius: 14,
  },
};
