import { useMemo, useState } from "react";
import type { Task } from "./api";
import { PixelGlyph, Stamp } from "./components/bits";
import { Composer } from "./components/Composer";
import { TransferPopup, type TransferPrefill } from "./components/TransferPopup";
import { useNetwork, useTick } from "./hooks";
import { BlocksView } from "./views/BlocksView";
import { NetworkView } from "./views/NetworkView";
import { RoundView } from "./views/RoundView";

const DEFAULT_BASE = "http://127.0.0.1:8001";
const fmt = new Intl.NumberFormat("fr-FR");

const CHIP_SHADOW = "shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_1px_2px_rgba(0,0,0,0.05)]";

type View = "reseau" | "manche" | "blocs";

const VIEW_LABELS: Record<View, string> = {
  reseau: "Réseau",
  manche: "Manche",
  blocs: "Blocs",
};

export default function App() {
  const [base] = useState(
    () => new URLSearchParams(window.location.search).get("node") ?? DEFAULT_BASE,
  );
  const tick = useTick(base);
  const network = useNetwork(base, tick);
  const [view, setView] = useState<View>("reseau");
  const [selected, setSelected] = useState<string | null>(null);
  // "envoyer un transfer a ce node" : ouvre le popup pre-rempli depuis la fiche
  const [prefill, setPrefill] = useState<TransferPrefill>(null);
  const [transferOpen, setTransferOpen] = useState(false);

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
    <div className="relative z-10 flex h-screen">
      {/* Le canvas occupe toute la hauteur ; le header flotte par-dessus. */}
      <section className="relative min-w-0 flex-1">
        <header className="pointer-events-none absolute inset-x-0 top-0 z-20 flex items-center gap-4 px-4 py-3">
          <div className="pointer-events-auto flex items-center gap-2">
            <PixelGlyph size={18} />
            <span className="font-display text-[20px] leading-none">AgentArena</span>
          </div>
          <div className="pointer-events-auto">
            <ViewMenu view={view} onChange={setView} />
          </div>
          <div className="pointer-events-auto ml-auto flex items-center gap-2 text-[12px] text-ink-soft">
            <TransferPopup
              base={network.nodes[0]?.url}
              disabled={!network.connected}
              height={network.height}
              prefill={prefill}
              open={transferOpen}
              onToggle={() => setTransferOpen((value) => !value)}
              onClose={() => setTransferOpen(false)}
            />
            <span className={`rounded-[8px] bg-card px-2.5 py-1.5 tabular-nums ${CHIP_SHADOW}`}>
              bloc {network.height}
            </span>
            <span
              className={`flex items-center gap-1.5 rounded-[8px] bg-card px-2.5 py-1.5 ${CHIP_SHADOW}`}
            >
              <span
                className="inline-block size-2 rounded-full"
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

        {!network.connected ? (
          <Offline base={base} />
        ) : view === "reseau" ? (
          <NetworkView
            network={network}
            activeTask={activeTask}
            onTransfer={(address) => {
              setPrefill({ address, at: Date.now() });
              setTransferOpen(true);
            }}
          />
        ) : view === "blocs" ? (
          <BlocksView network={network} />
        ) : activeId ? (
          <RoundView network={network} taskId={activeId} />
        ) : (
          <div className="grid h-full place-items-center text-center">
            <div>
              <p className="font-display text-[26px] text-ink-soft">Aucune manche</p>
              <p className="mt-1 text-[13px] text-ink-faint">
                lance-en une depuis le composer →
              </p>
            </div>
          </div>
        )}
      </section>

      {/* Panneau flottant : carte interne pour la liste,
          composer epingle en bas en overlay. */}
      <aside className="relative my-2 mr-2 flex w-[380px] shrink-0 flex-col overflow-hidden rounded-[12px] bg-white/70 shadow-[0_0_0_1px_rgba(0,0,0,0.05),0_12px_32px_rgba(0,0,0,0.10)] backdrop-blur-xl">
        <section className="relative m-1.5 flex min-h-0 flex-1 flex-col overflow-hidden rounded-[10px] bg-card shadow-[0_0_0_1px_rgba(0,0,0,0.05)]">
          <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto p-3 pb-[200px]">
            <div className="flex items-center justify-between px-1 pb-2.5">
              <h2 className="text-[13px] font-medium">Manches</h2>
              <span className="rounded-full bg-ink/5 px-2 py-0.5 text-[11px] tabular-nums text-ink-soft">
                {taskIds.length}
              </span>
            </div>
            {taskIds.length === 0 ? (
              <p className="px-1 text-[12px] text-ink-faint">aucune manche pour l'instant</p>
            ) : (
              <div className="space-y-2">
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
                      className={`block w-full rounded-[10px] border bg-card p-3 text-left transition ${
                        active
                          ? "border-ink/25 shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
                          : "border-line hover:border-ink/15 hover:shadow-[0_1px_3px_rgba(0,0,0,0.05)]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[12px] font-semibold uppercase tracking-[0.06em]">
                          {taskId}
                        </span>
                        <Stamp value={task.state} />
                      </div>
                      <p className="mt-1 truncate text-[11px] text-ink-soft">{task.brief}</p>
                      <p className="mt-1 text-[11px] tabular-nums text-ink-faint">
                        prix {fmt.format(task.prize)}
                      </p>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>
        <div className="absolute inset-x-0 bottom-2 z-20 px-2">
          <Composer
            base={network.nodes[0]?.url}
            disabled={!network.connected}
            onCreated={(taskId) => {
              setSelected(taskId);
              setView("manche");
            }}
          />
        </div>
      </aside>
    </div>
  );
}

// Menu de vues : un seul bouton compact, la liste se deroule dessous.
function ViewMenu({ view, onChange }: { view: View; onChange: (view: View) => void }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        className={`flex h-[30px] items-center gap-1.5 rounded-[8px] bg-card px-2.5 text-[13px] font-medium text-ink ${CHIP_SHADOW}`}
      >
        {VIEW_LABELS[view]}
        <svg
          viewBox="0 0 256 256"
          className={`h-2.5 w-2.5 text-ink-faint transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z" />
        </svg>
      </button>
      {open && (
        <>
          <div className="fixed inset-0" onClick={() => setOpen(false)} />
          <div
            role="menu"
            className="absolute left-0 top-full z-10 mt-1.5 w-[150px] rounded-[8px] border border-line bg-card p-1 shadow-[0_2px_6px_rgba(0,0,0,0.08),0_12px_28px_rgba(0,0,0,0.14)]"
          >
            {(Object.keys(VIEW_LABELS) as View[]).map((item) => (
              <button
                key={item}
                role="menuitem"
                onClick={() => {
                  onChange(item);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between rounded-[5px] px-2 py-1.5 text-[12px] transition ${
                  view === item
                    ? "bg-ink/5 font-medium text-ink"
                    : "text-ink-soft hover:bg-ink/[0.03] hover:text-ink"
                }`}
              >
                {VIEW_LABELS[item]}
                {view === item && (
                  <span
                    className="size-1.5 rounded-full"
                    style={{ backgroundColor: "var(--color-olive)" }}
                  />
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Offline({ base }: { base: string }) {
  return (
    <div className="grid h-full place-items-center text-center">
      <div>
        <p className="font-display text-[28px] text-ink-soft">Réseau injoignable</p>
        <p className="mt-2 text-[13px] leading-[1.7] text-ink-faint">
          node de référence : <span className="text-ink-soft">{base}</span>
          <br />
          lance <span className="text-ink-soft">arena</span> puis recharge —
          <br />
          ou pointe un autre node avec <span className="text-ink-soft">?node=http://...</span>
        </p>
      </div>
    </div>
  );
}
