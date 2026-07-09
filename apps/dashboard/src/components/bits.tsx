// Petites pièces partagées : tampon, glyphe pixel, chip.

const STAMP_COLORS: Record<string, string> = {
  COMMITTED: "var(--color-ink-faint)",
  REVEAL_OK: "var(--color-olive)",
  MISMATCH: "var(--color-danger)",
  OPEN: "var(--color-amber)",
  SCORING: "var(--color-violet)",
  SETTLED: "var(--color-olive)",
};

const STAMP_LABELS: Record<string, string> = {
  COMMITTED: "scelle",
  REVEAL_OK: "revele",
  MISMATCH: "mismatch",
};

export function Stamp({ value }: { value: string }) {
  const color = STAMP_COLORS[value] ?? "var(--color-ink-soft)";
  return (
    <span
      className="inline-block -rotate-6 border-[1.5px] px-1.5 py-px text-[10px] font-semibold uppercase tracking-[0.14em]"
      style={{ color, borderColor: color }}
    >
      {STAMP_LABELS[value] ?? value}
    </span>
  );
}

// Glyphe pixel du logo, dans l'esprit des icones departement de la reference.
export function PixelGlyph({ size = 16 }: { size?: number }) {
  const cells: Array<[number, number, string]> = [
    [1, 0, "#e77b14"], [2, 0, "#ed9037"],
    [0, 1, "#b45f10"], [3, 1, "#e77b14"],
    [0, 2, "#8a72e5"], [1, 2, "#7a9200"], [2, 2, "#7a9200"], [3, 2, "#8a72e5"],
    [0, 3, "#8a72e5"], [3, 3, "#8a72e5"],
  ];
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 4 4"
      style={{ imageRendering: "pixelated" }}
      aria-hidden="true"
    >
      {cells.map(([x, y, fill]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" fill={fill} />
      ))}
    </svg>
  );
}

// Icone pixel identicon : deterministe par adresse, palette par role
// (comme les icones departement de la reference).
const ICON_PALETTES: Record<string, string[]> = {
  builder: ["#e77b14", "#ed9037", "#b45f10"],
  juge: ["#8a72e5", "#9b83f8", "#5a3fd6"],
  none: ["#a8a69b", "#8b897e", "#6f6d64"],
};

export function PixelIcon({
  address,
  role,
  muted = false,
  size = 14,
}: {
  address: string;
  role: "builder" | "juge" | null;
  muted?: boolean;
  size?: number;
}) {
  const palette = ICON_PALETTES[role ?? "none"];
  const hex = address || "0";
  const cells: Array<[number, number, string]> = [];
  for (let row = 0; row < 5; row += 1) {
    for (let col = 0; col < 3; col += 1) {
      const nibble = parseInt(hex[(row * 3 + col) % hex.length], 16) || 0;
      if (nibble >= 7) {
        const fill = palette[(row + col) % palette.length];
        cells.push([col, row, fill]);
        if (col < 2) cells.push([4 - col, row, fill]); // symetrie identicon
      }
    }
  }
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 5 5"
      style={{ imageRendering: "pixelated", opacity: muted ? 0.45 : 1 }}
      className="shrink-0"
      aria-hidden="true"
    >
      {cells.map(([x, y, fill], index) => (
        <rect key={index} x={x} y={y} width="1" height="1" fill={fill} />
      ))}
    </svg>
  );
}

export function RoleChip({ role }: { role: "builder" | "juge" | "sponsor" }) {
  const color =
    role === "builder"
      ? "var(--color-amber)"
      : role === "juge"
        ? "var(--color-violet)"
        : "var(--color-olive)";
  return (
    <span
      className="rounded-[3px] px-1.5 py-px text-[10px] font-semibold uppercase tracking-[0.1em] text-white"
      style={{ backgroundColor: color }}
    >
      {role}
    </span>
  );
}

export function DashedRule() {
  return <div className="my-2 border-t border-dashed border-line" />;
}
