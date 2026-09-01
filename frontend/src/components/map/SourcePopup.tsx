import { Brain, Navigation, X } from "lucide-react";
import type { Source } from "./types";

export function SourcePopup({
  source,
  onAnalyze,
  onNavigate,
  onClose,
}: {
  source: Source;
  onAnalyze: (source: Source) => void;
  onNavigate: (source: Source) => void;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed bottom-3 left-1/2 z-50 w-[calc(100vw-1.5rem)] max-w-[420px] -translate-x-1/2 overflow-hidden rounded-md border border-[#2c3442]/70 bg-[#13171e]/90 backdrop-blur-xl text-white shadow-[0_24px_80px_rgba(5,7,10,0.4)] sm:bottom-6 sm:bg-[#13171e]/75"
      style={{ animation: "slide-up 0.2s ease-out" }}
    >
      <style>{`@keyframes slide-up { from { transform: translate(-50%, 20px); opacity: 0; } to { transform: translate(-50%, 0); opacity: 1; } }`}</style>
      <div className="flex items-center justify-between border-b border-[#2a3140]/70 bg-[#151a21]/60 px-4 py-2.5">
        <span className="min-w-0 truncate text-[10px] font-bold tracking-[0.16em] text-[#9fc9ea] sm:text-[11px] sm:tracking-[0.2em]">WATER_SOURCE: {source.label.toUpperCase()}</span>
        <button onClick={onClose} className="shrink-0 text-[#a3afbd] transition hover:text-white" aria-label="Fermer">
          <X className="size-4" />
        </button>
      </div>
      <div className="grid grid-cols-2 gap-3 p-4 text-[11px]">
        <Row label="STATUS" value={source.statut.toUpperCase()} color={source.statut === "actif" ? "#62e6a6" : source.statut === "à risque" ? "#f6c65b" : "#ff6b6b"} />
        <Row label="NDWI" value={source.ndwi.toFixed(3)} />
        <Row label="RISK_SCORE" value={`${(source.risk_score * 100).toFixed(0)}%`} />
        <Row label="TARISSEMENT_EST." value={source.tarissement_estime ?? "-"} />
        <Row label="SUPERFICIE" value={`${source.superficie.toFixed(3)} km2`} />
        <Row label="ZONE" value={(source.zone_detail ?? source.zone ?? "Ouagadougou").toUpperCase()} />
      </div>
      <div className="grid grid-cols-2 gap-px bg-[#2a3140]">
        <button
          onClick={() => onAnalyze(source)}
          className="flex items-center justify-center gap-2 bg-[#232a32] py-3 text-[10px] font-bold tracking-widest text-white transition hover:bg-[#2b333d]"
        >
          <Brain className="size-3.5" /> ANALYSER IA
        </button>
        <button
          onClick={() => onNavigate(source)}
          className="flex items-center justify-center gap-2 bg-[#13171e] py-3 text-[10px] font-bold tracking-widest text-[#9fc9ea] transition hover:bg-[#20262d]"
        >
          <Navigation className="size-3.5" /> M'Y GUIDER
        </button>
      </div>
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="min-w-0">
      <div className="truncate text-[9px] tracking-widest text-[#a3afbd]">{label}</div>
      <div className="mt-0.5 truncate font-bold" style={{ color: color ?? "#9fc9ea" }}>{value}</div>
    </div>
  );
}
