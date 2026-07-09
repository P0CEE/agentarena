// Vue Blocs : liste simple, du plus récent au plus ancien. Seuls les blocs
// portant des transactions apparaissent (le consensus cadence des blocs vides
// toutes les ~2 s, ils sont masqués). Le chaînage se lit dans le bloc
// déplié : hash / prev.

import { useEffect, useState } from "react";
import { getBlocks, type BlockEntry, type Tx } from "../api";
import type { Network } from "../hooks";
import { PixelIcon } from "../components/bits";

const WINDOW = 120; // /blocks ne pagine que par "from" : fenêtre des N derniers
const fmt = new Intl.NumberFormat("fr-FR");
const timeFmt = new Intl.DateTimeFormat("fr-FR", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

// Garde sur undefined : un node pas encore redemarre ne sert pas "hash".
const short = (hex: string | undefined, length = 12) =>
  !hex ? "—" : hex.length > length ? `${hex.slice(0, length)}…` : hex;

export function BlocksView({ network }: { network: Network }) {
  const base = network.nodes[0]?.url;
  const [entries, setEntries] = useState<BlockEntry[]>([]);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  useEffect(() => {
    if (!base) return;
    let cancelled = false;
    getBlocks(base, Math.max(0, network.height - WINDOW + 1))
      .then((blocks) => {
        if (!cancelled) setEntries(blocks);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [base, network.height]);

  const newestFirst = [...entries].reverse();
  const tip = newestFirst[0]?.block.header.height ?? 0;
  const visible = newestFirst.filter(
    (entry) => entry.block.txs.length > 0 || entry.block.header.height === 0,
  );

  const toggle = (height: number) =>
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(height)) next.delete(height);
      else next.add(height);
      return next;
    });

  return (
    <div className="no-scrollbar h-full overflow-y-auto px-6 pb-12 pt-16">
      <div className="flex items-baseline gap-4 px-1 pb-5">
        <h2 className="font-display text-[26px]">La chaîne</h2>
        <span className="text-[11px] tabular-nums text-ink-faint">
          bloc {tip} · seuls les blocs avec transactions s'affichent
        </span>
      </div>

      {visible.length === 0 ? (
        <p className="px-1 text-[12px] text-ink-faint">
          {entries.length === 0
            ? "en attente de blocs…"
            : `aucune transaction dans les ${entries.length} derniers blocs — envoie un transfer ou lance une manche, puis reviens`}
        </p>
      ) : (
        <div className="space-y-2">
          {visible.map((entry) => (
            <BlockCard
              key={entry.block.header.height}
              entry={entry}
              names={network.names}
              open={expanded.has(entry.block.header.height)}
              onToggle={() => toggle(entry.block.header.height)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function BlockCard({
  entry,
  names,
  open,
  onToggle,
}: {
  entry: BlockEntry;
  names: Record<string, string>;
  open: boolean;
  onToggle: () => void;
}) {
  const { header, txs } = entry.block;
  const genesis = header.height === 0;
  const voters = Object.keys(entry.qc).length;

  return (
    <article
      className={`rounded-[10px] border bg-card px-4 py-3 transition ${
        open ? "border-ink/15 shadow-[0_1px_3px_rgba(0,0,0,0.05)]" : "border-line"
      }`}
    >
      {/* Seul le header est cliquable : le contenu deplie ne referme pas la carte. */}
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 text-left"
        aria-expanded={open}
      >
        <span className="font-display text-[22px] leading-none tabular-nums">
          #{header.height}
        </span>
        {genesis ? (
          <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-soft">
            genesis
          </span>
        ) : (
          <span className="flex items-center gap-1.5 text-[12px] text-ink-soft">
            <PixelIcon address={header.proposer} role={null} size={15} />
            {names[header.proposer] ?? short(header.proposer, 8)}
          </span>
        )}
        <span className="ml-auto text-[11px] tabular-nums text-ink-faint">
          {header.timestamp > 0 ? timeFmt.format(new Date(header.timestamp)) : "—"}
        </span>
        {!genesis && (
          <span
            className="rounded-full px-2 py-0.5 text-[11px] font-semibold tabular-nums text-white"
            style={{ backgroundColor: "var(--color-amber)" }}
          >
            {txs.length} tx
          </span>
        )}
        <svg
          viewBox="0 0 16 16"
          className={`size-3.5 shrink-0 text-ink-faint transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          aria-hidden="true"
        >
          <path d="M4 6l4 4 4-4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="mt-3 space-y-2 border-t border-dashed border-line pt-3">
          {/* le chainage : le prev de ce bloc est le hash du bloc precedent */}
          <div className="grid gap-1 rounded-[8px] bg-ink/[0.03] px-3 py-2 font-mono text-[11px] text-ink-soft">
            <span title={entry.hash}>
              <span className="text-ink-faint">hash&nbsp;&nbsp;</span>
              {short(entry.hash, 34)}
            </span>
            {!genesis && (
              <span title={header.prev_hash}>
                <span className="text-ink-faint">prev&nbsp;&nbsp;</span>
                {short(header.prev_hash, 34)}
                <span className="text-ink-faint"> = hash du bloc #{header.height - 1}</span>
              </span>
            )}
          </div>
          {genesis ? (
            <p className="text-[12px] text-ink-faint">bloc d'origine — aucune transaction</p>
          ) : (
            <>
              {txs.map((tx, index) => (
                <TxRow
                  key={tx.signature}
                  tx={tx}
                  txid={entry.txids?.[index]}
                  names={names}
                />
              ))}
              <p className="px-1 text-[11px] tabular-nums text-ink-faint">
                round {header.round} · quorum de {voters} votes
              </p>
            </>
          )}
        </div>
      )}
    </article>
  );
}

function TxRow({
  tx,
  txid,
  names,
}: {
  tx: Tx;
  txid: string | undefined;
  names: Record<string, string>;
}) {
  const { payload } = tx;
  const target = payload.to ?? payload.task ?? null;
  return (
    <div className="rounded-[8px] border border-line/70 bg-paper/70 px-3 py-2.5 text-[12px]">
      <div className="flex items-center gap-2.5">
        <span
          className="inline-block -rotate-3 border-[1.5px] px-1.5 py-px text-[10px] font-semibold uppercase tracking-[0.12em]"
          style={{ color: "var(--color-ink-soft)", borderColor: "var(--color-ink-faint)" }}
        >
          {payload.type}
        </span>
        <span className="flex items-center gap-1.5 text-ink-soft">
          <PixelIcon address={tx.sender} role={null} size={15} />
          {names[tx.sender] ?? short(tx.sender, 8)}
          {target !== null && (
            <>
              <svg
                viewBox="0 0 16 16"
                className="size-3.5 text-ink-faint"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.6"
                aria-hidden="true"
              >
                <path d="M2 8h11M9 4l4 4-4 4" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              {names[target] ?? short(target, 8)}
            </>
          )}
        </span>
        {payload.amount !== undefined && (
          <span className="ml-auto text-[13px] font-semibold tabular-nums">
            {fmt.format(payload.amount)}
          </span>
        )}
      </div>
      <p className="mt-1.5 font-mono text-[11px] text-ink-faint" title={txid}>
        txid {short(txid, 24)}
      </p>
    </div>
  );
}
