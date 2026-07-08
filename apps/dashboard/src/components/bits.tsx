// Petites pièces partagées : punaise, tampon, glyphe pixel, chip.

export function Pin({ lime = false }: { lime?: boolean }) {
  const id = lime ? "pin-lime" : "pin-steel";
  return (
    <svg viewBox="0 0 24 34" className="size-7" aria-hidden="true">
      <defs>
        <radialGradient id={id} cx="32%" cy="28%" r="68%">
          {lime ? (
            <>
              <stop offset="0%" stopColor="#f8ff9a" />
              <stop offset="40%" stopColor="#e4f222" />
              <stop offset="100%" stopColor="#9aad00" />
            </>
          ) : (
            <>
              <stop offset="0%" stopColor="#f8f8f6" />
              <stop offset="40%" stopColor="#c8c8c4" />
              <stop offset="100%" stopColor="#5a5a56" />
            </>
          )}
        </radialGradient>
      </defs>
      <ellipse cx="12" cy="12.5" rx="5.8" ry="1.3" fill="rgba(0,0,0,0.12)" />
      <circle cx="12" cy="9.5" r="7.2" fill={`url(#${id})`} />
      <ellipse cx="9.8" cy="7.4" rx="2.4" ry="1.5" fill="white" opacity="0.6" />
      <rect x="11.15" y="15.2" width="1.7" height="13.5" rx="0.85" fill="#6d6d69" />
      <path d="M12 28.7 L10.4 32.2 L13.6 32.2 Z" fill="#3a3a38" />
    </svg>
  );
}

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
      className="inline-block -rotate-6 border-[1.5px] px-1.5 py-px text-[9px] font-semibold uppercase tracking-[0.14em]"
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
}: {
  address: string;
  role: "builder" | "juge" | null;
  muted?: boolean;
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
      width={14}
      height={14}
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
      className="rounded-[3px] px-1 py-px text-[9px] font-semibold uppercase tracking-[0.1em] text-white"
      style={{ backgroundColor: color }}
    >
      {role}
    </span>
  );
}

export function DashedRule() {
  return <div className="my-2 border-t border-dashed border-line" />;
}
