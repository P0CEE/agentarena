// Le composer sponsor : soumettre une task (brief + prix) au node de référence.

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
    <div className="rounded-[10px] bg-card p-3 shadow-[0_1px_2px_rgba(30,25,10,0.05),0_6px_16px_rgba(30,25,10,0.07)]">
      <div className="mb-2 flex items-center gap-2">
        <RoleChip role="sponsor" />
        <span className="text-[10px] uppercase tracking-[0.1em] text-ink-soft">
          nouvelle manche
        </span>
      </div>
      <textarea
        value={brief}
        onChange={(event) => setBrief(event.target.value)}
        rows={4}
        className="w-full resize-none rounded-[6px] border border-line bg-paper/60 p-2 text-[11px] leading-[1.5] text-ink outline-none focus:border-ink-faint"
        placeholder="Le brief pour les builders..."
      />
      <div className="mt-2 flex items-center gap-2">
        <label className="flex flex-1 items-center gap-2 rounded-[6px] border border-line px-2 py-1.5">
          <span className="text-[9px] uppercase tracking-[0.1em] text-ink-faint">prix</span>
          <input
            type="number"
            value={prize}
            min={10_000}
            step={5_000}
            onChange={(event) => setPrize(Number(event.target.value))}
            className="w-full bg-transparent text-right text-[11px] tabular-nums outline-none"
          />
        </label>
        <button
          onClick={submit}
          disabled={disabled || pending || brief.trim().length === 0}
          className="rounded-[6px] bg-ink px-3 py-2 text-[11px] font-semibold text-paper transition hover:opacity-85 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pending ? "..." : "lancer"}
        </button>
      </div>
      {error && <p className="mt-2 text-[10px] text-danger">{error}</p>}
    </div>
  );
}
