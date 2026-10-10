import { useEffect, useState, type ReactNode } from "react";
import { ArrowLeft, Check, Link2, Navigation } from "lucide-react";
import { fetchHistory, isAbort, type ApiHistoryPoint } from "@/lib/api";
import { coordinates, hectares, monthLong, monthShort, ofMonth, percent, risk, signedPoints, volume } from "@/lib/format";
import { useMonitoring } from "@/lib/monitoring";
import { STATUS_META, firstCriticalMonth, type Site } from "@/lib/sites";
import { Notice } from "@/ui/chrome";
import { ForecastChart, HistoryChart } from "@/ui/charts";
import { FillGauge } from "@/ui/FillGauge";
import { StatusBadge } from "@/ui/Status";
import { AdvicePanel } from "./AdvicePanel";

/** La conclusion en une phrase, avant tout chiffre. */
function verdict(site: Site): string {
  if (site.forecast.length === 0) {
    return "Ce point d'eau figure à l'inventaire mais n'est pas encore suivi chaque mois : aucune prévision n'est disponible.";
  }
  const critical = firstCriticalMonth(site);
  const worst = site.forecast.reduce((a, b) => (b.pCritical > a.pCritical ? b : a));
  if (site.status === "tari") {
    return `La retenue devrait être presque à sec dès ${monthLong(site.forecast[0].month)}.`;
  }
  if (critical) {
    const lead = site.status === "à risque" ? "" : "Pas d'alerte le mois prochain, mais ";
    const sentence = `${risk(critical.pCritical)} de risque de passer sous le seuil critique en ${monthLong(critical.month)}.`;
    return lead ? `${lead}${sentence}` : sentence;
  }
  if (worst.pCritical >= 0.2) {
    return `Pas d'alerte, mais un risque à surveiller : ${risk(worst.pCritical)} en ${monthLong(worst.month)}.`;
  }
  return "Aucune alerte prévue pour les trois prochains mois.";
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t px-4 py-5">
      <h3 className="text-[18px] text-ink">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

export function SiteDetail({ site, onBack, onRoute }: { site: Site; onBack: () => void; onRoute: () => void }) {
  const { issueMonth, criticalFill, bulletin } = useMonitoring();
  const [history, setHistory] = useState<ApiHistoryPoint[] | null>(null);
  const [historyError, setHistoryError] = useState(false);
  const [copied, setCopied] = useState<"done" | "failed" | null>(null);
  const meta = STATUS_META[site.status];

  useEffect(() => {
    setHistory(null);
    setHistoryError(false);
    if (!site.reservoirId) return;
    const controller = new AbortController();
    fetchHistory(site.reservoirId, controller.signal)
      .then((payload) => setHistory(payload.points))
      .catch((err: unknown) => { if (!isAbort(err)) setHistoryError(true); });
    return () => controller.abort();
  }, [site.reservoirId]);

  useEffect(() => setCopied(null), [site.key]);

  const copyLink = async () => {
    const url = window.location.href;
    let done = false;
    try {
      await navigator.clipboard.writeText(url);
      done = true;
    } catch {
      // Presse-papiers moderne indisponible (page servie sans https) : ancienne méthode.
      const field = document.createElement("textarea");
      field.value = url;
      field.setAttribute("readonly", "");
      field.style.position = "fixed";
      field.style.opacity = "0";
      document.body.appendChild(field);
      field.select();
      try { done = document.execCommand("copy"); } catch { done = false; }
      field.remove();
    }
    setCopied(done ? "done" : "failed");
    setTimeout(() => setCopied(null), 3000);
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
      <div className="px-4 pb-5 pt-2">
        <button
          type="button" onClick={onBack}
          className="-ml-2 inline-flex h-10 items-center gap-1.5 rounded-md px-2 text-[15px] font-semibold text-water hover:bg-water-soft"
        >
          <ArrowLeft size={17} aria-hidden="true" /> Toutes les retenues
        </button>

        <div className="mt-1 flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
          <div className="min-w-0">
            <h2 className="text-[26px] text-ink">{site.name}</h2>
            <p className="mt-1 text-[15px] text-ink-2">
              {[site.zone, site.reservoirId && site.name !== `Retenue ${site.reservoirId}` ? `réf. ${site.reservoirId}` : null]
                .filter(Boolean).join(", ") || (site.toValidate ? "Repérée par satellite" : "Province non renseignée")}
            </p>
          </div>
          <StatusBadge status={site.status} />
        </div>

        <p className="mt-4 text-[17px] font-semibold leading-snug" style={{ color: site.status === "actif" ? undefined : meta.ink }}>
          {verdict(site)}
        </p>

        {site.fillNow !== null && issueMonth && (
          <div className="mt-5">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[15px] text-ink-2">Remplissage en {monthLong(issueMonth)}</p>
              <p className="num text-[34px] font-bold leading-none text-ink">{percent(site.fillNow)}</p>
            </div>
            <div className="mt-2.5">
              <FillGauge fill={site.fillNow} status={site.status} critical={criticalFill} size="lg" showThresholdLabel />
            </div>
            <p className="num mt-2 text-[15px] text-ink-2">
              {hectares(site.areaHa)} en eau sur {hectares(site.refAreaHa)} de référence
              {site.fillChange !== null && ` (${signedPoints(site.fillChange)} en un mois)`}
            </p>
            {site.fillNow > 1.05 && (
              <p className="mt-1 text-[14px] text-ink-3">
                Au-dessus de 100 % : l'eau s'étend au-delà de la surface de référence (crue ou zone inondée).
              </p>
            )}
          </div>
        )}

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button" onClick={onRoute}
            className="inline-flex h-11 items-center gap-2 rounded-lg bg-water px-4 text-[15px] font-semibold text-white hover:bg-water-deep"
          >
            <Navigation size={17} aria-hidden="true" /> Itinéraire
          </button>
          <button
            type="button" onClick={copyLink}
            className="inline-flex h-11 items-center gap-2 rounded-lg border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink hover:bg-sunken"
          >
            {copied === "done" ? <Check size={17} aria-hidden="true" /> : <Link2 size={17} aria-hidden="true" />}
            <span aria-live="polite">
              {copied === "done" ? "Lien copié" : copied === "failed" ? "Copiez l'adresse de la page" : "Copier le lien"}
            </span>
          </button>
        </div>

        {site.toValidate && (
          <div className="mt-4">
            <Notice>
              Plan d'eau repéré automatiquement sur les images satellite, pas encore confirmé sur le terrain
              par un gestionnaire.
            </Notice>
          </div>
        )}
      </div>

      {site.forecast.length > 0 && issueMonth && (
        <Section title="Prévision à trois mois">
          <ul className="mb-1 flex flex-wrap gap-x-5 gap-y-1 text-[14px] text-ink-2">
            <li className="flex items-center gap-2">
              <span className="inline-block h-3 w-5 rounded-sm bg-water/15" aria-hidden="true" /> Fourchette probable
            </li>
            <li className="flex items-center gap-2">
              <span className="inline-block w-5 border-t-2 border-dashed border-ink" aria-hidden="true" /> Seuil critique
            </li>
          </ul>
          <ForecastChart issueMonth={issueMonth} fillNow={site.fillNow} forecast={site.forecast} critical={criticalFill} />
          <table className="mt-3 w-full text-[15px]">
            <thead>
              <tr className="text-left text-[13px] text-ink-2">
                <th className="py-1.5 font-semibold">Mois</th>
                <th className="py-1.5 text-right font-semibold">Remplissage prévu</th>
                <th className="py-1.5 text-right font-semibold">Fourchette</th>
                <th className="py-1.5 text-right font-semibold">Risque</th>
              </tr>
            </thead>
            <tbody>
              {site.forecast.map((point) => (
                <tr key={point.horizon} className="border-t">
                  <td className="py-2 text-ink">{monthShort(point.month)}</td>
                  <td className="num py-2 text-right font-semibold text-ink">{percent(point.fill)}</td>
                  <td className="num py-2 text-right text-ink-2">
                    {Math.round(point.low * 100)} à {percent(point.high)}
                  </td>
                  <td
                    className="num py-2 text-right font-semibold"
                    style={{ color: point.pCritical >= 0.5 ? STATUS_META["à risque"].ink : undefined }}
                  >
                    {risk(point.pCritical)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-[14px] text-ink-3">
            Fourchette : 8 fois sur 10, la valeur réelle tombe dedans. Risque : probabilité de passer sous le
            seuil critique de {percent(criticalFill)}. Prévision établie avec les mesures {ofMonth(issueMonth)}.
          </p>
        </Section>
      )}

      {site.reservoirId && (
        <Section title="Depuis 2019, mois par mois">
          {historyError && (
            <p className="text-[15px] text-ink-2">L'historique n'a pas pu être chargé. Rouvrez la fiche pour réessayer.</p>
          )}
          {!historyError && history === null && <div className="skeleton h-[200px] w-full" role="status" aria-label="Chargement de l'historique" />}
          {history && <HistoryChart points={history} critical={criticalFill} />}
          {history && history.length > 1 && (
            <p className="mt-2 text-[14px] text-ink-3">
              Surface en eau mesurée par satellite (Sentinel-2, 10 m), rapportée à la surface de référence.
              Le trait pointillé marque le seuil critique.
            </p>
          )}
        </Section>
      )}

      {site.sourceIds.length > 0 && (
        <Section title="Conseil pour agir">
          <AdvicePanel sourceId={site.sourceIds[0]} />
        </Section>
      )}

      <Section title="Repères">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-[15px]">
          <dt className="text-ink-2">Coordonnées</dt>
          <dd className="num text-ink">{coordinates(site.lat, site.lng)}</dd>
          {site.reservoirId && (<><dt className="text-ink-2">Référence</dt><dd className="num text-ink">{site.reservoirId}</dd></>)}
          {site.volumeM3 !== null && site.volumeM3 > 0 && (
            <><dt className="text-ink-2">Volume estimé</dt><dd className="num text-ink">{volume(site.volumeM3)}</dd></>
          )}
          {site.refAreaHa === null && site.areaHa !== null && (
            <><dt className="text-ink-2">Surface cartographiée</dt><dd className="num text-ink">{hectares(site.areaHa)}</dd></>
          )}
          <dt className="text-ink-2">Inventaire</dt>
          <dd className="text-ink">
            {site.origin === "JRC"
              ? "Détecté par satellite (catalogue JRC), à confirmer"
              : site.sourceIds.length > 1
                ? `${site.sourceIds.length} plans d'eau recensés, regroupés en une retenue`
                : "Recensé et validé"}
          </dd>
          {bulletin?.model_version && site.forecast.length > 0 && (
            <><dt className="text-ink-2">Modèle</dt><dd className="num text-ink">version {bulletin.model_version.split(" ")[0]}</dd></>
          )}
        </dl>
      </Section>
    </div>
  );
}
