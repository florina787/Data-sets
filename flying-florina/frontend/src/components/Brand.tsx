import { useState } from "react";

/** The Flying Florina emblem (original, public/brand/ff-emblem.svg); falls back to the neutral placeholder mark. */
export function BrandMark({ size = 40 }: { size?: number }) {
  const [src, setSrc] = useState("/brand/ff-emblem.svg");
  return (
    <img
      src={src}
      onError={() => setSrc("/brand/ff-mark.svg")}
      width={size}
      height={size}
      alt="Flying_Florina logo"
      className="rounded-full object-cover drop-shadow-[0_2px_6px_rgba(15,40,80,0.25)]"
      style={{ width: size, height: size }}
    />
  );
}
