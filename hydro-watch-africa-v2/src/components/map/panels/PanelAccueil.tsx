import { ArrowRight } from "lucide-react";
import type { Source } from "../types";

export function PanelAccueil({ sources, onSelect }: { sources: Source[]; onSelect: (s: Source) => void }) {
  const counts = {
    actif: sources.filter(s => s.statut === "actif").length,
    risque: sources.filter(s => s.statut === "à risque").length,
    tari: sources.filter(s => s.statut === "tari").length,
  };
  const critical = [...sources].filter(s => s.risk_score > 0.7).slice(0, 5);

  return (
    <div className="p-5 space-y-6">
      <div className="font-mono text-[10px] tracking-[0.25em] text-cyan">// APERÇU GÉNÉRAL</div>

      <div className="space-y-2">
        {[
          { c: "#00ff88", n: counts.actif, l: "ACTIVES" },
          { c: "#ffd700", n: counts.risque, l: "À RISQUE" },
          { c: "#ff4444", n: counts.tari, l: "TARIES" },
        ].map((s) => (
          <div key={s.l} className="flex items-center gap-3 p-2.5 border border-cyan/10 rounded-sm bg-cyan/5">
            <span className="size-2.5 rounded-full" style={{ background: s.c, boxShadow: `0 0 8px ${s.c}` }} />
            <span className="font-mono text-base font-bold text-foreground">{s.n}</span>
            <span className="font-mono text-[10px] tracking-widest text-muted-foreground ml-auto">{s.l}</span>
          </div>
        ))}
      </div>

      <div className="border-t border-cyan/10 pt-5 space-y-3">
        <div className="font-mono text-[10px] tracking-[0.25em] text-cyan">SOURCES CRITIQUES</div>
        {critical.map((s) => (
          <div key={s.id} className="border border-cyan/15 bg-cyan/5 rounded-sm p-3 hover:border-cyan/40 transition">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-xs font-bold">SOURCE {s.label.toUpperCase()}</span>
              <span className="font-mono text-[9px] tracking-widest px-1.5 py-0.5 rounded-sm"
                style={{ background: s.statut === "tari" ? "rgba(255,68,68,0.15)" : "rgba(255,215,0,0.15)", color: s.statut === "tari" ? "#ff4444" : "#ffd700" }}>
                {s.statut.toUpperCase()}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-muted-foreground">RISK {(s.risk_score * 100).toFixed(0)}%</span>
              <button onClick={() => onSelect(s)} className="font-mono text-[10px] text-cyan flex items-center gap-1 hover:gap-1.5 transition">
                ANALYSER <ArrowRight className="size-3" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
