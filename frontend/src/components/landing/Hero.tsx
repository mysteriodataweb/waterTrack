import { ArrowRight, FileCode, Activity } from "lucide-react";
import { TelemetryPanel } from "./TelemetryPanel";

export function Hero() {
  return (
    <section className="relative min-h-screen pt-14 overflow-hidden">
      {/* Space background */}
      <div className="absolute inset-0 -z-10">
        <div
          className="absolute inset-0 opacity-50"
          style={{
            background:
              "radial-gradient(ellipse at 70% 40%, rgba(0,212,255,0.15), transparent 60%), radial-gradient(ellipse at 20% 80%, rgba(0,80,120,0.25), transparent 70%), #050a0f",
          }}
        />
        <div
          className="absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "radial-gradient(1px 1px at 20% 30%, white, transparent), radial-gradient(1px 1px at 70% 60%, white, transparent), radial-gradient(1px 1px at 40% 80%, white, transparent), radial-gradient(2px 2px at 90% 20%, white, transparent), radial-gradient(1px 1px at 50% 50%, white, transparent)",
            backgroundSize: "200px 200px",
          }}
        />
        {/* Africa silhouette glow */}
        <div className="absolute right-[-10%] top-1/4 size-[600px] rounded-full opacity-30"
          style={{ background: "radial-gradient(circle, rgba(0,212,255,0.3), transparent 60%)" }} />
        {/* Grid */}
        <div className="absolute inset-0 opacity-[0.07]"
          style={{
            backgroundImage: "linear-gradient(rgba(0,212,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,1) 1px, transparent 1px)",
            backgroundSize: "80px 80px",
          }}
        />
      </div>

      <div className="mx-auto max-w-[1400px] px-6 pt-20 pb-32 grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
        <div className="lg:col-span-7 space-y-8">
          <div className="inline-flex items-center gap-2 border border-status-active/40 bg-status-active/10 px-3 py-1.5 rounded-sm font-mono text-[10px] tracking-[0.25em] text-status-active">
            <Activity className="size-3 animate-pulse" />
            STATUS: ORBITAL LINK ACTIVE
          </div>

          <h1 className="font-mono text-5xl md:text-7xl font-bold tracking-tight leading-[0.95] uppercase">
            Surveillance<br />
            <span className="text-cyan text-glow">Hydrique</span><br />
            Orbitale
          </h1>

          <p className="max-w-xl text-base text-muted-foreground leading-relaxed">
            Cartographiez les ressources vitales depuis l'espace. WaterTracker fusionne
            l'intelligence artificielle et la télémétrie satellitaire pour une gestion
            précise de l'eau en Afrique subsaharienne.
          </p>

          <div className="flex flex-wrap gap-4">
            <button className="group inline-flex items-center gap-2 bg-cyan text-primary-foreground font-mono text-[11px] tracking-[0.25em] font-bold px-6 py-3.5 rounded-sm glow-cyan hover:bg-cyan/90 transition">
              INITIALISER LE SCAN
              <ArrowRight className="size-3.5 group-hover:translate-x-1 transition" />
            </button>
            <button className="inline-flex items-center gap-2 border border-cyan/50 text-cyan font-mono text-[11px] tracking-[0.25em] font-bold px-6 py-3.5 rounded-sm hover:bg-cyan/10 transition">
              <FileCode className="size-3.5" />
              DOCUMENTATION API
            </button>
          </div>

          <div className="flex gap-8 pt-4 font-mono text-[10px] tracking-[0.2em] text-muted-foreground">
            <div><span className="text-cyan">LAT</span> 12.3647°N</div>
            <div><span className="text-cyan">LON</span> -1.5221°W</div>
            <div><span className="text-cyan">SAT</span> SENTINEL-2</div>
          </div>
        </div>

        <div className="lg:col-span-5">
          <TelemetryPanel />
        </div>
      </div>
    </section>
  );
}
