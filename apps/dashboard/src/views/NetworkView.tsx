// Vue Réseau : le canvas spatial de la référence — un grand cercle fin qui
// porte les agents, des rayons pointillés à connecteurs vers le centre. Le
// rayon du proposer courant est olive.

import { useEffect, useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ViewportPortal,
  useNodesState,
  type Node,
} from "@xyflow/react";
import type { Task } from "../api";
import type { Network } from "../hooks";
import { AgentPill, CenterPlate } from "../components/plates";

const nodeTypes = { center: CenterPlate, agent: AgentPill };

const RADIUS = 430;
const PILL = { w: 116, h: 30 };
const CENTER = { w: 176, h: 92 };

const CIRCLE_STROKE = "rgba(42, 41, 36, 0.20)";
const SPOKE_STROKE = "rgba(42, 41, 36, 0.30)";
const DOT_STROKE = "rgba(42, 41, 36, 0.38)";

type Spoke = { key: string; angle: number; proposer: boolean };

function buildNodes(network: Network, activeTask: Task | null, count: number): Node[] {
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
        role: activeTask
          ? activeTask.builders.includes(address)
            ? ("builder" as const)
            : activeTask.judges.includes(address)
              ? ("juge" as const)
              : null
          : null,
      },
    });
  });
  return flowNodes;
}

export function NetworkView({
  network,
  activeTask,
}: {
  network: Network;
  activeTask: Task | null;
}) {
  const count = Math.max(network.nodes.length, 1);

  // Pattern controle de React Flow v12 : setNodes + onNodesChange, sinon les
  // mesures des nodes se perdent a chaque refetch et ils restent invisibles.
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  useEffect(() => {
    setNodes(buildNodes(network, activeTask, count));
  }, [network, activeTask, count, setNodes]);

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
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={2.2} color="#cfc9b2" />
        <ViewportPortal>
          <Rings spokes={spokes} />
        </ViewportPortal>
      </ReactFlow>
      <Legend />
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
      style={{ position: "absolute", left: -margin, top: -margin, pointerEvents: "none" }}
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
      className="pointer-events-none absolute bottom-4 left-4 space-y-1.5 rounded-[8px] px-3 py-2.5 text-[9px] uppercase tracking-[0.1em] text-ink-soft shadow-[0_1px_4px_rgba(30,25,10,0.10)]"
      style={{ backgroundColor: "var(--color-card)" }}
    >
      <div className="flex items-center gap-2">
        {swatch("var(--color-amber)")}
        <span>builder de la manche active</span>
      </div>
      <div className="flex items-center gap-2">
        {swatch("var(--color-violet)")}
        <span>juge de la manche active</span>
      </div>
      <div className="flex items-center gap-2">
        <span
          className="inline-block h-0 w-4 border-t-2 border-dashed"
          style={{ borderColor: "var(--color-olive)" }}
        />
        <span>proposer du prochain bloc</span>
      </div>
      <div className="flex items-center gap-2">
        {swatch("var(--color-ink-faint)")}
        <span>sans role / delave = down ou jailed</span>
      </div>
    </div>
  );
}
