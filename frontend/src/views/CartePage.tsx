import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronUp, LoaderCircle, LocateFixed } from "lucide-react";
import { MapCanvas, panMapTo, type MapRoute } from "@/carte/MapCanvas";
import { RoutePanel } from "@/carte/RoutePanel";
import { SiteDetail } from "@/carte/SiteDetail";
import { NO_FILTERS, SiteList, type Filters } from "@/carte/SiteList";
import { monthLong, monthsSince, ofMonth, plural } from "@/lib/format";
import { readCurrentPosition, type Position } from "@/lib/geo";
import { useMediaQuery, useTitle } from "@/lib/hooks";
import { useMonitoring } from "@/lib/monitoring";
import { STATUS_META, STATUS_ORDER, countByStatus, matchesQuery, type Site } from "@/lib/sites";
import { AppHeader, LoadState, Notice } from "@/ui/chrome";
import { StatusGlyph } from "@/ui/Status";

const SHEET_PEEK = 104;

/** Ce que dit le bulletin, en une phrase. */
function headline(sites: Site[], issueMonth: string | null): string {
  if (!issueMonth) return `${plural(sites.length, "plan", "plans")} d'eau à l'inventaire`;
  const followed = sites.filter((s) => s.forecast.length > 0);
  const alert = followed.filter((s) => s.status === "à risque" || s.status === "tari").length;
  const later = followed.filter((s) => s.status === "actif" && (s.pCriticalMax ?? 0) >= 0.5);
  const horizon = followed[0]?.forecast.at(-1)?.month;
  const first = alert === 0
    ? `Aucune des ${followed.length} retenues suivies n'est en alerte pour le mois prochain`
    : `${alert} des ${followed.length} retenues suivies ${alert > 1 ? "sont" : "est"} en alerte pour le mois prochain`;
  if (later.length === 0 || !horizon) return `${first}.`;
  return `${first} ; ${later.length} autre${later.length > 1 ? "s pourraient" : " pourrait"} passer sous le seuil critique d'ici ${monthLong(horizon)}.`;
}

export default function CartePage() {
  const { phase, sites, shapes, issueMonth, bulletin } = useMonitoring();
  const [params, setParams] = useSearchParams();
  const selectedKey = params.get("retenue");
  const routing = params.get("vue") === "itineraire";
  const isDesktop = useMediaQuery("(min-width: 1024px)");

  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [route, setRoute] = useState<MapRoute | null>(null);
  const [me, setMe] = useState<Position | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);
  const [viewportHeight, setViewportHeight] = useState(() => window.innerHeight);

  useEffect(() => {
    const update = () => setViewportHeight(window.innerHeight);
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  const selected = useMemo(() => sites.find((s) => s.key === selectedKey) ?? null, [sites, selectedKey]);
  useTitle(selected ? selected.name : "Carte des retenues");

  const visible = useMemo(() => sites.filter((site) =>
    matchesQuery(site, filters.query)
    && (filters.statuses.length === 0 || filters.statuses.includes(site.status))
    && (filters.zone === "" || site.zone === filters.zone)), [sites, filters]);

  // La retenue ouverte reste sur la carte même si un filtre l'exclut.
  const mapSites = useMemo(
    () => (selected && !visible.includes(selected) ? [selected, ...visible] : visible),
    [visible, selected],
  );

  const select = useCallback((key: string | null, view?: "itineraire") => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (key) next.set("retenue", key); else next.delete("retenue");
      if (view) next.set("vue", view); else next.delete("vue");
      return next;
    });
    if (key) setSheetOpen(true);
  }, [setParams]);

  // Une fiche ouverte par un lien partagé doit être visible d'emblée sur mobile.
  useEffect(() => { if (selectedKey) setSheetOpen(true); }, [selectedKey]);
  useEffect(() => { if (!routing) setRoute(null); }, [routing]);

  const locateMe = async () => {
    setLocating(true);
    setLocateError(null);
    try {
      const position = await readCurrentPosition();
      setMe(position);
      panMapTo(position);
    } catch (err) {
      setLocateError(err instanceof Error ? err.message : "Position indisponible.");
    } finally {
      setLocating(false);
    }
  };

  const alertCount = useMemo(() => {
    const counts = countByStatus(sites);
    return counts.tari + counts["à risque"];
  }, [sites]);
  const sheetHeight = sheetOpen ? Math.round(viewportHeight * 0.62) : SHEET_PEEK;
  const missing = phase === "ready" && selectedKey !== null && selected === null;

  const panel = (
    <>
      {phase !== "ready" && <div className="p-4"><LoadState /></div>}

      {missing && (
        <div className="space-y-3 p-4">
          <Notice tone="warn">
            Le plan d'eau « {selectedKey} » n'existe pas dans l'inventaire actuel. Le lien est peut-être ancien.
          </Notice>
          <button
            type="button" onClick={() => select(null)}
            className="inline-flex h-10 items-center rounded-md bg-ink px-4 text-[15px] font-semibold text-white"
          >
            Voir toutes les retenues
          </button>
        </div>
      )}

      {phase === "ready" && selected && routing && (
        <RoutePanel key={selected.key} site={selected} onBack={() => select(selected.key)} onRoute={setRoute} onPosition={setMe} />
      )}
      {phase === "ready" && selected && !routing && (
        <SiteDetail key={selected.key} site={selected} onBack={() => select(null)} onRoute={() => select(selected.key, "itineraire")} />
      )}

      {phase === "ready" && !selectedKey && (
        <>
          <div className="shrink-0 px-4 pt-4 max-lg:hidden">
            <h1 className="text-[22px] text-ink">
              {issueMonth ? `Bulletin ${ofMonth(issueMonth)}` : "Inventaire des plans d'eau"}
            </h1>
            <p className="mt-1.5 text-[15px] leading-snug text-ink-2">{headline(sites, issueMonth)}</p>
          </div>
          {issueMonth && monthsSince(issueMonth) >= 2 && (
            <div className="px-4 pt-3">
              <Notice tone="warn">
                Dernier bulletin publié : {monthLong(issueMonth)}. Les mesures des mois suivants ne sont pas encore disponibles.
              </Notice>
            </div>
          )}
          {!bulletin && (
            <div className="px-4 pt-3">
              <Notice tone="warn">
                Les prévisions mensuelles ne sont pas disponibles pour l'instant. La carte montre l'inventaire seul.
              </Notice>
            </div>
          )}
          <SiteList all={sites} visible={visible} filters={filters} onFilters={setFilters} onSelect={(key) => select(key)} />
        </>
      )}
    </>
  );

  return (
    <div className="flex h-dvh flex-col overflow-hidden bg-canvas">
      <a href="#panneau" className="skip-link">Aller à la liste des retenues</a>
      <AppHeader />

      <div className="relative flex min-h-0 flex-1">
        <aside
          id="panneau"
          aria-label="Retenues"
          className="z-[1000] flex flex-col bg-surface max-lg:absolute max-lg:inset-x-0 max-lg:bottom-0 max-lg:rounded-t-2xl max-lg:shadow-sheet max-lg:transition-[height] max-lg:duration-200 lg:w-[430px] lg:shrink-0 lg:border-r"
          style={isDesktop ? undefined : { height: sheetHeight }}
        >
          <button
            type="button"
            onClick={() => setSheetOpen((open) => !open)}
            aria-expanded={sheetOpen}
            aria-controls="panneau-contenu"
            className="flex w-full shrink-0 flex-col items-stretch rounded-t-2xl px-4 pb-2 pt-2 text-left lg:hidden"
          >
            <span className="mx-auto h-1.5 w-10 rounded-full bg-line-strong" aria-hidden="true" />
            <span className="mt-2 flex items-center justify-between gap-3">
              <span className="min-w-0">
                {/* Ouvert, le panneau affiche déjà son titre : on ne le répète pas. */}
                <span
                  className={`block truncate text-[17px] font-bold text-ink ${sheetOpen && selected ? "sr-only" : ""}`}
                  style={{ fontStretch: "88%" }}
                >
                  {selected ? selected.name : issueMonth ? `Bulletin ${ofMonth(issueMonth)}` : "Plans d'eau"}
                </span>
                {!sheetOpen && (
                  <span className="mt-0.5 flex items-center gap-1.5 truncate text-[14px] text-ink-2">
                    {selected ? (
                      <><StatusGlyph status={selected.status} size={10} /> {STATUS_META[selected.status].label}</>
                    ) : phase !== "ready" ? (
                      phase === "error" ? "Données indisponibles" : "Chargement…"
                    ) : alertCount > 0 ? (
                      <><StatusGlyph status="à risque" size={10} /> {alertCount} en alerte sur {plural(sites.length, "plan", "plans")} d'eau</>
                    ) : (
                      <><StatusGlyph status="actif" size={10} /> Aucune alerte sur {plural(sites.length, "plan", "plans")} d'eau</>
                    )}
                  </span>
                )}
              </span>
              <span className="flex h-9 shrink-0 items-center gap-1 rounded-full bg-sunken px-3 text-[14px] font-semibold text-ink">
                {sheetOpen ? <>Carte <ChevronDown size={16} aria-hidden="true" /></> : <>{selected ? "Fiche" : "Liste"} <ChevronUp size={16} aria-hidden="true" /></>}
              </span>
            </span>
          </button>

          <div
            id="panneau-contenu"
            className={`min-h-0 flex-1 flex-col ${sheetOpen ? "flex" : "max-lg:hidden lg:flex"}`}
          >
            {panel}
          </div>
        </aside>

        <main className="relative min-w-0 flex-1" aria-label="Carte">
          <MapCanvas
            sites={mapSites}
            shapes={shapes}
            selectedKey={selected?.key ?? null}
            onSelect={(key) => select(key)}
            route={route}
            me={me}
            bottomInset={isDesktop ? 0 : sheetHeight}
          />

          <details
            className="no-print absolute left-3 top-3 z-[500] rounded-lg bg-surface/95 text-[14px] shadow-panel backdrop-blur-sm"
            open={isDesktop || undefined}
          >
            <summary className="flex h-9 cursor-pointer list-none items-center gap-1.5 px-3 font-semibold text-ink [&::-webkit-details-marker]:hidden">
              Légende <ChevronDown size={15} aria-hidden="true" />
            </summary>
            <ul className="space-y-1.5 px-3 pb-3 pt-0.5">
              {STATUS_ORDER.map((status) => (
                <li key={status} className="flex items-center gap-2 text-ink">
                  <span
                    className="inline-block size-3 rounded-full"
                    style={status === "inconnu"
                      ? { boxShadow: `inset 0 0 0 2px ${STATUS_META[status].color}`, background: "#fff" }
                      : { background: STATUS_META[status].color }}
                    aria-hidden="true"
                  />
                  {STATUS_META[status].label}
                </li>
              ))}
            </ul>
          </details>

          <div className="no-print absolute right-[10px] top-[98px] z-[500] flex flex-col items-end gap-2">
            <button
              type="button" onClick={locateMe} disabled={locating}
              aria-label="Me localiser sur la carte" title="Me localiser"
              className="flex size-[38px] items-center justify-center rounded-lg border border-line-strong bg-surface text-ink shadow-panel hover:bg-sunken"
            >
              {locating ? <LoaderCircle size={18} className="spin" aria-hidden="true" /> : <LocateFixed size={18} aria-hidden="true" />}
            </button>
            {locateError && (
              <div role="alert" className="w-64 rounded-lg bg-surface p-3 text-[14px] leading-snug text-ink shadow-panel">
                {locateError}
                <button type="button" onClick={() => setLocateError(null)} className="mt-1.5 block font-semibold text-water">
                  Fermer
                </button>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
