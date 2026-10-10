import { useEffect, useRef, useState, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { ApiError, fetchAdvice, isAbort, type AdviceProfile, type ApiAdvice } from "@/lib/api";
import { Notice } from "@/ui/chrome";

const PROFILES: Array<{ key: AdviceProfile; label: string }> = [
  { key: "communaute", label: "Habitants et usagers" },
  { key: "agent_terrain", label: "Agent de terrain" },
  { key: "ong", label: "ONG" },
  { key: "gouvernement", label: "Service de l'État" },
];

/** Le texte arrive avec du gras en **astérisques** et des retours à la ligne. */
function renderAdvice(text: string): ReactNode {
  return text.split(/\n+/).filter((line) => line.trim()).map((line, index) => (
    <p key={index} className={index > 0 ? "mt-2" : ""}>
      {line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
        part.startsWith("**") && part.endsWith("**")
          ? <strong key={i} className="font-semibold">{part.slice(2, -2)}</strong>
          : part.replace(/^[-•]\s*/, ""))}
    </p>
  ));
}

/** "2025-S1" est-il un semestre déjà terminé ? */
function isPastSemester(value: string | null | undefined): boolean {
  const match = /^(\d{4})-S([12])$/.exec(value ?? "");
  if (!match) return false;
  const end = new Date(Number(match[1]), match[2] === "1" ? 6 : 12, 1);
  return end.getTime() <= Date.now();
}

export function AdvicePanel({ sourceId }: { sourceId: number }) {
  const [profile, setProfile] = useState<AdviceProfile>("communaute");
  const [advice, setAdvice] = useState<ApiAdvice | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);

  // Changer de retenue ou de public efface le conseil précédent.
  useEffect(() => {
    controllerRef.current?.abort();
    setAdvice(null);
    setError(null);
    setLoading(false);
  }, [sourceId, profile]);
  useEffect(() => () => controllerRef.current?.abort(), []);

  const generate = async () => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      setAdvice(await fetchAdvice(sourceId, profile, controller.signal));
    } catch (err) {
      if (isAbort(err)) return;
      setError(
        err instanceof ApiError && err.kind === "http" && err.status !== null && err.status < 500
          ? "Pas assez d'historique sur ce plan d'eau pour rédiger un conseil."
          : "Le conseil n'a pas pu être rédigé. Réessayez dans un instant.",
      );
    } finally {
      if (!controller.signal.aborted) setLoading(false);
    }
  };

  return (
    <div>
      <p className="text-[15px] text-ink-2">
        Un texte court, rédigé automatiquement, adapté à la personne qui doit agir.
      </p>
      <div className="mt-3 flex flex-wrap items-end gap-2">
        <label className="block min-w-0 flex-1">
          <span className="mb-1 block text-[14px] font-semibold text-ink">Pour qui ?</span>
          <select
            value={profile}
            onChange={(event) => setProfile(event.target.value as AdviceProfile)}
            className="h-11 w-full rounded-lg border border-line-strong bg-surface px-3 text-[16px] text-ink"
          >
            {PROFILES.map((item) => <option key={item.key} value={item.key}>{item.label}</option>)}
          </select>
        </label>
        <button
          type="button"
          onClick={generate}
          disabled={loading}
          className="inline-flex h-11 items-center gap-2 rounded-lg border border-water bg-surface px-4 text-[15px] font-semibold text-water hover:bg-water-soft disabled:opacity-60"
        >
          {loading && <LoaderCircle size={16} className="spin" aria-hidden="true" />}
          {loading ? "Rédaction…" : advice ? "Rédiger à nouveau" : "Rédiger le conseil"}
        </button>
      </div>

      <div aria-live="polite" className="mt-3 space-y-3">
        {loading && <p className="text-[14px] text-ink-2">Cela prend une dizaine de secondes.</p>}
        {error && <Notice tone="warn">{error}</Notice>}
        {advice && !loading && (
          <>
            {isPastSemester(advice.date_tarissement) && (
              <Notice tone="warn">
                Ce conseil s'appuie sur l'ancienne analyse par semestre, dont les données s'arrêtent avant
                la période qu'il cite ({advice.date_tarissement}). En cas de contradiction, fiez-vous à la
                prévision mensuelle ci-dessus.
              </Notice>
            )}
            <div className="rounded-lg border bg-surface p-3.5 text-[16px] leading-relaxed text-ink">
              {advice.recommandation ? renderAdvice(advice.recommandation) : "Aucun conseil n'a été renvoyé pour ce plan d'eau."}
            </div>
            <p className="text-[13px] text-ink-3">
              Texte généré par un modèle de langage : à relire avant toute décision.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
