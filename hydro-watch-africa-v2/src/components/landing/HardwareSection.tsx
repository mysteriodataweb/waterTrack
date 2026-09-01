import { Cpu, Radio, Satellite } from "lucide-react";
import { SectionLabel } from "./SectionLabel";

const items = [
  { n: "01", icon: Cpu, t: "Mesure pH & Turbidité", d: "Capteur fixe ESP32 — mesure pH, turbidité, nitrates et température en temps réel." },
  { n: "02", icon: Radio, t: "Kit Portable Terrain", d: "Kit portatif 30-50 USD pour agents terrain. Bluetooth sync avec l'app mobile." },
  { n: "03", icon: Satellite, t: "Transmission Satellite", d: "Données synchronisées vers PostgreSQL via connexion GSM/satellite toutes les heures." },
];

export function HardwareSection() {
  return (
    <section className="relative py-32 border-t border-border">
      <div className="mx-auto max-w-[1400px] px-6">
        <SectionLabel index="02" label="HARDWARE SPECIFICATIONS" />
        <h2 className="mt-4 font-mono text-4xl md:text-5xl font-bold uppercase">
          Capteurs Terrain <span className="text-cyan">ESP32</span>
        </h2>

        <div className="mt-16 grid grid-cols-1 lg:grid-cols-2 gap-12 items-start">
          {/* Left: stylized device */}
          <div className="relative border border-border bg-card rounded-sm aspect-square flex items-center justify-center overflow-hidden">
            <div className="absolute inset-0 opacity-20"
              style={{ backgroundImage: "linear-gradient(rgba(0,212,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,255,1) 1px, transparent 1px)", backgroundSize: "30px 30px" }} />
            <div className="relative z-10 size-64 border-2 border-cyan/60 bg-background/80 rounded-sm flex flex-col items-center justify-center glow-cyan">
              <div className="absolute top-3 left-3 font-mono text-[9px] text-cyan tracking-widest">ESP32-WROOM</div>
              <Cpu className="size-32 text-cyan" strokeWidth={0.8} />
              <div className="mt-3 font-mono text-[10px] text-cyan tracking-[0.3em]">v3.2.1</div>
              {/* circuit lines */}
              {[0, 90, 180, 270].map(r => (
                <div key={r} className="absolute top-1/2 left-1/2 w-32 h-px bg-cyan/40"
                  style={{ transform: `translate(-50%,-50%) rotate(${r}deg) translateX(80px)` }} />
              ))}
            </div>
            <div className="absolute bottom-4 left-4 font-mono text-[9px] text-muted-foreground tracking-widest">
              IOT_DEVICE_REF://hw_2026.01
            </div>
          </div>

          <div className="space-y-px bg-border border border-border rounded-sm overflow-hidden">
            {items.map(({ n, icon: Icon, t, d }) => (
              <div key={n} className="bg-card p-6 flex gap-6 hover:bg-cyan/5 transition group">
                <div className="font-mono text-3xl font-bold text-cyan/60 group-hover:text-cyan transition">{n}</div>
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-2">
                    <Icon className="size-4 text-cyan" />
                    <h3 className="font-mono text-base font-bold uppercase tracking-wider">{t}</h3>
                  </div>
                  <p className="text-sm text-muted-foreground leading-relaxed">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
