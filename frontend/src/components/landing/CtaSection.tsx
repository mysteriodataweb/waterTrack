import { ArrowRight } from "lucide-react";

export function CtaSection() {
  return (
    <section className="relative py-32 border-t border-border overflow-hidden">
      <div className="absolute inset-0 -z-10"
        style={{ background: "radial-gradient(ellipse at center, rgba(0,212,255,0.12), transparent 60%)" }} />
      <div className="mx-auto max-w-3xl px-6 text-center">
        <div className="font-mono text-[10px] tracking-[0.3em] text-cyan mb-6">// FINAL_TRANSMISSION</div>
        <h2 className="font-mono text-4xl md:text-5xl font-bold uppercase leading-tight">
          Prêt à surveiller<br />vos <span className="text-cyan text-glow">ressources</span> ?
        </h2>
        <p className="mt-6 text-muted-foreground max-w-xl mx-auto">
          Rejoignez les ONG et gouvernements qui utilisent WaterTracker pour
          protéger l'eau en Afrique.
        </p>
        <div className="mt-10 flex flex-wrap gap-4 justify-center">
          <button className="group inline-flex items-center gap-2 bg-cyan text-primary-foreground font-mono text-[11px] tracking-[0.25em] font-bold px-6 py-3.5 rounded-sm glow-cyan hover:bg-cyan/90 transition">
            DEMANDER UN ACCÈS DÉMO
            <ArrowRight className="size-3.5 group-hover:translate-x-1 transition" />
          </button>
          <button className="inline-flex items-center gap-2 border border-cyan/50 text-cyan font-mono text-[11px] tracking-[0.25em] font-bold px-6 py-3.5 rounded-sm hover:bg-cyan/10 transition">
            CONSULTER LES TARIFS
          </button>
        </div>
      </div>
    </section>
  );
}
