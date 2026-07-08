// Types et fetchers vers l'API des nodes (CORS ouvert cote node).

export type Status = {
  address: string;
  height: number;
  round: number;
  mempool: number;
  peers: string[];
  validators: number;
  jailed_until: number;
  proposer_next: boolean;
};

export type TaskResult = {
  aborted?: string;
  builders?: string[];
  judges?: string[];
  consensus?: number[];
  incentive?: number[];
  dividends?: number[];
  payouts?: { builders: Record<string, number>; judges: Record<string, number> };
};

export type Task = {
  sponsor: string;
  prize: number;
  brief: string;
  state: "OPEN" | "SCORING" | "SETTLED";
  builders: string[];
  judges: string[];
  submit_until: number;
  reveal_until: number;
  commit_score_until: number;
  reveal_score_until: number;
  slashed: string[];
  result: TaskResult | null;
};

export type Submission = {
  commit: string;
  content: string | null;
  height: number;
  status: "COMMITTED" | "REVEAL_OK" | "MISMATCH";
};

export type ScoreRecord = {
  commit: string;
  scores: Record<string, number> | null;
  status: "COMMITTED" | "REVEAL_OK" | "MISMATCH";
};

export type TaskDetail = {
  task: Task;
  submissions: Record<string, Submission>;
  scores: Record<string, ScoreRecord>;
};

export type AgentInfo = {
  jailed_until: number;
  offenses: number;
  last_offense: number;
  free: number;
  locked: number;
};

async function get<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url}: ${response.status}`);
  return response.json();
}

export const getStatus = (base: string) => get<Status>(`${base}/status`);

export const getTasks = (base: string) =>
  get<{ tasks: Record<string, Task> }>(`${base}/tasks`).then((data) => data.tasks);

export const getTaskDetail = (base: string, taskId: string) =>
  get<TaskDetail>(`${base}/tasks/${taskId}`);

export const getAgents = (base: string) =>
  get<{ agents: Record<string, AgentInfo> }>(`${base}/agents`).then((data) => data.agents);

export async function createTask(
  base: string,
  brief: string,
  prize: number,
): Promise<string> {
  const response = await fetch(`${base}/sponsor/tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ brief, prize }),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail ?? "tx rejetee");
  return body.task;
}

export function portOf(url: string): number {
  return Number(url.match(/:(\d+)$/)?.[1] ?? 0);
}
