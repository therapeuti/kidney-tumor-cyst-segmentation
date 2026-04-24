import type { CSSProperties } from "react";

type SliceCanvasProps = {
  src: string | null;
  alt: string;
};

export function SliceCanvas({ src, alt }: SliceCanvasProps) {
  if (!src) {
    return null;
  }

  return <img key={src} src={src} alt={alt} style={styles.image} loading="eager" />;
}

const styles: Record<string, CSSProperties> = {
  image: {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    imageRendering: "pixelated",
    borderRadius: 14,
  },
};
