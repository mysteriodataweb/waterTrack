import { useEffect, useState } from "react";
import { Check, Copy, Share2 } from "lucide-react";
import { fetchAdvice, isAbort, type AdviceAudience, type ApiAdvice } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { Notice } from "@/ui/chrome";

const AUDIENCES: Array<{ key: AdviceAudience; label: string }> = [
  { key: "communaute", label: "Habitants et usagers" },
  { key: "agent_terrain", label: "Agent de terrain" },
  { key: "ong", label: "ONG" },
  { key: "gouvernement", label: "Service de l'État" },
];

// Le public choisi est retenu d'une fiche à l'autre, pour ce navigateur seulement.
const STORAGE_KEY = "watertracker.adviceAudience";

function storedAudience(): AdviceAudience {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    const known = AUDIENCES.find((item) => item.key === value);
    if (known) return known.key;
  } catch {
    // Stockage indisponible (navigation privée) : public par défaut.
  }
  return "communaute";
}

/**
 * Conseil pour agir, construit par le serveur à partir de la prévision affichée
 * dans la fiche (règles fixes, sans modèle de langage) : la réponse est immédiate.
 */
export function AdvicePanel({ reservoirId }: { reservoirId: string }) {
  const [audience, setAudience] = useState<AdviceAudience>(storedAudience);
  const [advice, setAdvice] = useState<ApiAdvice | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [copied, setCopied] = useState<"done" | "failed" | null>(null);

  useEffect(() => {
    setAdvice(null);
    setFailed(false);
    const controller = new AbortController();
    fetchAdvice(reservoirId, controller.signal)
      .then(setAdvice)
      .catch((err: unknown) => { if (!isAbort(err)) setFailed(true); });
    return () => controller.abort();
  }, [reservoirId, attempt]);

  useEffect(() => setCopied(null), [reservoirId, audience]);

  const choose = (key: AdviceAudience) => {
    setAudience(key);
    try {
      window.localStorage.setItem(STORAGE_KEY, key);
    } catch {
      // Sans stockage, le choix vaut pour cette fiche seulement.
    }
  };

  const current = advice?.audiences[audience] ?? null;
  const canShare = typeof navigator !== "undefined" && typeof navigator.share === "function";

  const copy = async () => {
    if (!current) return;
    setCopied((await copyText(current.text)) ? "done" : "failed");
    setTimeout(() => setCopied(null), 3000);
  };

  const share = async () => {
    if (!current) return;
    try {
      await navigator.share({ text: current.text });
    } catch {
      // Partage annulé par l'utilisateur.
    }
  };

  return (
    <div>
      <fieldset>
        <legend className="mb-2 text-[14px] font-semibold text-ink">Pour qui ?</legend>
        <div className="flex flex-wrap gap-2">
          {AUDIENCES.map((item) => {
            const active = item.key === audience;
            return (
              <button
                key={item.key}
                type="button"
                aria-pressed={active}
                onClick={() => choose(item.key)}
                className={`h-10 rounded-full border px-3.5 text-[15px] font-semibold ${
                  active
                    ? "border-water bg-water-soft text-water-deep"
                    : "border-line-strong bg-surface text-ink-2 hover:bg-sunken hover:text-ink"
                }`}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </fieldset>

      <div aria-live="polite" className="mt-4">
        {failed && (
          <Notice tone="warn">
            Le conseil n'a pas pu être chargé.{" "}
            <button type="button" onClick={() => setAttempt((n) => n + 1)} className="font-semibold text-water underline">
              Réessayer
            </button>
          </Notice>
        )}
        {!failed && !advice && <div className="skeleton h-[120px] w-full" role="status" aria-label="Chargement du conseil" />}
        {advice && current && (
          <>
            <h4 className="text-[15px] font-semibold text-ink">À faire</h4>
            <ul className="mt-2 space-y-2 text-[16px] leading-snug text-ink">
              {current.actions.map((action) => (
                <li key={action} className="flex gap-2.5">
                  <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full bg-water" aria-hidden="true" />
                  <span>{action}</span>
                </li>
              ))}
            </ul>
            {advice.when && (
              <p className="mt-3 text-[16px] text-ink">
                <span className="font-semibold">Quand : </span>{advice.when}.
              </p>
            )}

            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={copy}
                className="inline-flex h-11 items-center gap-2 rounded-lg border border-water bg-surface px-4 text-[15px] font-semibold text-water hover:bg-water-soft"
              >
                {copied === "done" ? <Check size={17} aria-hidden="true" /> : <Copy size={17} aria-hidden="true" />}
                <span aria-live="polite">
                  {copied === "done" ? "Message copié" : copied === "failed" ? "Copie impossible" : "Copier le message"}
                </span>
              </button>
              {canShare && (
                <button
                  type="button"
                  onClick={share}
                  className="inline-flex h-11 items-center gap-2 rounded-lg border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink hover:bg-sunken"
                >
                  <Share2 size={17} aria-hidden="true" /> Partager
                </button>
              )}
            </div>
            <p className="mt-2 text-[14px] text-ink-2">
              Le message reprend la synthèse, les chiffres de la prévision et ces actions.
            </p>

            <ul className="mt-4 space-y-1 text-[14px] leading-snug text-ink-3">
              {advice.caveats.map((caveat) => <li key={caveat}>{caveat}</li>)}
            </ul>
            <p className="mt-2 text-[13px] text-ink-3">
              Conseil établi par des règles fixes à partir de la prévision ci-dessus : la même situation donne
              toujours le même conseil.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
