import { useMemo, useState } from "react";
import type { Task } from "./api";
import { PixelGlyph, Stamp } from "./components/bits";
import { Composer } from "./components/Composer";
import { useNetwork, useTick } from "./hooks";
import { NetworkView } from "./views/NetworkView";
import { RoundView } from "./views/RoundView";

const DEFAULT_BASE = "http://127.0.0.1:8001";
const fmt = new Intl.NumberFormat("fr-FR");

export default function App() {
  const [base] = useState(
    () => new URLSearchParams(window.location.search).get("node") ?? DEFAULT_BASE,
  );
  const tick = useTick(base);
  const network = useNetwork(base, tick);
  const [view, setView] = useState<"reseau" | "manche">("reseau");
  const [selected, setSelected] = useState<string | null>(null);

  // Les manches, plus recentes d'abord (la fenetre de submit croit avec la hauteur).
  const taskIds = useMemo(
    () =>
      Object.keys(network.tasks).sort(
        (a, b) => network.tasks[b].submit_until - network.tasks[a].submit_until,
      ),
    [network.tasks],
  );
  const activeId = selected ?? taskIds[0] ?? null;
  const activeTask: Task | null = activeId ? (network.tasks[activeId] ?? null) : null;

  return (
    <div className="relative z-10 flex h-screen flex-col">
      <header className="flex items-center gap-4 border-b border-line px-4 py-2.5">
        <div className="flex items-center gap-2">
          <PixelGlyph size={18} />
          <span className="font-display text-[20px] leading-none">AgentArena</span>
        </div>
        <nav className="flex gap-1 rounded-full bg-card p-[3px] shadow-[inset_0_0_0_1px_rgba(30,25,10,0.06)]">
          {(["reseau", "manche"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setView(tab)}
              className={`rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] transition ${
                view === tab ? "bg-ink text-paper" : "text-ink-soft hover:text-ink"
              }`}
            >
              {tab === "reseau" ? "réseau" : "manche"}
            </button>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3 text-[10px] text-ink-soft">
          <span className="tabular-nums">bloc {network.height}</span>
          <span className="flex items-center gap-1.5">
            <span
              className="inline-block size-1.5 rounded-full"
              style={{
                backgroundColor: network.connected
                  ? "var(--color-olive)"
                  : "var(--color-danger)",
              }}
            />
            {network.connected ? `${network.nodes.length} nodes` : "hors ligne"}
          </span>
        </div>
      </header>

      <main className="flex min-h-0 flex-1">
        <section className="min-w-0 flex-1">
          {!network.connected ? (
            <Offline base={base} />
          ) : view === "reseau" ? (
            <NetworkView network={network} activeTask={activeTask} />
          ) : activeId ? (
            <RoundView network={network} taskId={activeId} />
          ) : (
            <div className="grid h-full place-items-center text-center">
              <div>
                <p className="font-display text-[26px] text-ink-soft">Aucune manche</p>
                <p className="mt-1 text-[11px] text-ink-faint">
                  lance-en une depuis le composer →
                </p>
              </div>
            </div>
          )}
        </section>

        <aside className="flex w-[320px] shrink-0 flex-col gap-3 overflow-y-auto border-l border-line bg-paper/60 p-3">
          <Composer
            base={network.nodes[0]?.url}
            disabled={!network.connected}
            onCreated={(taskId) => {
              setSelected(taskId);
              setView("manche");
            }}
          />
          <div>
            <p className="px-1 pb-1.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-ink-faint">
              manches
            </p>
            <div className="space-y-1.5">
              {taskIds.length === 0 && (
                <p className="px-1 text-[10px] text-ink-faint">aucune pour l'instant</p>
              )}
              {taskIds.map((taskId) => {
                const task = network.tasks[taskId];
                const active = taskId === activeId;
                return (
                  <button
                    key={taskId}
                    onClick={() => {
                      setSelected(taskId);
                      setView("manche");
                    }}
                    className={`w-full rounded-[8px] bg-card px-2.5 py-2 text-left shadow-[0_1px_3px_rgba(30,25,10,0.06)] transition hover:shadow-[0_2px_6px_rgba(30,25,10,0.10)] ${
                      active ? "outline outline-1 outline-ink/25" : ""
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-semibold uppercase tracking-[0.06em]">
                        {taskId}
                      </span>
                      <Stamp value={task.state} />
                    </div>
                    <p className="mt-1 truncate text-[9px] text-ink-soft">{task.brief}</p>
                    <p className="mt-1 text-[9px] tabular-nums text-ink-faint">
                      prix {fmt.format(task.prize)}
                    </p>
                  </button>
                );
              })}
            </div>
          </div>
        </aside>
      </main>
    </div>
  );
}

function Offline({ base }: { base: string }) {
  return (
    <div className="grid h-full place-items-center text-center">
      <div>
        <p className="font-display text-[28px] text-ink-soft">Réseau injoignable</p>
        <p className="mt-2 text-[11px] leading-[1.7] text-ink-faint">
          node de référence : <span className="text-ink-soft">{base}</span>
          <br />
          lance <span className="text-ink-soft">arena start</span> puis recharge —
          <br />
          ou pointe un autre node avec <span className="text-ink-soft">?node=http://...</span>
        </p>
      </div>
    </div>
  );
}
