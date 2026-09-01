import { Waves, Globe2, Shield, Brain } from "lucide-react";
import { SectionLabel } from "./SectionLabel";

export function MissionSection() {
  return (
    <section className="relative py-32 border-t border-border">
      <div className="mx-auto max-w-[1400px] px-6">
        <SectionLabel index="01" label="MISSION OVERVIEW" />
        <h2 className="mt-4 max-w-3xl font-mono text-4xl md:text-5xl font-bold uppercase leading-tight">
          Cartographie de l'Avenir <span className="text-cyan">Hydrologique</span>
        </h2>

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left card */}
          <div className="relative border border-border bg-card p-8 rounded-sm">
            <div className="font-mono text-[10px] tracking-[0.25em] text-cyan mb-4">// MULTI_SPECTRAL</div>
            <h3 className="font-mono text-2xl font-bold uppercase mb-4">Analyse Spectrale Multi-Bandes</h3>
            <p className="text-muted-foreground leading-relaxed mb-10">
              Sentinel-2 capture 13 bandes spectrales simultanément. Le calcul NDWI
              (Normalized Difference Water Index) identifie chaque source d'eau à 10m
              de résolution. Les 278 sources détectées autour de Ouagadougou sont mises
              à jour toutes les 5 jours.
            </p>
            <div className="grid grid-cols-3 gap-4 pt-6 border-t border-border">
              {[
                ["278", "SOURCES DÉTECTÉES"],
                ["2 780", "OBSERVATIONS HISTORIQUES"],
                ["5 ANS", "HISTORIQUE SATELLITE"],
              ].map(([v, l]) => (
                <div key={l}>
                  <div className="font-mono text-3xl font-bold text-cyan text-glow">{v}</div>
                  <div className="font-mono text-[9px] tracking-[0.2em] text-muted-foreground mt-2 leading-relaxed">{l}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-6">
            <div className="relative border border-border bg-card rounded-sm overflow-hidden">
              <div
                className="h-40 relative"
                style={{
                  background:
                    "radial-gradient(circle at 50% 60%, rgba(0,212,255,0.4), transparent 50%), radial-gradient(circle at 50% 60%, #001a2b, #050a0f)",
                }}
              >
                <Globe2 className="absolute inset-0 m-auto size-24 text-cyan/70" strokeWidth={0.8} />
              </div>
              <div className="p-6">
                <div className="font-mono text-[10px] tracking-[0.25em] text-cyan mb-2">// AI_FORECAST</div>
                <h3 className="font-mono text-xl font-bold uppercase mb-2">Analyse Prédictive IA</h3>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  Prophet prédit le tarissement de chaque source avec intervalles de
                  confiance sur 3 semestres.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-px bg-border border border-border rounded-sm overflow-hidden">
              {[
                { icon: Waves, t: "Stress Hydrique", d: "Score de risque en temps réel par source" },
                { icon: Brain, t: "Impact Terrain", d: "Recommandations IA par profil utilisateur" },
                { icon: Shield, t: "Données Sécurisées", d: "Infrastructure certifiée pour ONG et gouvernements" },
              ].map(({ icon: Icon, t, d }) => (
                <div key={t} className="bg-card p-5 hover:bg-cyan/5 transition">
                  <Icon className="size-5 text-cyan mb-3" />
                  <div className="font-mono text-[11px] font-bold uppercase mb-1.5">{t}</div>
                  <div className="text-xs text-muted-foreground leading-relaxed">{d}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
