import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { API_DOCS_URL } from "@/lib/api";
import { monthLong, monthShort, ofMonth, percent, risk } from "@/lib/format";
import { useTitle } from "@/lib/hooks";
import { useMonitoring } from "@/lib/monitoring";
import { STATUS_META, type Site } from "@/lib/sites";
import { AppHeader, BrandMark, LoadState } from "@/ui/chrome";
import { FillGauge } from "@/ui/FillGauge";
import { StatusGlyph } from "@/ui/Status";

const STEPS = [
  {
    title: "Mesurer",
    body: "Chaque mois, les images du satellite Sentinel-2 donnent la surface en eau de chaque retenue, à 10 mètres près. Quand les nuages masquent le sol, le radar Sentinel-1 prend le relais.",
  },
  {
    title: "Prévoir",
    body: "Un modèle entraîné sur l'historique depuis 2019, les pluies et le climat estime le remplissage à un, deux et trois mois. Il donne une fourchette et un risque chiffré, pas une certitude.",
  },
  {
    title: "Agir",
    body: "Le bulletin classe les retenues de la plus menacée à la plus sûre. Chaque fiche propose l'itinéraire pour s'y rendre et un conseil rédigé pour celui qui doit décider.",
  },
];

const LIMITS = [
  {
    title: "Une surface, pas un volume",
    body: "Le satellite voit l'étendue de l'eau, pas sa profondeur. Le volume affiché est une estimation, et la qualité de l'eau n'est pas mesurée.",
  },
  {
    title: "Des retenues à confirmer",
    body: "Une partie de l'inventaire vient d'une détection automatique. Tant qu'un gestionnaire ne l'a pas confirmée, la fiche le signale.",
  },
  {
    title: "Une zone précise",
    body: "Le suivi couvre un rayon de 50 km autour de Ouagadougou : Kadiogo, Oubritenga, Bazèga, Kourwéogo et leurs abords.",
  },
];

function TopRisks() {
  const { phase, sites, issueMonth, criticalFill } = useMonitoring();
  if (phase !== "ready") return <LoadState />;

  const followed = sites.filter((site) => site.forecast.length > 0);
  if (followed.length === 0 || !issueMonth) {
    return (
      <p className="text-[16px] text-ink-2">
        Le bulletin du mois n'est pas encore publié. L'inventaire des plans d'eau reste consultable sur la carte.
      </p>
    );
  }
  const top = followed.slice(0, 5);
  const horizon = top[0].forecast.at(-1)?.month;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-[20px] text-ink">Les plus menacées, bulletin {ofMonth(issueMonth)}</h2>
      </div>
      <ul className="mt-3 divide-y">
        {top.map((site) => <RiskRow key={site.key} site={site} critical={criticalFill} />)}
      </ul>
      <p className="mt-3 text-[14px] text-ink-3">
        Remplissage mesuré en {monthLong(issueMonth)}
        {horizon ? ` ; risque de passer sous le seuil critique d'ici ${monthLong(horizon)}.` : "."}
      </p>
      <Link
        to="/bulletin"
        className="mt-4 inline-flex items-center gap-1.5 text-[16px] font-semibold text-water no-underline hover:underline"
      >
        Voir les {followed.length} retenues <ArrowRight size={17} aria-hidden="true" />
      </Link>
    </div>
  );
}

function RiskRow({ site, critical }: { site: Site; critical: number }) {
  const last = site.forecast.at(-1);
  return (
    <li>
      <Link
        to={`/carte?retenue=${encodeURIComponent(site.key)}`}
        className="group -mx-2 grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-1.5 rounded-lg px-2 py-3 text-ink no-underline hover:bg-sunken"
      >
        <span className="flex min-w-0 items-baseline gap-2">
          <StatusGlyph status={site.status} size={11} />
          <span className="truncate text-[16px] font-semibold group-hover:underline">{site.name}</span>
          {site.zone && <span className="shrink-0 text-[14px] text-ink-2">{site.zone}</span>}
        </span>
        <span
          className="num text-right text-[15px]"
          style={{ color: (site.pCriticalMax ?? 0) >= 0.5 ? STATUS_META["à risque"].ink : undefined }}
        >
          <span className="font-bold">{risk(site.pCriticalMax)}</span> de risque
        </span>
        <span className="flex items-center gap-2.5">
          <span className="flex-1"><FillGauge fill={site.fillNow} status={site.status} critical={critical} size="sm" /></span>
          <span className="num w-11 text-right text-[14px] font-semibold">{percent(site.fillNow)}</span>
        </span>
        <span className="num text-right text-[14px] text-ink-2">
          {last ? `${percent(last.fill)} prévu en ${monthShort(last.month, false)}` : ""}
        </span>
      </Link>
    </li>
  );
}

export default function LandingPage() {
  const { sites } = useMonitoring();
  useTitle("");
  const followed = sites.filter((site) => site.forecast.length > 0).length;

  return (
    <div className="min-h-dvh bg-canvas">
      <a href="#contenu" className="skip-link">Aller au contenu</a>
      <AppHeader />

      <main id="contenu">
        <section className="border-b bg-surface">
          <div className="mx-auto grid max-w-[1180px] gap-x-14 gap-y-10 px-4 py-12 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:py-20">
            <div className="self-center">
              <h1 className="text-[38px] text-ink sm:text-[52px]" style={{ fontStretch: "80%", fontWeight: 700, lineHeight: 1.04 }}>
                Savoir, trois mois à l'avance, quelles retenues vont manquer d'eau.
              </h1>
              <p className="mt-6 max-w-[34rem] text-[19px] leading-relaxed text-ink-2">
                WaterTracker mesure chaque mois par satellite la surface en eau
                {followed > 0 ? ` de ${followed} retenues` : " des retenues"} autour de Ouagadougou et prévoit leur
                remplissage. Le bulletin est en accès libre.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  to="/carte"
                  className="inline-flex h-12 items-center gap-2 rounded-lg bg-water px-5 text-[17px] font-semibold text-white no-underline hover:bg-water-deep"
                >
                  Ouvrir la carte
                </Link>
                <Link
                  to="/bulletin"
                  className="inline-flex h-12 items-center gap-2 rounded-lg border border-line-strong bg-surface px-5 text-[17px] font-semibold text-ink no-underline hover:bg-sunken"
                >
                  Lire le bulletin
                </Link>
              </div>
            </div>

            <div className="rounded-2xl border bg-surface p-5 shadow-panel sm:p-6">
              <TopRisks />
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-[1180px] px-4 py-14 sm:px-6 lg:py-20">
          <h2 className="max-w-[30rem] text-[30px] text-ink sm:text-[36px]">De l'image satellite à la décision</h2>
          <ol className="mt-10 grid gap-x-10 gap-y-8 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li key={step.title} className="border-t-2 border-ink pt-4">
                <p className="num text-[15px] font-semibold text-ink-2">Étape {index + 1}</p>
                <h3 className="mt-1 text-[24px] text-ink">{step.title}</h3>
                <p className="mt-3 text-[17px] leading-relaxed text-ink-2">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className="border-y bg-surface">
          <div className="mx-auto grid max-w-[1180px] gap-x-14 gap-y-8 px-4 py-14 sm:px-6 lg:grid-cols-[0.8fr_1.2fr] lg:py-20">
            <div>
              <h2 className="text-[30px] text-ink sm:text-[36px]">Ce que l'outil ne dit pas</h2>
              <p className="mt-4 max-w-[26rem] text-[17px] leading-relaxed text-ink-2">
                Une prévision aide à décider, elle ne remplace pas une visite sur place. Voici ses limites, pour
                l'utiliser à bon escient.
              </p>
            </div>
            <dl className="space-y-6">
              {LIMITS.map((limit) => (
                <div key={limit.title}>
                  <dt className="text-[19px] font-semibold text-ink">{limit.title}</dt>
                  <dd className="mt-1.5 max-w-[38rem] text-[17px] leading-relaxed text-ink-2">{limit.body}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      </main>

      <footer className="mx-auto max-w-[1180px] px-4 py-10 sm:px-6">
        <div className="flex flex-wrap items-start justify-between gap-x-12 gap-y-6">
          <div className="flex items-center gap-2 text-ink">
            <BrandMark size={22} />
            <span className="font-bold" style={{ fontStretch: "88%" }}>WaterTracker</span>
          </div>
          <p className="max-w-[40rem] text-[14px] leading-relaxed text-ink-2">
            Données : images Sentinel-1 et Sentinel-2 du programme Copernicus, pluies CHIRPS, climat ERA5-Land,
            catalogue JRC Global Surface Water, fond de carte et contours © contributeurs OpenStreetMap.
          </p>
          <nav aria-label="Liens utiles" className="flex flex-col gap-1.5 text-[15px]">
            <Link to="/carte" className="text-water no-underline hover:underline">Carte</Link>
            <Link to="/bulletin" className="text-water no-underline hover:underline">Bulletin</Link>
            <a href={API_DOCS_URL} target="_blank" rel="noreferrer" className="text-water no-underline hover:underline">
              Documentation de l'API
            </a>
          </nav>
        </div>
      </footer>
    </div>
  );
}
