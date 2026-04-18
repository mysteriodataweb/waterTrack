import MapShell from "./components/map-shell";

const statusLegend = [
  { label: "Actif", color: "var(--active)" },
  { label: "A risque", color: "var(--risk)" },
  { label: "Tari", color: "var(--dry)" },
];

export default function Home() {
  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(29,111,214,0.18),_transparent_34%),linear-gradient(180deg,_#edf6f4_0%,_#f7efe0_100%)] px-5 py-6 sm:px-8 lg:px-12">
      <section className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <div className="overflow-hidden rounded-[32px] border border-[var(--line)] bg-[rgba(253,252,247,0.86)] shadow-[0_24px_80px_rgba(16,42,67,0.12)] backdrop-blur">
          <div className="grid gap-8 p-6 sm:p-8 lg:grid-cols-[1.05fr_0.95fr] lg:p-10">
            <div className="flex flex-col gap-6">
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--foreground)] text-lg font-semibold text-white">
                  WT
                </div>
                <div>
                  <p className="text-sm font-medium uppercase tracking-[0.26em] text-[var(--muted)]">
                    Burkina Faso
                  </p>
                  <h1 className="text-3xl font-semibold tracking-[-0.04em] sm:text-5xl">
                    Cartographier l&apos;eau de surface avant qu&apos;elle ne disparaisse.
                  </h1>
                </div>
              </div>

              <p className="max-w-2xl text-base leading-7 text-[var(--muted)] sm:text-lg">
                WaterTracker combine imagerie Sentinel-2, intelligence artificielle
                et capteurs IoT pour localiser les sources d&apos;eau, estimer leur
                risque et orienter les interventions terrain.
              </p>

              <div className="grid gap-4 sm:grid-cols-3">
                <article className="rounded-[24px] border border-[var(--line)] bg-[var(--surface)] p-4">
                  <p className="text-sm text-[var(--muted)]">Sources detectees</p>
                  <p className="mt-2 text-3xl font-semibold">278</p>
                </article>
                <article className="rounded-[24px] border border-[var(--line)] bg-[var(--surface)] p-4">
                  <p className="text-sm text-[var(--muted)]">Zone pilote</p>
                  <p className="mt-2 text-3xl font-semibold">Ouaga</p>
                </article>
                <article className="rounded-[24px] border border-[var(--line)] bg-[var(--surface)] p-4">
                  <p className="text-sm text-[var(--muted)]">Flux de donnees</p>
                  <p className="mt-2 text-3xl font-semibold">API live</p>
                </article>
              </div>
            </div>

            <div className="flex flex-col gap-4 rounded-[28px] border border-[var(--line)] bg-[linear-gradient(180deg,_rgba(214,235,228,0.85),_rgba(253,252,247,0.95))] p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                    Legende terrain
                  </p>
                  <p className="mt-1 text-lg font-semibold">Etat des sources</p>
                </div>
                <div className="rounded-full border border-[var(--line)] bg-white/70 px-3 py-1 text-xs text-[var(--muted)]">
                  Leaflet + FastAPI
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-1">
                {statusLegend.map((item) => (
                  <div
                    key={item.label}
                    className="flex items-center gap-3 rounded-2xl border border-[var(--line)] bg-[var(--surface)] px-4 py-3"
                  >
                    <span
                      className="h-3.5 w-3.5 rounded-full"
                      style={{ backgroundColor: item.color }}
                    />
                    <span className="text-sm font-medium">{item.label}</span>
                  </div>
                ))}
              </div>

              <p className="text-sm leading-6 text-[var(--muted)]">
                Cliquez sur une zone de la carte pour afficher son identifiant,
                son statut, son NDWI moyen, son score de risque et sa date
                d&apos;analyse.
              </p>
            </div>
          </div>
        </div>

        <section className="overflow-hidden rounded-[32px] border border-[var(--line)] bg-[rgba(253,252,247,0.9)] shadow-[0_24px_70px_rgba(16,42,67,0.08)]">
          <div className="flex flex-col gap-3 border-b border-[var(--line)] px-6 py-5 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[var(--muted)]">
                Carte interactive
              </p>
              <h2 className="mt-1 text-2xl font-semibold tracking-[-0.03em]">
                Sources d&apos;eau de surface detectees par satellite
              </h2>
            </div>
            <p className="max-w-xl text-sm leading-6 text-[var(--muted)]">
              Les polygones sont recuperes depuis l&apos;API FastAPI et styles selon
              leur statut pour faciliter le suivi des priorites.
            </p>
          </div>
          <div className="p-4 sm:p-6">
            <MapShell />
          </div>
        </section>
      </section>
    </main>
  );
}
