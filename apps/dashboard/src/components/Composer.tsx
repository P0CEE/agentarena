// Le composer sponsor : soumettre une task (brief + prix) au node de référence.
// Style « input flottant » : verre depoli, bordure fine, bouton fleche.

import { useState } from "react";
import { createTask } from "../api";
import { RoleChip } from "./bits";

const DEFAULT_BRIEF =
  "Ecris une fonction Python is_prime(n) documentee, avec la gestion des cas limites et trois exemples d'utilisation.";

export function Composer({
  base,
  disabled,
  onCreated,
}: {
  base: string | undefined;
  disabled: boolean;
  onCreated: (taskId: string) => void;
}) {
  const [brief, setBrief] = useState(DEFAULT_BRIEF);
  const [prize, setPrize] = useState(50_000);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!base || pending) return;
    setPending(true);
    setError(null);
    try {
      onCreated(await createTask(base, brief, prize));
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "erreur");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="rounded-[8px] border border-line bg-card/90 p-2.5 shadow-[0_8px_24px_rgba(0,0,0,0.12)] backdrop-blur-md">
      <div className="mb-2 flex items-center gap-2">
        <RoleChip role="sponsor" />
        <span className="text-[10px] uppercase tracking-[0.1em] text-ink-soft">
          nouvelle manche
        </span>
      </div>
      <textarea
        value={brief}
        onChange={(event) => setBrief(event.target.value)}
        rows={3}
        className="w-full resize-none rounded-[6px] border border-line px-2.5 py-2 text-[12px] leading-[1.6] text-ink outline-none transition placeholder:text-ink-faint focus:border-ink/25"
        placeholder="Le brief pour les builders..."
      />
      <div className="mt-2 flex items-center justify-between gap-2">
        <label className="flex items-center gap-1.5 rounded-[6px] border border-line px-2.5 py-1.5">
          <span className="text-[9px] uppercase tracking-[0.1em] text-ink-faint">prix</span>
          <input
            type="number"
            value={prize}
            min={10_000}
            step={5_000}
            onChange={(event) => setPrize(Number(event.target.value))}
            className="w-20 bg-transparent text-right text-[12px] tabular-nums outline-none"
          />
        </label>
        <button
          onClick={submit}
          disabled={disabled || pending || brief.trim().length === 0}
          aria-label="lancer la manche"
          className="flex size-7 shrink-0 items-center justify-center rounded-[6px] bg-ink text-paper transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pending ? (
            "…"
          ) : (
            <svg viewBox="0 0 256 256" className="size-3.5" fill="currentColor" aria-hidden="true">
              <path d="M205.66,117.66a8,8,0,0,1-11.32,0L136,59.31V216a8,8,0,0,1-16,0V59.31L61.66,117.66a8,8,0,0,1-11.32-11.32l72-72a8,8,0,0,1,11.32,0l72,72A8,8,0,0,1,205.66,117.66Z" />
            </svg>
          )}
        </button>
      </div>
      {error && <p className="mt-2 text-[11px] text-danger">{error}</p>}
    </div>
  );
}
