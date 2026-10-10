import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Download, Printer, Search } from "lucide-react";
import { BULLETIN_CSV_URL, fetchReport, isAbort, type ApiReport } from "@/lib/api";
import { hectares, monthLong, monthShort, monthsSince, ofMonth, percent, plural, risk, signedPoints } from "@/lib/format";
import { useTitle } from "@/lib/hooks";
import { useMonitoring } from "@/lib/monitoring";
import { STATUS_META, STATUS_ORDER, countByStatus, matchesQuery, type Site, type Status } from "@/lib/sites";
import { AppHeader, LoadState, Notice } from "@/ui/chrome";
import { NdwiBars } from "@/ui/charts";
import { FillGauge } from "@/ui/FillGauge";
import { StatusBadge, StatusGlyph } from "@/ui/Status";

export default function BulletinPage() {
  const { phase, sites, issueMonth, criticalFill, bulletin } = useMonitoring();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status | "">("");
  const [report, setReport] = useState<ApiReport | null>(null);
  useTitle(issueMonth ? `Bulletin ${ofMonth(issueMonth)}` : "Bulletin");

  useEffect(() => {
    const controller = new AbortController();
    // Section secondaire : si elle échoue, le bulletin reste lisible sans elle.
    fetchReport(controller.signal).then(setReport).catch((err: unknown) => { if (!isAbort(err)) setReport(null); });
    return () => controller.abort();
  }, []);

  const followed = useMemo(() => sites.filter((s) => s.forecast.length > 0), [sites]);
  const unfollowed = sites.length - followed.length;
  const counts = useMemo(() => countByStatus(followed), [followed]);
  const rows = useMemo(
    () => followed.filter((s) => matchesQuery(s, query) && (status === "" || s.status === status)),
    [followed, query, status],
  );
  const months = followed[0]?.forecast.map((f) => f.month) ?? [];
  const later = followed.filter((s) => s.status === "actif" && (s.pCriticalMax ?? 0) >= 0.5).length;
  const toValidate = followed.filter((s) => s.toValidate).length;

  return (
    <div className="min-h-dvh bg-canvas">
      <a href="#contenu" className="skip-link">Aller au contenu</a>
      <AppHeader />

      <main id="contenu" className="mx-auto max-w-[1180px] px-4 pb-16 pt-8 sm:px-6">
        {phase !== "ready" && <LoadState />}

        {phase === "ready" && (!bulletin || !issueMonth) && (
          <Notice tone="warn">
            Aucun bulletin n'a encore été publié : les prévisions mensuelles ne sont pas chargées sur le serveur.
            L'inventaire reste consultable sur la <Link to="/carte" className="font-semibold text-water">carte</Link>.
          </Notice>
        )}

        {phase === "ready" && bulletin && issueMonth && (
          <>
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="max-w-[46rem]">
                <h1 className="text-[34px] text-ink sm:text-[40px]">Bulletin {ofMonth(issueMonth)}</h1>
                <p className="mt-3 text-[18px] leading-snug text-ink-2">
                  État de {plural(followed.length, "retenue")} autour de Ouagadougou, mesuré par satellite en{" "}
                  {monthLong(issueMonth)}, et prévision de leur remplissage jusqu'en {months.length > 0 ? monthLong(months[months.length - 1]) : "fin de période"}.
                </p>
              </div>
              <div className="no-print flex flex-wrap gap-2">
                <a
                  href={BULLETIN_CSV_URL}
                  className="inline-flex h-11 items-center gap-2 rounded-lg bg-water px-4 text-[15px] font-semibold text-white no-underline hover:bg-water-deep"
                >
                  <Download size={17} aria-hidden="true" /> Télécharger (CSV)
                </a>
                <button
                  type="button" onClick={() => window.print()}
                  className="inline-flex h-11 items-center gap-2 rounded-lg border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink hover:bg-sunken"
                >
                  <Printer size={17} aria-hidden="true" /> Imprimer
                </button>
              </div>
            </div>

            {monthsSince(issueMonth) >= 2 && (
              <div className="mt-6">
                <Notice tone="warn">
                  Ce bulletin est le dernier publié. Les mesures des mois suivants ne sont pas encore
                  disponibles : une partie de la période de prévision est déjà écoulée.
                </Notice>
              </div>
            )}

            <dl className="mt-7 grid grid-cols-2 gap-px overflow-hidden rounded-xl border bg-line sm:grid-cols-4">
              {STATUS_ORDER.filter((s) => s !== "inconnu").map((s) => (
                <div key={s} className="bg-surface p-4">
                  <dt className="flex items-center gap-1.5 text-[14px] text-ink-2">
                    <StatusGlyph status={s} size={10} /> {STATUS_META[s].label}
                  </dt>
                  <dd className="num mt-1 text-[32px] font-bold leading-none text-ink">{counts[s]}</dd>
                  <dd className="mt-1.5 text-[13px] leading-snug text-ink-3">{STATUS_META[s].hint}</dd>
                </div>
              ))}
              <div className="bg-surface p-4">
                <dt className="text-[14px] text-ink-2">À surveiller ensuite</dt>
                <dd className="num mt-1 text-[32px] font-bold leading-none text-ink">{later}</dd>
                <dd className="mt-1.5 text-[13px] leading-snug text-ink-3">
                  Sans alerte le mois prochain, mais risque supérieur à 50 % dans les trois mois
                </dd>
              </div>
            </dl>

            <div className="no-print mt-8 flex flex-wrap items-center gap-2">
              <label className="relative block w-full sm:w-80">
                <span className="sr-only">Chercher une retenue</span>
                <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden="true" />
                <input
                  type="search" value={query} onChange={(event) => setQuery(event.target.value)}
                  placeholder="Nom, numéro ou province"
                  className="h-11 w-full rounded-lg border border-line-strong bg-surface pl-10 pr-3 text-[16px] text-ink placeholder:text-ink-3"
                />
              </label>
              <label className="block">
                <span className="sr-only">État</span>
                <select
                  value={status} onChange={(event) => setStatus(event.target.value as Status | "")}
                  className="h-11 rounded-lg border border-line-strong bg-surface px-3 text-[16px] text-ink"
                >
                  <option value="">Tous les états</option>
                  {STATUS_ORDER.filter((s) => counts[s] > 0).map((s) => <option key={s} value={s}>{STATUS_META[s].label}</option>)}
                </select>
              </label>
              <p className="ml-auto text-[14px] text-ink-2" aria-live="polite">
                {plural(rows.length, "retenue")}, les plus menacées d'abord
              </p>
            </div>

            {rows.length === 0 ? (
              <p className="mt-6 text-[16px] text-ink-2">Aucune retenue ne correspond à cette recherche.</p>
            ) : (
              <>
                {/* Tableau sur grand écran et à l'impression */}
                <div className="print-plain mt-4 hidden overflow-hidden rounded-xl border bg-surface md:block print:block">
                  <table className="w-full text-[15px]">
                    <thead>
                      <tr className="border-b bg-sunken text-left text-[13px] text-ink-2">
                        <th scope="col" className="px-4 py-2.5 font-semibold">Retenue</th>
                        <th scope="col" className="px-3 py-2.5 font-semibold">État</th>
                        <th scope="col" className="w-[210px] px-3 py-2.5 font-semibold">Remplissage en {monthShort(issueMonth, false)}</th>
                        <th scope="col" className="px-3 py-2.5 text-right font-semibold">En un mois</th>
                        {months.map((month) => (
                          <th key={month} scope="col" className="px-3 py-2.5 text-right font-semibold">Prévu {monthShort(month, false)}</th>
                        ))}
                        <th scope="col" className="px-4 py-2.5 text-right font-semibold">Risque max.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((site) => <TableRow key={site.key} site={site} critical={criticalFill} />)}
                    </tbody>
                  </table>
                </div>

                {/* Fiches sur téléphone */}
                <ul className="mt-4 space-y-2 md:hidden print:hidden">
                  {rows.map((site) => <Card key={site.key} site={site} critical={criticalFill} />)}
                </ul>
              </>
            )}

            <section className="mt-12 grid gap-x-12 gap-y-8 lg:grid-cols-2">
              <div>
                <h2 className="text-[24px] text-ink">Lire ce bulletin</h2>
                <dl className="mt-4 space-y-4 text-[16px] leading-relaxed">
                  <div>
                    <dt className="font-semibold text-ink">Remplissage</dt>
                    <dd className="text-ink-2">
                      Surface en eau du mois, rapportée à la surface de référence de la retenue. Ce n'est pas un
                      volume : une retenue peu profonde peut afficher 60 % et contenir peu d'eau.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-ink">Seuil critique</dt>
                    <dd className="text-ink-2">
                      Fixé à {percent(criticalFill)} de la surface de référence. En dessous, les usages
                      (maraîchage, abreuvement) deviennent difficiles.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-ink">Risque</dt>
                    <dd className="text-ink-2">
                      Probabilité de passer sous le seuil critique. « Risque max. » retient le pire des trois
                      mois à venir. Une retenue est classée « à risque » dès que cette probabilité dépasse 50 %
                      pour le mois prochain.
                    </dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-ink">Limites</dt>
                    <dd className="text-ink-2">
                      {toValidate > 0 && `${toValidate} des ${followed.length} retenues ont été repérées automatiquement et n'ont pas encore été confirmées sur le terrain. `}
                      {unfollowed > 0 && `${plural(unfollowed, "point")} d'eau de l'inventaire ${unfollowed > 1 ? "ne sont pas suivis" : "n'est pas suivi"} chaque mois et ${unfollowed > 1 ? "n'apparaissent" : "n'apparaît"} pas ici. `}
                      Les mois très nuageux sont estimés à partir des mois voisins.
                    </dd>
                  </div>
                </dl>
              </div>

              {report && report.periodes.length > 1 && (
                <div>
                  <h2 className="text-[24px] text-ink">Tendance par semestre, {report.periodes[0].periode.slice(0, 4)}–{report.periodes.at(-1)!.periode.slice(0, 4)}</h2>
                  <p className="mt-3 text-[16px] leading-relaxed text-ink-2">
                    Indice d'eau moyen (NDWI) des plans d'eau recensés : plus il est élevé, plus l'eau est présente.
                    Le second semestre, après la saison des pluies, est en bleu plein.
                  </p>
                  <div className="mt-4 rounded-xl border bg-surface p-4">
                    <NdwiBars periods={report.periodes} />
                  </div>
                  <p className="mt-2 text-[14px] text-ink-3">
                    Série issue de l'ancienne analyse semestrielle ({report.nb_observations.toLocaleString("fr-FR")} observations),
                    arrêtée à {report.periode}. Elle n'entre pas dans la prévision mensuelle.
                  </p>
                </div>
              )}
            </section>

            <p className="mt-10 border-t pt-4 text-[14px] text-ink-3">
              Modèle de prévision version {bulletin.model_version?.split(" ")[0] ?? "non renseignée"}. Mesures Sentinel-2 (programme Copernicus),
              pluies CHIRPS, climat ERA5-Land.
            </p>
          </>
        )}
      </main>
    </div>
  );
}

function placeLine(site: Site): string {
  if (site.zone) return site.toValidate ? `${site.zone}, à confirmer` : site.zone;
  return site.toValidate ? "Repérée par satellite, à confirmer" : "Province non renseignée";
}

function riskStyle(p: number | null) {
  return p !== null && p >= 0.5 ? { color: STATUS_META["à risque"].ink, fontWeight: 650 } : undefined;
}

function TableRow({ site, critical }: { site: Site; critical: number }) {
  return (
    <tr className="border-b last:border-b-0 hover:bg-sunken/60">
      <th scope="row" className="px-4 py-3 text-left font-normal">
        <Link to={`/carte?retenue=${encodeURIComponent(site.key)}`} className="font-semibold text-water no-underline hover:underline">
          {site.name}
        </Link>
        <span className="block text-[13px] text-ink-2">
          {placeLine(site)}
        </span>
      </th>
      <td className="px-3 py-3"><StatusBadge status={site.status} /></td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-2.5">
          <div className="flex-1"><FillGauge fill={site.fillNow} status={site.status} critical={critical} size="sm" /></div>
          <span className="num w-12 text-right font-semibold text-ink">{percent(site.fillNow)}</span>
        </div>
      </td>
      <td className="num px-3 py-3 text-right text-ink-2">{signedPoints(site.fillChange)}</td>
      {site.forecast.map((point) => (
        <td key={point.horizon} className="num px-3 py-3 text-right text-ink">{percent(point.fill)}</td>
      ))}
      <td className="num px-4 py-3 text-right" style={riskStyle(site.pCriticalMax)}>{risk(site.pCriticalMax)}</td>
    </tr>
  );
}

function Card({ site, critical }: { site: Site; critical: number }) {
  return (
    <li>
      <Link
        to={`/carte?retenue=${encodeURIComponent(site.key)}`}
        className="block rounded-xl border bg-surface p-4 text-ink no-underline"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate text-[17px] font-semibold">{site.name}</p>
            <p className="text-[14px] text-ink-2">{placeLine(site)}, {hectares(site.areaHa)} en eau</p>
          </div>
          <StatusBadge status={site.status} />
        </div>
        <div className="mt-3 flex items-center gap-2.5">
          <div className="flex-1"><FillGauge fill={site.fillNow} status={site.status} critical={critical} /></div>
          <span className="num w-12 text-right text-[16px] font-semibold">{percent(site.fillNow)}</span>
        </div>
        <p className="num mt-2.5 text-[14px] text-ink-2">
          Prévu : {site.forecast.map((point) => `${percent(point.fill)} en ${monthShort(point.month, false)}`).join(", ")}
        </p>
        <p className="num mt-0.5 text-[14px] text-ink-2">
          Risque maximal : <span style={riskStyle(site.pCriticalMax)}>{risk(site.pCriticalMax)}</span>
        </p>
      </Link>
    </li>
  );
}
