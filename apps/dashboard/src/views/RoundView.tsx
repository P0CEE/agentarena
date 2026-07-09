// Vue Manche : « follow the money » — la task, les rendus, les notes et le
// règlement en cartes-reçus reliées par des fils.

import { useEffect, useState } from "react";
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  useEdgesState,
  useNodesState,
  useReactFlow,
  type Edge,
  type Node,
} from "@xyflow/react";
import { getTaskDetail, type TaskDetail } from "../api";
import type { Network } from "../hooks";
import {
  JudgeReceipt,
  SettlementReceipt,
  SubmissionReceipt,
  TaskReceipt,
} from "../components/receipts";

const nodeTypes = {
  task: TaskReceipt,
  submission: SubmissionReceipt,
  judge: JudgeReceipt,
  settlement: SettlementReceipt,
};

const TILTS = [-2.5, 1.8, -1.2, 2.2, -1.8, 1.2, -2.2];

function thread(id: string, source: string, target: string, color: string): Edge {
  return {
    id,
    source,
    target,
    type: "default",
    style: { stroke: color, strokeWidth: 1.4, strokeDasharray: "5 5", opacity: 0.8 },
  };
}

export function RoundView({ network, taskId }: { network: Network; taskId: string }) {
  const base = network.nodes[0]?.url;
  const [detail, setDetail] = useState<TaskDetail | null>(null);

  useEffect(() => {
    if (!base) return;
    let cancelled = false;
    getTaskDetail(base, taskId)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [base, taskId, network.height]);

  // Pattern controle de React Flow v12 : setNodes + onNodesChange, sinon les
  // mesures des nodes se perdent a chaque refetch et ils restent invisibles.
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  useEffect(() => {
    if (detail === null) return;
    const { task, submissions, scores } = detail;
    const names = network.names;
    const payouts = task.result?.payouts ?? null;

    const flowNodes: Node[] = [];
    const flowEdges: Edge[] = [];

    const buildersY = -((task.builders.length - 1) * 280) / 2;
    const judgesY = -((task.judges.length - 1) * 180) / 2;

    flowNodes.push({
      id: "task",
      type: "task",
      position: { x: 0, y: -130 },
      data: { taskId, task, height: network.height },
    });

    task.builders.forEach((address, index) => {
      const id = `builder-${address}`;
      flowNodes.push({
        id,
        type: "submission",
        position: { x: 420, y: buildersY + index * 280 - 90 },
        data: {
          name: names[address] ?? address.slice(0, 8),
          submission: submissions[address] ?? null,
          payout: payouts?.builders[address] ?? null,
          tilt: TILTS[index % TILTS.length],
        },
      });
      flowEdges.push(thread(`t-${id}`, "task", id, "var(--color-amber)"));
      flowEdges.push(thread(`s-${id}`, id, "settlement", "var(--color-ink-faint)"));
    });

    task.judges.forEach((address, index) => {
      const id = `judge-${address}`;
      flowNodes.push({
        id,
        type: "judge",
        position: { x: 830, y: judgesY + index * 180 - 60 },
        data: {
          name: names[address] ?? address.slice(0, 8),
          record: scores[address] ?? null,
          builders: task.builders,
          payout: payouts?.judges[address] ?? null,
          tilt: TILTS[(index + 3) % TILTS.length],
        },
      });
      flowEdges.push(thread(`j-${id}`, id, "settlement", "var(--color-violet)"));
    });

    flowNodes.push({
      id: "settlement",
      type: "settlement",
      position: { x: 1220, y: -140 },
      data: { task, names },
    });

    // Reporte les mesures des nodes existants : sans `measured`, React Flow v12
    // repasse chaque node en visibility:hidden a chaque rebuild (canvas vide).
    setNodes((current) => {
      const measured = new Map(current.map((node) => [node.id, node.measured]));
      return flowNodes.map((node) => ({ ...node, measured: measured.get(node.id) }));
    });
    setEdges(flowEdges);
  }, [detail, network.names, network.height, taskId, setNodes, setEdges]);

  if (detail === null) {
    return (
      <div className="grid h-full place-items-center">
        <p className="text-[13px] text-ink-faint">chargement de {taskId}...</p>
      </div>
    );
  }

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        onNodesChange={onNodesChange}
        edges={edges}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.2}
        maxZoom={1.6}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={24} size={2.2} color="#dcdcdc" />
        <AutoFit signature={`${taskId}|${detail.task.state}`} />
      </ReactFlow>
      <PhaseBar task={detail.task} height={network.height} />
    </div>
  );
}

// Les recus grandissent a chaque phase (reveals, notes, reglement) et sortaient
// du cadre : on re-cadre a chaque changement d'etat de la manche.
function AutoFit({ signature }: { signature: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    const timer = setTimeout(
      () => fitView({ padding: 0.12, duration: 400 }),
      80, // laisse React Flow mesurer les recus re-rendus
    );
    return () => clearTimeout(timer);
  }, [signature, fitView]);
  return null;
}

function PhaseBar({ task, height }: { task: TaskDetail["task"]; height: number }) {
  const phases = [
    { label: "rendus", until: task.submit_until },
    { label: "reveals", until: task.reveal_until },
    { label: "notes", until: task.commit_score_until },
    { label: "reveals notes", until: task.reveal_score_until },
  ];
  return (
    <div
      className="pointer-events-none absolute bottom-4 left-4 flex items-center gap-2 rounded-[8px] px-3 py-2 shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_1px_4px_rgba(0,0,0,0.08)]"
      style={{ backgroundColor: "var(--color-card)" }}
    >
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em]">
        {task.state}
      </span>
      {phases.map((phase, index) => {
        const done = height >= phase.until;
        const current = index === phases.findIndex((p) => height < p.until);
        const active = current && task.state !== "SETTLED";
        return (
          <span key={phase.label} className="flex items-center gap-1">
            <span
              className="h-[3px] w-6 rounded-full"
              style={{
                backgroundColor: done
                  ? "var(--color-olive)"
                  : active
                    ? "var(--color-amber)"
                    : "var(--color-line)",
              }}
            />
            <span className="text-[10px] uppercase tracking-[0.08em] text-ink-faint">
              {phase.label}≤{phase.until}
            </span>
          </span>
        );
      })}
      <span className="text-[11px] tabular-nums text-ink-soft">h={height}</span>
    </div>
  );
}
