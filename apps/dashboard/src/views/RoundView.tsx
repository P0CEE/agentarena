// Vue Manche : « follow the money » — la task, les rendus, les notes et le
// règlement en cartes-reçus reliées par des fils.

import { useEffect, useMemo, useState } from "react";
import { Background, BackgroundVariant, ReactFlow, type Edge, type Node } from "@xyflow/react";
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
    style: { stroke: color, strokeWidth: 1.3, strokeDasharray: "5 5", opacity: 0.5 },
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

  const { nodes, edges } = useMemo(() => {
    if (detail === null) return { nodes: [] as Node[], edges: [] as Edge[] };
    const { task, submissions, scores } = detail;
    const names = network.names;
    const payouts = task.result?.payouts ?? null;

    const flowNodes: Node[] = [];
    const flowEdges: Edge[] = [];

    const buildersY = -((task.builders.length - 1) * 260) / 2;
    const judgesY = -((task.judges.length - 1) * 165) / 2;

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
        position: { x: 420, y: buildersY + index * 260 - 90 },
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
        position: { x: 830, y: judgesY + index * 165 - 60 },
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

    return { nodes: flowNodes, edges: flowEdges };
  }, [detail, network.names, network.height, taskId]);

  if (detail === null) {
    return (
      <div className="grid h-full place-items-center">
        <p className="text-[12px] text-ink-faint">chargement de {taskId}...</p>
      </div>
    );
  }

  return (
    <div className="relative h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        minZoom={0.2}
        maxZoom={1.6}
        nodesConnectable={false}
        elementsSelectable={false}
      >
        <Background variant={BackgroundVariant.Dots} gap={30} size={1.4} color="#ddd8c8" />
      </ReactFlow>
      <PhaseBar task={detail.task} height={network.height} />
    </div>
  );
}

function PhaseBar({ task, height }: { task: TaskDetail["task"]; height: number }) {
  const phases = [
    { label: "rendus", until: task.submit_until },
    { label: "reveals", until: task.reveal_until },
    { label: "notes", until: task.commit_score_until },
    { label: "reveals notes", until: task.reveal_score_until },
  ];
  return (
    <div className="pointer-events-none absolute left-4 top-4 flex items-center gap-2 rounded-[8px] bg-card/90 px-3 py-2 shadow-[0_1px_4px_rgba(30,25,10,0.10)] backdrop-blur">
      <span className="text-[9px] font-semibold uppercase tracking-[0.12em]">
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
            <span className="text-[8px] uppercase tracking-[0.08em] text-ink-faint">
              {phase.label}≤{phase.until}
            </span>
          </span>
        );
      })}
      <span className="text-[9px] tabular-nums text-ink-soft">h={height}</span>
    </div>
  );
}
