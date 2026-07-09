// Le bouton transfer du header et son popup : formulaire custodial (le node
// signe avec le wallet sponsor) + miner le prochain bloc, au meme endroit —
// on soumet, on mine, on voit la tx incluse.

import { useEffect, useState } from "react";
import { getBlocks, mine, postTransfer, type MineResult } from "../api";

export type TransferPrefill = { address: string; at: number } | null;

const short = (hex: string) => `${hex.slice(0, 10)}…`;

export function TransferPopup({
  base,
  disabled,
  height,
  prefill,
  open,
  onToggle,
  onClose,
}: {
  base: string | undefined;
  disabled: boolean;
  height: number;
  prefill: TransferPrefill;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}) {
  const [recipient, setRecipient] = useState("");
  const [amount, setAmount] = useState(1_000);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [txid, setTxid] = useState<string | null>(null);
  const [includedIn, setIncludedIn] = useState<number | null>(null);
  const [mining, setMining] = useState(false);
  const [mined, setMined] = useState<MineResult | null>(null);

  // "envoyer un transfer a ce node" depuis la fiche node
  useEffect(() => {
    if (prefill) setRecipient(prefill.address);
  }, [prefill]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Confirmation d'inclusion : a chaque bloc (tick SSE -> height), cherche le
  // txid en attente dans les txids des derniers blocs.
  useEffect(() => {
    if (!base || txid === null || includedIn !== null) return;
    let cancelled = false;
    getBlocks(base, Math.max(0, height - 5))
      .then((blocks) => {
        const hit = blocks.find((entry) => entry.txids?.includes(txid));
        if (!cancelled && hit) setIncludedIn(hit.block.header.height);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [base, txid, height, includedIn]);

  async function submit() {
    if (!base || pending) return;
    setPending(true);
    setError(null);
    setIncludedIn(null);
    try {
      setTxid(await postTransfer(base, recipient.trim(), amount));
    } catch (exc) {
      setTxid(null);
      setError(exc instanceof Error ? exc.message : "erreur");
    } finally {
      setPending(false);
    }
  }

  async function mineNext() {
    if (!base || mining) return;
    setMining(true);
    setError(null);
    try {
      setMined(await mine(base));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "erreur");
    } finally {
      setMining(false);
    }
  }

  return (
    <div className="relative">
      <button
        onClick={onToggle}
        disabled={disabled}
        className="flex h-[30px] items-center gap-1.5 rounded-[8px] bg-ink px-2.5 text-[12px] text-paper shadow-[0_0_0_1px_rgba(0,0,0,0.06),0_1px_2px_rgba(0,0,0,0.05)] transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-50"
      >
        transfer
        <svg
          viewBox="0 0 256 256"
          className={`h-2.5 w-2.5 opacity-70 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M213.66,101.66l-80,80a8,8,0,0,1-11.32,0l-80-80A8,8,0,0,1,53.66,90.34L128,164.69l74.34-74.35a8,8,0,0,1,11.32,11.32Z" />
        </svg>
      </button>

      {open && (
        <>
          <div className="fixed inset-0" onClick={onClose} />
          <div className="absolute right-0 top-full z-10 mt-2 w-[330px] rounded-[10px] border border-line bg-card/95 p-3 text-left text-ink shadow-[0_2px_6px_rgba(0,0,0,0.08),0_16px_40px_rgba(0,0,0,0.16)] backdrop-blur-md">
            <p className="text-[10px] uppercase tracking-[0.12em] text-ink-faint">
              transfer — signé par le wallet sponsor
            </p>
            <input
              value={recipient}
              onChange={(event) => setRecipient(event.target.value)}
              className="mt-2 w-full rounded-[6px] border border-line px-2.5 py-2 font-mono text-[12px] text-ink outline-none transition placeholder:font-sans placeholder:text-ink-faint focus:border-ink/25"
              placeholder="adresse du destinataire (hex)"
              spellCheck={false}
            />
            <div className="mt-2 flex items-center gap-2">
              <label className="flex flex-1 items-center gap-1.5 rounded-[6px] border border-line px-2.5 py-1.5">
                <span className="text-[9px] uppercase tracking-[0.1em] text-ink-faint">
                  montant
                </span>
                <input
                  type="number"
                  value={amount}
                  min={1}
                  step={100}
                  onChange={(event) => setAmount(Number(event.target.value))}
                  className="w-full bg-transparent text-right text-[12px] tabular-nums outline-none"
                />
              </label>
              <button
                onClick={submit}
                disabled={disabled || pending || recipient.trim().length === 0 || amount <= 0}
                className="rounded-[6px] bg-ink px-3 py-1.5 text-[12px] text-paper transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {pending ? "…" : "envoyer"}
              </button>
            </div>
            {txid && (
              <p className="mt-2 text-[11px] text-ink-soft">
                tx <span className="font-mono">{short(txid)}</span>{" "}
                {includedIn !== null ? (
                  <span style={{ color: "var(--color-olive)" }}>
                    incluse au bloc #{includedIn} ✓
                  </span>
                ) : (
                  <span className="text-ink-faint">en attente du prochain bloc…</span>
                )}
              </p>
            )}

            <div className="my-3 border-t border-dashed border-line" />

            <button
              onClick={mineNext}
              disabled={disabled || mining}
              className="flex w-full items-center justify-center gap-2 rounded-[6px] border border-line py-2 text-[11px] uppercase tracking-[0.1em] text-ink-soft transition hover:border-ink/25 hover:text-ink disabled:cursor-not-allowed disabled:opacity-40"
            >
              {mining && (
                <span
                  className="size-1.5 animate-pulse rounded-full"
                  style={{ backgroundColor: "var(--color-amber)" }}
                />
              )}
              {mining ? "attente du bloc…" : "miner le prochain bloc"}
            </button>
            {mined && (
              <p className="mt-2 text-[11px] text-ink-soft">
                bloc #{mined.block.header.height} finalisé ·{" "}
                <span className="font-mono">{short(mined.hash)}</span> · {mined.txids.length}{" "}
                tx · qc {mined.consensus.voters.length}
                {txid && mined.txids.includes(txid) && (
                  <span style={{ color: "var(--color-olive)" }}> · contient votre tx ✓</span>
                )}
              </p>
            )}
            {error && <p className="mt-2 text-[11px] text-danger">{error}</p>}
          </div>
        </>
      )}
    </div>
  );
}
