// Les nodes du canvas Réseau, dans l'esprit du canvas de référence :
// un centre sobre (wordmark serif sur écran clair) et des pills compactes
// (icône pixel + nom) posées sur le cercle.

import type { NodeProps } from "@xyflow/react";
import { PixelGlyph, PixelIcon } from "./bits";

export type CenterData = { height: number; round: number };

export function CenterPlate({ data }: NodeProps) {
  const { height, round } = data as CenterData;
  return (
    <div className="relative w-[176px]">
      <div className="pointer-events-none absolute -top-7 left-1/2 -translate-x-1/2 opacity-80">
        <PixelGlyph size={20} />
      </div>
      <div className="rounded-[10px] bg-card p-[3px] shadow-[0_2px_5px_rgba(30,25,10,0.08),0_12px_28px_rgba(30,25,10,0.07)]">
        <div className="relative overflow-hidden rounded-[8px] bg-[#edebdf] px-4 py-4 text-center shadow-[inset_0_1px_2px_rgba(30,25,10,0.07)]">
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "linear-gradient(135deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 60%)",
              clipPath: "polygon(0 0, 100% 0, 82% 100%, 0 100%)",
            }}
          />
          <p className="relative font-display text-[24px] leading-none text-ink/85">
            AgentArena
          </p>
          <p className="relative mt-2 text-[8px] uppercase tracking-[0.2em] text-ink-faint">
            bloc {height} · round {round}
          </p>
        </div>
      </div>
    </div>
  );
}

export type PillData = {
  name: string;
  address: string;
  down: boolean;
  late: boolean;
  jailed: boolean;
  proposer: boolean;
  role: "builder" | "juge" | null;
};

export function AgentPill({ data }: NodeProps) {
  const pill = data as PillData;
  const dim = pill.down || pill.jailed;
  const shadow = pill.proposer
    ? "0 0 0 1.5px var(--color-olive), 0 2px 8px rgba(122,146,0,0.22), 0 4px 10px rgba(30,25,10,0.06)"
    : dim
      ? "inset 0 0 0 1px rgba(30,25,10,0.06), inset 0 2px 3px rgba(30,25,10,0.08)"
      : "0 1px 2px rgba(30,25,10,0.06), 0 4px 10px rgba(30,25,10,0.08)";
  const state = pill.down ? "down" : pill.jailed ? "jailed" : pill.late ? "en retard" : "ok";
  return (
    <div
      className={`flex h-[30px] w-[116px] items-center justify-center gap-1.5 rounded-[8px] px-2 ${
        dim ? "bg-paper" : "bg-card"
      }`}
      style={{ boxShadow: shadow }}
      title={`${pill.address.slice(0, 12)}... · ${state}`}
    >
      <PixelIcon address={pill.address} role={pill.role} muted={dim} />
      <span className={`text-[12px] ${dim ? "text-ink-faint" : "text-ink-soft"}`}>
        {pill.name}
      </span>
      {(pill.down || pill.late) && (
        <span
          className="size-1.5 shrink-0 rounded-full"
          style={{
            backgroundColor: pill.down ? "var(--color-danger)" : "var(--color-amber)",
          }}
        />
      )}
    </div>
  );
}
