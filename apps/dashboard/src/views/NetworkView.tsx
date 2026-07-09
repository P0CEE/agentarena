// Vue Réseau : le canvas spatial de la référence — un grand cercle fin qui
// porte les agents, des rayons pointillés à connecteurs vers le centre. Le
// rayon du proposer courant est olive.

import { useEffect, useMemo, useState } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ViewportPortal,
  useNodesState,
  type Node,
} from "@xyflow/react";
import type { Task } from "../api";
import type { Network, NodeEntry } from "../hooks";
import { PixelIcon, RoleChip } from "../components/bits";
import { AgentPill, CenterPlate } from "../components/plates";

const nodeTypes = { center: CenterPlate, agent: AgentPill };

const RADIUS = 430;
const PILL = { w: 128, h: 32 };
const CENTER = { w: 176, h: 92 };

const CIRCLE_STROKE = "rgba(0, 0, 0, 0.14)";
const SPOKE_STROKE = "rgba(0, 0, 0, 0.22)";
const DOT_STROKE = "rgba(0, 0, 0, 0.30)";

type Spoke = { key: string; angle: number; proposer: boolean };

function roleOf(activeTask: Task | null, address: string): "builder" | "juge" | null {
  if (!activeTask) return null;
  if (activeTask.builders.includes(address)) return "builder";
  if (activeTask.judges.includes(address)) return "juge";
  return null;
}

function buildNodes(
  network: Network,
  activeTask: Task | null,
  count: number,
  selected: string | null,
): Node[] {
  const flowNodes: Node[] = [
    {
      id: "center",
      type: "center",
      position: { x: -CENTER.w / 2, y: -CENTER.h / 2 },
      draggable: false,
      data: {
        height: network.height,
        round: network.nodes[0]?.status?.round ?? 0,
      },
    },
  ];
  network.nodes.forEach((entry, index) => {
    const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
    const address = entry.status?.address ?? "";
    const info = network.agents[address];
    flowNodes.push({
      id: entry.name,
      type: "agent",
      position: {
        x: Math.cos(angle) * RADIUS - PILL.w / 2,
        y: Math.sin(angle) * RADIUS - PILL.h / 2,
      },
      data: {
        name: entry.name,
        address,
        down: entry.status === null,
        late: entry.status !== null && entry.status.height < network.height - 1,
        jailed: info ? info.jailed_until > network.height : false,
        proposer: entry.status?.proposer_next ?? false,
        selected: selected !== null && selected === entry.name,
        role: roleOf(activeTask, address),
      },
    });
  });
  return flowNodes;
}

export function NetworkView({
  network,
  activeTask,
  onTransfer,
}: {
  network: Network;
  activeTask: Task | null;
  onTransfer: (address: string) => void;
}) {
  const count = Math.max(network.nodes.length, 1);
  const [selected, setSelected] = useState<string | null>(null);

  // Pattern controle de React Flow v12 : setNodes + onNodesChange, sinon les
  // mesures des nodes se perdent a chaque refetch et ils restent invisibles.
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  useEffect(() => {
    setNodes(buildNodes(network, activeTask, count, selected));
  }, [network, activeTask, count, selected, setNodes]);

  const selectedEntry = network.nodes.find((entry) => entry.name === selected) ?? null;

  const spokes = useMemo<Spoke[]>(
    () =>
      network.nodes.map((entry, index) => ({
        key: entry.name,
        angle: -Math.PI / 2 + (index * 2 * Math.PI) / count,
        proposer: entry.status?.proposer_next ?? false,
      })),
    [network.nodes, count],
  );

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        onNodesChange={onNodesChange}
        edges={[]}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.14 }}
        minZoom={0.25}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        onNodeClick={(_, node) => {
          if (node.type === "agent") {
            setSelected((current) => (current === node.id ? null : node.id));
          }
        }}
        onPaneClick={() => setSelected(null)}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={2.2} color="#dcdcdc" />
        <ViewportPortal>
          <Rings spokes={spokes} />
        </ViewportPortal>
      </ReactFlow>
      {selectedEntry ? (
        <NodePanel
          entry={selectedEntry}
          network={network}
          role={roleOf(activeTask, selectedEntry.status?.address ?? "")}
          onClose={() => setSelected(null)}
          onTransfer={(address) => {
            setSelected(null);
            onTransfer(address);
          }}
        />
      ) : (
        <Legend />
      )}
    </div>
  );
}

// Fiche du node selectionne : centree sur le canvas, dans l'esprit de la
// plaque centrale (ecran clair, reflet, cadre carte).
function NodePanel({
  entry,
  network,
  role,
  onClose,
  onTransfer,
}: {
  entry: NodeEntry;
  network: Network;
  role: "builder" | "juge" | null;
  onClose: () => void;
  onTransfer: (address: string) => void;
}) {
  const status = entry.status;
  const address = status?.address ?? "";
  const info = network.agents[address];
  const fmt = new Intl.NumberFormat("fr-FR");
  const state = !status
    ? { label: "down", color: "var(--color-danger)" }
    : info && info.jailed_until > network.height
      ? { label: "jailed", color: "var(--color-danger)" }
      : status.height < network.height - 1
        ? { label: "en retard", color: "var(--color-amber)" }
        : { label: "en consensus", color: "var(--color-olive)" };

  return (
    <div
      className="absolute inset-0 z-10 grid place-items-center bg-ink/10 backdrop-blur-[1.5px]"
      onClick={onClose}
    >
      <div
        className="receipt-drop w-[480px] max-w-[calc(100%-32px)] rounded-[14px] p-1 shadow-[0_2px_6px_rgba(0,0,0,0.10),0_28px_64px_rgba(0,0,0,0.22)]"
        style={{ backgroundColor: "var(--color-card)" }}
        onClick={(event) => event.stopPropagation()}
      >
        {/* l'ecran : identite du node */}
        <div className="relative overflow-hidden rounded-[11px] bg-[#f2f2f2] px-5 py-4 shadow-[inset_0_1px_2px_rgba(0,0,0,0.07)]">
          <div
            className="pointer-events-none absolute inset-0"
            style={{
              background:
                "linear-gradient(135deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0) 60%)",
              clipPath: "polygon(0 0, 100% 0, 82% 100%, 0 100%)",
            }}
          />
          <div className="relative flex items-center gap-3.5">
            <span className="grid size-12 shrink-0 place-items-center rounded-[10px] bg-card shadow-[0_1px_3px_rgba(0,0,0,0.10)]">
              <PixelIcon address={address} role={role} size={30} />
            </span>
            <div className="min-w-0">
              <p className="font-display text-[28px] leading-none">{entry.name}</p>
              <p className="mt-1.5 font-mono text-[11px] text-ink-soft">{entry.url}</p>
            </div>
            <div className="ml-auto mr-7 flex flex-col items-end gap-1.5">
              <span
                className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.14em]"
                style={{ color: state.color }}
              >
                <span
                  className="size-2 rounded-full"
                  style={{ backgroundColor: state.color }}
                />
                {state.label}
              </span>
              {role && <RoleChip role={role} />}
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="fermer"
            className="absolute right-3 top-3 text-ink-faint transition hover:text-ink"
          >
            <svg
              viewBox="0 0 16 16"
              className="size-4"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              aria-hidden="true"
            >
              <path d="M4 4l8 8M12 4l-8 8" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        <div className="px-4 py-3.5">
          <CopyRow label="adresse ed25519" value={address} />
          {status ? (
            <div className="mt-3 grid grid-cols-3 gap-2">
              <PanelStat label="hauteur" value={String(status.height)} />
              <PanelStat label="round" value={`r${status.round}`} />
              <PanelStat label="mempool" value={`${status.mempool} tx`} />
              <PanelStat label="pairs" value={String(status.peers.length)} />
              <PanelStat label="stake libre" value={info ? fmt.format(info.free) : "—"} />
              <PanelStat label="verrouillé" value={info ? fmt.format(info.locked) : "—"} />
            </div>
          ) : (
            <p className="mt-3 text-[12px] text-ink-soft">
              node injoignable — dernier état inconnu
            </p>
          )}
          {status?.proposer_next && (
            <p
              className="mt-3 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: "var(--color-olive)" }}
            >
              <span
                className="inline-block h-0 w-5 border-t-2 border-dashed"
                style={{ borderColor: "var(--color-olive)" }}
              />
              proposer du prochain bloc
            </p>
          )}
          {address && (
            <button
              onClick={() => onTransfer(address)}
              className="mt-3 w-full rounded-[8px] bg-ink py-2 text-[12px] font-medium text-paper transition hover:opacity-85"
            >
              envoyer un transfer à ce node
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function CopyRow({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  if (!value) return null;
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      title="copier l'adresse"
      className="group w-full rounded-[8px] bg-ink/[0.04] px-3 py-2 text-left transition hover:bg-ink/[0.07]"
    >
      <span className="flex items-center justify-between text-[9px] uppercase tracking-[0.12em] text-ink-soft">
        {label}
        <span
          className="opacity-0 transition group-hover:opacity-100"
          style={copied ? { color: "var(--color-olive)", opacity: 1 } : undefined}
        >
          {copied ? "copié ✓" : "copier"}
        </span>
      </span>
      <span className="mt-1 block break-all font-mono text-[12px] leading-[1.55] text-ink">
        {value}
      </span>
    </button>
  );
}

function PanelStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[8px] bg-ink/[0.04] px-2.5 py-2">
      <p className="text-[9px] uppercase tracking-[0.1em] text-ink-soft">{label}</p>
      <p className="mt-0.5 text-[17px] leading-tight tabular-nums text-ink">{value}</p>
    </div>
  );
}

// Distance du centre d'un rectangle a son bord, le long d'une direction.
function edgeDistance(halfW: number, halfH: number, angle: number): number {
  const cos = Math.abs(Math.cos(angle));
  const sin = Math.abs(Math.sin(angle));
  return Math.min(cos > 1e-6 ? halfW / cos : Infinity, sin > 1e-6 ? halfH / sin : Infinity);
}

function Rings({ spokes }: { spokes: Spoke[] }) {
  const margin = RADIUS + 90;
  return (
    <svg
      width={2 * margin}
      height={2 * margin}
      viewBox={`${-margin} ${-margin} ${2 * margin} ${2 * margin}`}
      style={{
        position: "absolute",
        left: -margin,
        top: -margin,
        pointerEvents: "none",
        // Le portal viewport est rendu apres la couche des nodes : sans
        // z-index negatif, les anneaux se dessinent par-dessus les pills.
        zIndex: -1,
      }}
    >
      <circle cx={0} cy={0} r={RADIUS} fill="none" stroke={CIRCLE_STROKE} strokeWidth={1.6} />
      {spokes.map((spoke) => {
        const inner = edgeDistance(CENTER.w / 2, CENTER.h / 2, spoke.angle) + 12;
        const outer = RADIUS - edgeDistance(PILL.w / 2, PILL.h / 2, spoke.angle) - 12;
        const cos = Math.cos(spoke.angle);
        const sin = Math.sin(spoke.angle);
        const stroke = spoke.proposer ? "var(--color-olive)" : SPOKE_STROKE;
        return (
          <g key={spoke.key}>
            <line
              x1={cos * inner}
              y1={sin * inner}
              x2={cos * outer}
              y2={sin * outer}
              stroke={stroke}
              strokeWidth={1.5}
              strokeDasharray="7 7"
              strokeLinecap="round"
            />
            {[inner, outer].map((distance) => (
              <circle
                key={distance}
                cx={cos * distance}
                cy={sin * distance}
                r={3.2}
                fill="var(--color-card)"
                stroke={DOT_STROKE}
                strokeWidth={1}
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}

function Legend() {
  const swatch = (color: string) => (
    <span className="inline-block size-2 rounded-[2px]" style={{ backgroundColor: color }} />
  );
  return (
    <div
      className="pointer-events-none absolute bottom-3 left-3 space-y-1 rounded-[7px] px-2.5 py-2 text-[9px] uppercase tracking-[0.08em] text-ink-faint shadow-[0_1px_4px_rgba(0,0,0,0.08)]"
      style={{ backgroundColor: "var(--color-card)" }}
    >
      <div className="flex items-center gap-1.5">
        {swatch("var(--color-amber)")}
        <span>builder de la manche active</span>
      </div>
      <div className="flex items-center gap-1.5">
        {swatch("var(--color-violet)")}
        <span>juge de la manche active</span>
      </div>
      <div className="flex items-center gap-1.5">
        <span
          className="inline-block h-0 w-3.5 border-t-2 border-dashed"
          style={{ borderColor: "var(--color-olive)" }}
        />
        <span>proposer du prochain bloc</span>
      </div>
      <div className="flex items-center gap-1.5">
        {swatch("var(--color-ink-faint)")}
        <span>sans role / delave = down ou jailed</span>
      </div>
    </div>
  );
}
