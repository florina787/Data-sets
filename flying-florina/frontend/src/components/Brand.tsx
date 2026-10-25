import { useState } from "react";

/** Uses the locally provided, authorized logo when present; otherwise the neutral placeholder mark. */
export function BrandMark({ size = 40 }: { size?: number }) {
  const [src, setSrc] = useState("/brand/florina-logo.png");
  return (
    <img
      src={src}
      onError={() => setSrc("/brand/ff-mark.svg")}
      width={size}
      height={size}
      alt="Flying_Florina logo"
      className="rounded-full ring-2 ring-gold/70 object-cover"
      style={{ width: size, height: size }}
    />
  );
}
