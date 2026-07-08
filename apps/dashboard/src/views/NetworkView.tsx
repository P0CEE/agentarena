// Vue Réseau : le canvas spatial de la référence — un grand cercle fin qui
// porte les agents, des rayons pointillés à connecteurs vers le centre, un
// fond plat. Le rayon du proposer courant est olive.

import { useMemo } from "react";
import { ReactFlow, ViewportPortal, type Node } from "@xyflow/react";
import type { Task } from "../api";
import type { Network } from "../hooks";
import { AgentPill, CenterPlate } from "../components/plates";

const nodeTypes = { center: CenterPlate, agent: AgentPill };

const RADIUS = 430;
const PILL = { w: 116, h: 30 };
const CENTER = { w: 176, h: 92 };

type Spoke = { key: string; angle: number; proposer: boolean };

export function NetworkView({
  network,
  activeTask,
}: {
  network: Network;
  activeTask: Task | null;
}) {
  const count = Math.max(network.nodes.length, 1);

  const { nodes, spokes } = useMemo(() => {
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
    const rays: Spoke[] = [];
    network.nodes.forEach((entry, index) => {
      const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
      const address = entry.status?.address ?? "";
      const info = network.agents[address];
      const proposer = entry.status?.proposer_next ?? false;
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
          proposer,
          role: activeTask
            ? activeTask.builders.includes(address)
              ? ("builder" as const)
              : activeTask.judges.includes(address)
                ? ("juge" as const)
                : null
            : null,
        },
      });
      rays.push({ key: entry.name, angle, proposer });
    });
    return { nodes: flowNodes, spokes: rays };
  }, [network, activeTask, count]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={[]}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.14 }}
      minZoom={0.25}
      maxZoom={1.6}
      nodesConnectable={false}
      elementsSelectable={false}
    >
      <ViewportPortal>
        <Rings spokes={spokes} />
      </ViewportPortal>
    </ReactFlow>
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
      <circle
        cx={0}
        cy={0}
        r={RADIUS}
        fill="none"
        stroke="rgba(42, 41, 36, 0.10)"
        strokeWidth={1.5}
      />
      {spokes.map((spoke) => {
        const inner = edgeDistance(CENTER.w / 2, CENTER.h / 2, spoke.angle) + 12;
        const outer =
          RADIUS - edgeDistance(PILL.w / 2, PILL.h / 2, spoke.angle) - 12;
        const cos = Math.cos(spoke.angle);
        const sin = Math.sin(spoke.angle);
        const stroke = spoke.proposer ? "var(--color-olive)" : "rgba(42, 41, 36, 0.16)";
        return (
          <g key={spoke.key} opacity={spoke.proposer ? 0.85 : 1}>
            <line
              x1={cos * inner}
              y1={sin * inner}
              x2={cos * outer}
              y2={sin * outer}
              stroke={stroke}
              strokeWidth={1.4}
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
                stroke="rgba(42, 41, 36, 0.22)"
                strokeWidth={0.9}
              />
            ))}
          </g>
        );
      })}
    </svg>
  );
}
