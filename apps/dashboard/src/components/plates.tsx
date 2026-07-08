// Les nodes du canvas Réseau (style plaques Cofounder) : le centre-chaîne
// en écran sombre, et une plaque par agent.

import type { NodeProps } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import { RoleChip } from "./bits";

const handleStyle = {
  opacity: 0,
  width: 1,
  height: 1,
  border: 0,
  left: "50%",
  top: "50%",
  pointerEvents: "none" as const,
};

export type ChainData = { height: number; round: number; blockTick: number };

export function ChainPlate({ data }: NodeProps) {
  const { height, round, blockTick } = data as ChainData;
  return (
    <div className="w-[190px] rounded-[10px] bg-card p-[3px] shadow-[0_2px_6px_rgba(30,25,10,0.10),0_10px_30px_rgba(30,25,10,0.08)]">
      <Handle type="source" position={Position.Top} style={handleStyle} />
      <div
        key={blockTick}
        className="block-tick relative overflow-hidden rounded-[8px] bg-screen px-4 py-4 text-center"
      >
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "linear-gradient(135deg, rgba(255,255,255,0.10) 0%, rgba(255,255,255,0.02) 60%)",
            clipPath: "polygon(0 0, 100% 0, 82% 100%, 0 100%)",
          }}
        />
        <p className="text-[9px] uppercase tracking-[0.22em] text-white/45">agentarena</p>
        <p className="mt-1 font-display text-[40px] leading-none text-white/90">{height}</p>
        <p className="mt-1 text-[9px] uppercase tracking-[0.14em] text-white/40">
          bloc finalise · round {round}
        </p>
      </div>
    </div>
  );
}

export type AgentData = {
  name: string;
  address: string;
  height: number | null;
  networkHeight: number;
  stake: number;
  jailed: boolean;
  proposer: boolean;
  role: "builder" | "juge" | null;
};

export function AgentPlate({ data }: NodeProps) {
  const agent = data as AgentData;
  const down = agent.height === null;
  const late = !down && agent.height! < agent.networkHeight - 1;
  const ring = agent.proposer
    ? "0 0 0 2px var(--color-olive)"
    : "inset 0 0 0 1px rgba(30,25,10,0.07)";
  return (
    <div
      className={`w-[168px] rounded-[8px] bg-card px-3 py-2.5 shadow-[0_1px_2px_rgba(30,25,10,0.05),0_5px_14px_rgba(30,25,10,0.08)] transition-opacity ${down || agent.jailed ? "opacity-55" : ""}`}
      style={{ boxShadow: `${ring}, 0 1px 2px rgba(30,25,10,0.05), 0 5px 14px rgba(30,25,10,0.08)` }}
    >
      <Handle type="target" position={Position.Top} style={handleStyle} />
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.06em]">
          {agent.name}
        </span>
        {agent.role && <RoleChip role={agent.role} />}
      </div>
      <p className="mt-0.5 text-[8px] tracking-[0.08em] text-ink-faint">
        {agent.address.slice(0, 12)}...
      </p>
      <div className="mt-2 flex items-center justify-between border-t border-dashed border-line pt-1.5">
        <span className="flex items-center gap-1 text-[9px] tabular-nums text-ink-soft">
          <span
            className="inline-block size-1.5 rounded-full"
            style={{
              backgroundColor: down
                ? "var(--color-danger)"
                : late
                  ? "var(--color-amber)"
                  : "var(--color-olive)",
            }}
          />
          {down ? "down" : `h=${agent.height}`}
        </span>
        <span className="text-[9px] tabular-nums text-ink-soft">
          stake {agent.stake.toLocaleString("fr-FR")}
        </span>
      </div>
      {agent.proposer && (
        <p className="mt-1 text-[8px] font-semibold uppercase tracking-[0.14em] text-olive">
          proposer
        </p>
      )}
      {agent.jailed && (
        <p className="mt-1 text-[8px] font-semibold uppercase tracking-[0.14em] text-danger">
          jailed
        </p>
      )}
    </div>
  );
}
