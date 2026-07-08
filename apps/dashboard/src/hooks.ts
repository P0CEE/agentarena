import { useEffect, useMemo, useState } from "react";
import {
  type AgentInfo,
  type Status,
  type Task,
  getAgents,
  getStatus,
  getTasks,
  portOf,
} from "./api";

// SSE du node de reference + intervalle de secours : chaque signal
// incremente un tick qui declenche les refetchs.
export function useTick(base: string): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const bump = () => setTick((t) => t + 1);
    const source = new EventSource(`${base}/events`);
    source.addEventListener("block", bump);
    source.addEventListener("task", bump);
    const fallback = setInterval(bump, 2500);
    return () => {
      source.close();
      clearInterval(fallback);
    };
  }, [base]);
  return tick;
}

export type NodeEntry = { url: string; name: string; status: Status | null };

export type Network = {
  connected: boolean;
  nodes: NodeEntry[];
  tasks: Record<string, Task>;
  agents: Record<string, AgentInfo>;
  height: number;
  names: Record<string, string>;
};

export function useNetwork(base: string, tick: number): Network {
  const [connected, setConnected] = useState(false);
  const [nodes, setNodes] = useState<NodeEntry[]>([]);
  const [tasks, setTasks] = useState<Record<string, Task>>({});
  const [agents, setAgents] = useState<Record<string, AgentInfo>>({});

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const reference = await getStatus(base);
        const urls = [base, ...reference.peers].sort((a, b) => portOf(a) - portOf(b));
        const [statuses, taskMap, agentMap] = await Promise.all([
          Promise.all(urls.map((url) => getStatus(url).catch(() => null))),
          getTasks(base),
          getAgents(base),
        ]);
        if (cancelled) return;
        setNodes(
          urls.map((url, index) => ({
            url,
            name: `node-${index}`,
            status: statuses[index],
          })),
        );
        setTasks(taskMap);
        setAgents(agentMap);
        setConnected(true);
      } catch {
        if (!cancelled) setConnected(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [base, tick]);

  const height = Math.max(0, ...nodes.map((node) => node.status?.height ?? 0));
  const names = useMemo(() => {
    const map: Record<string, string> = {};
    for (const node of nodes) {
      if (node.status) map[node.status.address] = node.name;
    }
    return map;
  }, [nodes]);

  return { connected, nodes, tasks, agents, height, names };
}
