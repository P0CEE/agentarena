// Vue Réseau : le canvas spatial — les agents en cercle autour du centre-chaîne.

import { useMemo } from "react";
import { Background, BackgroundVariant, ReactFlow, type Edge, type Node } from "@xyflow/react";
import type { Task } from "../api";
import type { Network } from "../hooks";
import { AgentPlate, ChainPlate } from "../components/plates";

const nodeTypes = { chain: ChainPlate, agent: AgentPlate };

const RADIUS = 420;

export function NetworkView({
  network,
  activeTask,
}: {
  network: Network;
  activeTask: Task | null;
}) {
  const { nodes, edges } = useMemo(() => {
    const agents = network.nodes;
    const count = Math.max(agents.length, 1);
    const flowNodes: Node[] = [
      {
        id: "chain",
        type: "chain",
        position: { x: -95, y: -60 },
        draggable: false,
        data: {
          height: network.height,
          round: agents[0]?.status?.round ?? 0,
          blockTick: network.height,
        },
      },
    ];
    const flowEdges: Edge[] = [];
    agents.forEach((entry, index) => {
      const angle = -Math.PI / 2 + (index * 2 * Math.PI) / count;
      const address = entry.status?.address ?? "";
      const info = network.agents[address];
      const role = activeTask
        ? activeTask.builders.includes(address)
          ? ("builder" as const)
          : activeTask.judges.includes(address)
            ? ("juge" as const)
            : null
        : null;
      const proposer = entry.status?.proposer_next ?? false;
      flowNodes.push({
        id: entry.name,
        type: "agent",
        position: {
          x: Math.cos(angle) * RADIUS - 84,
          y: Math.sin(angle) * RADIUS - 40,
        },
        data: {
          name: entry.name,
          address,
          height: entry.status?.height ?? null,
          networkHeight: network.height,
          stake: info ? info.free + info.locked : 0,
          jailed: info ? info.jailed_until > network.height : false,
          proposer,
          role,
        },
      });
      flowEdges.push({
        id: `link-${entry.name}`,
        source: "chain",
        target: entry.name,
        type: "straight",
        animated: proposer,
        style: {
          stroke: proposer ? "var(--color-olive)" : "var(--color-ink-faint)",
          strokeWidth: proposer ? 1.6 : 1,
          strokeDasharray: "7 6",
          opacity: proposer ? 0.9 : 0.35,
        },
      });
    });
    return { nodes: flowNodes, edges: flowEdges };
  }, [network, activeTask]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.15 }}
      minZoom={0.25}
      maxZoom={1.6}
      nodesConnectable={false}
      elementsSelectable={false}
    >
      <Background variant={BackgroundVariant.Dots} gap={30} size={1.4} color="#ddd8c8" />
    </ReactFlow>
  );
}
