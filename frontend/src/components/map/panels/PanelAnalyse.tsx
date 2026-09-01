import { useEffect, useMemo, useState } from "react";
import { Brain, Loader2, Search } from "lucide-react";
import { fetchSourcePrediction, type PredictionProfile, type SourcePrediction } from "../api";
import type { Source } from "../types";

const profiles: Array<{ key: PredictionProfile; label: string }> = [
  { key: "ong", label: "ONG" },
  { key: "gouvernement", label: "Gouvernement" },
  { key: "agent_terrain", label: "Agent" },
  { key: "communaute", label: "Communaute" },
];

export function PanelAnalyse({
  sources,
  targetSource,
  actionNonce,
}: {
  sources: Source[];
  targetSource: Source | null;
  actionNonce: number;
}) {
  const [profile, setProfile] = useState<PredictionProfile>("communaute");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [prediction, setPrediction] = useState<SourcePrediction | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sortedSources = useMemo(
    () => [...sources].sort((a, b) => b.risk_score - a.risk_score),
    [sources],
  );

  const visibleSources = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return sortedSources.slice(0, 8);

    return sortedSources
      .filter((source) =>
        `source ${source.id} ${source.label} ${source.zone_detail ?? source.zone ?? ""} ${source.statut}`
          .toLowerCase()
          .includes(normalized),
      )
      .slice(0, 8);
  }, [query, sortedSources]);

  const selectedSource = useMemo(
    () => sortedSources.find((source) => source.id === selectedId) ?? sortedSources[0] ?? null,
    [selectedId, sortedSources],
  );

  useEffect(() => {
    if (!targetSource) return;
    setSelectedId(targetSource.id);
    setQuery(`source ${targetSource.id}`);
  }, [targetSource, actionNonce]);

  useEffect(() => {
    if (!selectedSource) return;
    if (selectedId === null) setSelectedId(selectedSource.id);

    const controller = new AbortController();
    setLoading(true);
    setError(null);
    setPrediction(null);

    fetchSourcePrediction(selectedSource.id, profile, controller.signal)
      .then(setPrediction)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Prediction indisponible");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [profile, selectedSource, selectedId]);

  const recommendation = prediction?.recommandation
    ?? prediction?.recommandations?.[profile]
    ?? prediction?.erreur
    ?? "Aucune recommandation disponible.";

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#9fc9ea]">
        <Brain className="size-4" /> Centre analyse IA
      </div>

      <label className="flex h-10 items-center gap-2 rounded-md border border-[#2a3140] bg-[#151a21] px-3 text-[#a3afbd] focus-within:border-[#9fc9ea]">
        <Search className="size-4" />
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Rechercher une source"
          className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-[#6f8ba0]"
        />
      </label>

      <div className="grid grid-cols-2 gap-2">
        {profiles.map((item) => (
          <button
            key={item.key}
            onClick={() => setProfile(item.key)}
            className={`rounded-md border px-3 py-2 text-xs font-medium transition ${
              profile === item.key
                ? "border-[#9fc9ea] bg-[#20262d] text-white"
                : "border-[#2a3140] text-[#a3afbd] hover:bg-[#171b22] hover:text-white"
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-2">
        {visibleSources.map((source) => (
          <button
            key={source.id}
            onClick={() => setSelectedId(source.id)}
            className={`rounded-md border p-3 text-left transition ${
              selectedSource?.id === source.id
                ? "border-[#9fc9ea] bg-[#20262d]"
                : "border-[#2a3140] bg-[#151a21] hover:bg-[#171b22]"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-white">{source.label}</span>
              <span className="text-xs text-[#9fc9ea]">{Math.round(source.risk_score * 100)}%</span>
            </div>
            <div className="mt-1 text-[11px] text-[#a3afbd]">{(source.zone_detail ?? source.zone ?? "Ouagadougou")} · {source.statut}</div>
          </button>
        ))}
      </div>

      <div className="rounded-md border border-[#2a3140] bg-black/40 p-4 min-h-[150px]">
        {loading && (
          <div className="flex items-center gap-2 text-sm text-[#a3afbd]">
            <Loader2 className="size-4 animate-spin" /> Analyse Prophet + Groq en cours...
          </div>
        )}

        {!loading && error && (
          <div className="text-sm leading-relaxed text-[#ffb4b4]">{error}</div>
        )}

        {!loading && !error && prediction && (
          <div className="space-y-4">
            <div className="grid grid-cols-4 gap-2">
              <Metric label="NDWI" value={formatNumber(prediction.ndwi_actuel)} />
              <Metric label="Tendance" value={formatNumber(prediction.tendance)} />
              <Metric label="Confiance" value={`${prediction.confiance ?? 0}%`} />
              <Metric label="Tarissement" value={prediction.date_tarissement ?? "Non estime"} />
            </div>

            <div className="rounded-md border border-[#2a3140] bg-[#151a21] p-3 text-sm leading-relaxed text-white/90">
              {recommendation}
            </div>

            <div className="space-y-2">
              {prediction.predictions?.map((item) => (
                <div key={item.periode} className="grid grid-cols-[80px_1fr_56px] items-center gap-3 text-xs">
                  <span className="text-[#a3afbd]">{item.periode}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-[#262d35]">
                    <div
                      className="h-full rounded-full bg-[#9fc9ea]"
                      style={{ width: `${Math.max(4, Math.min(100, item.probabilite_tarissement))}%` }}
                    />
                  </div>
                  <span className="text-right text-[#9fc9ea]">{item.probabilite_tarissement.toFixed(1)}%</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#2a3140] bg-[#151a21] p-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-[#a3afbd]">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-[#9fc9ea]">{value}</div>
    </div>
  );
}

function formatNumber(value: number | undefined): string {
  return typeof value === "number" ? value.toFixed(3) : "-";
}
