// Les cartes-reçus de la vue Manche (style « follow the money »).
// Chaque reçu est un node React Flow ; les fils sont des edges.

import type { NodeProps } from "@xyflow/react";
import { Handle, Position } from "@xyflow/react";
import type { ScoreRecord, Submission, Task } from "../api";
import { DashedRule, RoleChip, Stamp } from "./bits";

const fmt = new Intl.NumberFormat("fr-FR");

function hiddenHandles() {
  const style = { opacity: 0, width: 1, height: 1, border: 0, pointerEvents: "none" as const };
  return (
    <>
      <Handle type="target" position={Position.Left} style={style} />
      <Handle type="source" position={Position.Right} style={style} />
    </>
  );
}

function Shell({
  tilt,
  width = 220,
  children,
}: {
  tilt: number;
  width?: number;
  children: React.ReactNode;
}) {
  return (
    <div
      className="receipt-drop relative"
      style={{ width, ["--tilt" as string]: `${tilt}deg`, transform: `rotate(${tilt}deg)` }}
    >
      <div className="receipt-edge relative overflow-hidden rounded-t-[4px] bg-card px-3.5 pt-3.5 pb-5 shadow-[0_1px_2px_rgba(30,25,10,0.06),0_6px_18px_rgba(30,25,10,0.10)]">
        <div className="receipt-texture pointer-events-none absolute inset-0" />
        <div className="relative">{children}</div>
      </div>
    </div>
  );
}

function Row({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className={`text-[9px] leading-[1.5] ${strong ? "text-ink" : "text-ink-soft"}`}>
        {label}
      </span>
      <span
        className={`shrink-0 text-[9px] tabular-nums ${strong ? "font-semibold text-ink" : "text-ink-soft"}`}
      >
        {value}
      </span>
    </div>
  );
}

// --- reçu de la task (le brief du sponsor) ---

export type TaskReceiptData = { taskId: string; task: Task; height: number };

export function TaskReceipt({ data }: NodeProps) {
  const { taskId, task, height } = data as TaskReceiptData;
  const reserve = Math.floor((task.prize * 20) / 100);
  return (
    <Shell tilt={-1.5} width={240}>
      {hiddenHandles()}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]">{taskId}</span>
        <RoleChip role="sponsor" />
      </div>
      <DashedRule />
      <p className="text-[10px] leading-[1.5] text-ink-soft" style={{ display: "-webkit-box", WebkitLineClamp: 4, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {task.brief}
      </p>
      <DashedRule />
      <Row label="pot builders (80%)" value={fmt.format(task.prize - reserve)} />
      <Row label="reserve juges (20%)" value={fmt.format(reserve)} />
      <div className="mt-2 flex items-end justify-between">
        <span className="text-[9px] uppercase tracking-[0.1em] text-ink-faint">prix</span>
        <span className="text-[16px] font-semibold leading-none tabular-nums">
          {fmt.format(task.prize)}
        </span>
      </div>
      <DashedRule />
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-ink-faint">h={height}</span>
        <Stamp value={task.state} />
      </div>
    </Shell>
  );
}

// --- reçu d'un rendu de builder ---

export type SubmissionReceiptData = {
  name: string;
  submission: Submission | null;
  payout: number | null;
  tilt: number;
};

export function SubmissionReceipt({ data }: NodeProps) {
  const { name, submission, payout, tilt } = data as SubmissionReceiptData;
  return (
    <Shell tilt={tilt}>
      {hiddenHandles()}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]">{name}</span>
        <RoleChip role="builder" />
      </div>
      <DashedRule />
      {submission === null ? (
        <p className="text-[10px] italic text-ink-faint">aucun rendu (no-show)</p>
      ) : submission.status === "COMMITTED" ? (
        <div className="space-y-1">
          <p className="text-[10px] text-ink-faint">contenu scelle (commit-reveal)</p>
          <p className="select-none text-[10px] tracking-[0.2em] text-ink-faint">
            ▓▓▓▓▓▓▓▓▓▓▓▓
          </p>
        </div>
      ) : (
        <p
          className="whitespace-pre-wrap text-[9px] leading-[1.5] text-ink-soft"
          style={{ display: "-webkit-box", WebkitLineClamp: 6, WebkitBoxOrient: "vertical", overflow: "hidden" }}
        >
          {submission.content}
        </p>
      )}
      <DashedRule />
      <div className="flex items-center justify-between">
        <span className="text-[9px] text-ink-faint">
          {submission ? `commit h=${submission.height}` : "-"}
        </span>
        {submission && <Stamp value={submission.status} />}
      </div>
      {payout !== null && (
        <>
          <DashedRule />
          <div className="flex items-end justify-between">
            <span className="text-[9px] uppercase tracking-[0.1em] text-ink-faint">gain</span>
            <span className="text-[14px] font-semibold tabular-nums text-amber">
              {fmt.format(payout)}
            </span>
          </div>
        </>
      )}
    </Shell>
  );
}

// --- reçu compact d'un juge ---

export type JudgeReceiptData = {
  name: string;
  record: ScoreRecord | null;
  builders: string[];
  payout: number | null;
  tilt: number;
};

export function JudgeReceipt({ data }: NodeProps) {
  const { name, record, builders, payout, tilt } = data as JudgeReceiptData;
  const scores = record?.status === "REVEAL_OK" ? record.scores : null;
  const total = scores ? Object.values(scores).reduce((a, b) => a + b, 0) : 0;
  return (
    <Shell tilt={tilt} width={190}>
      {hiddenHandles()}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.08em]">{name}</span>
        <RoleChip role="juge" />
      </div>
      <DashedRule />
      {scores === null ? (
        <p className="text-[9px] text-ink-faint">
          {record === null ? "pas encore de notes" : "notes scellees ▓▓▓▓"}
        </p>
      ) : (
        <div className="space-y-1">
          {builders.map((builder) => {
            const value = scores[builder] ?? 0;
            return (
              <div key={builder} className="flex items-center gap-1.5">
                <span className="w-3 text-[8px] text-ink-faint">
                  {builder.slice(0, 2)}
                </span>
                <div className="h-[5px] flex-1 overflow-hidden rounded-full bg-line">
                  <div
                    className="h-full rounded-full bg-violet"
                    style={{ width: `${total ? (value / total) * 100 : 0}%` }}
                  />
                </div>
                <span className="w-7 text-right text-[8px] tabular-nums text-ink-soft">
                  {total ? Math.round((value / total) * 100) : 0}%
                </span>
              </div>
            );
          })}
        </div>
      )}
      {payout !== null && (
        <>
          <DashedRule />
          <div className="flex items-end justify-between">
            <span className="text-[8px] uppercase tracking-[0.1em] text-ink-faint">dividende</span>
            <span className="text-[12px] font-semibold tabular-nums text-violet">
              {fmt.format(payout)}
            </span>
          </div>
        </>
      )}
    </Shell>
  );
}

// --- reçu de règlement (Yuma) ---

export type SettlementReceiptData = {
  task: Task;
  names: Record<string, string>;
};

export function SettlementReceipt({ data }: NodeProps) {
  const { task, names } = data as SettlementReceiptData;
  const result = task.result;
  return (
    <Shell tilt={1.5} width={240}>
      {hiddenHandles()}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em]">
          reglement yuma
        </span>
        <Stamp value={task.state} />
      </div>
      <DashedRule />
      {result === null ? (
        <p className="text-[10px] text-ink-faint">
          en attente de la cloture des fenetres...
        </p>
      ) : result.aborted ? (
        <p className="text-[10px] text-ink-soft">
          manche annulee ({result.aborted}) — prix rembourse au sponsor
        </p>
      ) : (
        <>
          <p className="mb-1 text-[9px] uppercase tracking-[0.1em] text-ink-faint">builders</p>
          {(result.builders ?? []).map((addr) => (
            <Row
              key={addr}
              label={names[addr] ?? addr.slice(0, 8)}
              value={fmt.format(result.payouts?.builders[addr] ?? 0)}
              strong
            />
          ))}
          <DashedRule />
          <p className="mb-1 text-[9px] uppercase tracking-[0.1em] text-ink-faint">juges</p>
          {(result.judges ?? []).map((addr) => (
            <Row
              key={addr}
              label={names[addr] ?? addr.slice(0, 8)}
              value={fmt.format(result.payouts?.judges[addr] ?? 0)}
            />
          ))}
          <DashedRule />
          <div className="flex items-end justify-between">
            <span className="text-[9px] uppercase tracking-[0.1em] text-ink-faint">total</span>
            <span className="text-[16px] font-semibold tabular-nums">
              {fmt.format(task.prize)}
            </span>
          </div>
        </>
      )}
    </Shell>
  );
}
