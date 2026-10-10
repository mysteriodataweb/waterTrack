import { useMemo } from "react";
import { ChevronRight, Search, X } from "lucide-react";
import { monthShort, percent, plural } from "@/lib/format";
import { useMonitoring } from "@/lib/monitoring";
import { STATUS_META, STATUS_ORDER, countByStatus, type Site, type Status } from "@/lib/sites";
import { FillGauge } from "@/ui/FillGauge";
import { StatusGlyph } from "@/ui/Status";

export interface Filters {
  query: string;
  statuses: Status[];
  zone: string;
}

export const NO_FILTERS: Filters = { query: "", statuses: [], zone: "" };

export function SiteList({
  all,
  visible,
  filters,
  onFilters,
  onSelect,
}: {
  /** Toutes les retenues (pour les compteurs et la liste des zones). */
  all: Site[];
  /** Les retenues qui passent les filtres. */
  visible: Site[];
  filters: Filters;
  onFilters: (next: Filters) => void;
  onSelect: (key: string) => void;
}) {
  const { criticalFill } = useMonitoring();
  const counts = useMemo(() => countByStatus(all), [all]);
  const zones = useMemo(
    () => [...new Set(all.map((s) => s.zone).filter((z): z is string => Boolean(z)))].sort((a, b) => a.localeCompare(b, "fr")),
    [all],
  );
  const filtered = filters.query !== "" || filters.statuses.length > 0 || filters.zone !== "";

  const toggleStatus = (status: Status) => {
    const statuses = filters.statuses.includes(status)
      ? filters.statuses.filter((s) => s !== status)
      : [...filters.statuses, status];
    onFilters({ ...filters, statuses });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 space-y-3 border-b px-4 pb-3 pt-3">
        <div className="flex gap-2">
          <label className="relative block min-w-0 flex-1">
            <span className="sr-only">Chercher une retenue</span>
            <Search size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3" aria-hidden="true" />
            <input
              type="search"
              value={filters.query}
              onChange={(event) => onFilters({ ...filters, query: event.target.value })}
              placeholder="Nom, numéro ou province"
              className="h-11 w-full rounded-lg border border-line-strong bg-surface pl-10 pr-3 text-[16px] text-ink placeholder:text-ink-3"
            />
          </label>
          {zones.length > 1 && (
            <label className="block shrink-0">
              <span className="sr-only">Province</span>
              <select
                value={filters.zone}
                onChange={(event) => onFilters({ ...filters, zone: event.target.value })}
                className="h-11 max-w-[9.5rem] rounded-lg border border-line-strong bg-surface px-2.5 text-[15px] text-ink"
              >
                <option value="">Toutes provinces</option>
                {zones.map((zone) => <option key={zone} value={zone}>{zone}</option>)}
              </select>
            </label>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filtrer par état">
          {STATUS_ORDER.filter((status) => counts[status] > 0).map((status) => {
            const pressed = filters.statuses.includes(status);
            return (
              <button
                key={status}
                type="button"
                aria-pressed={pressed}
                onClick={() => toggleStatus(status)}
                className={`inline-flex h-9 items-center gap-1.5 rounded-full border px-3 text-[14px] font-semibold transition-colors ${
                  pressed ? "border-ink bg-ink text-white" : "border-line-strong bg-surface text-ink hover:bg-sunken"
                }`}
              >
                <StatusGlyph status={status} size={10} />
                {STATUS_META[status].plural}
                <span className={`num font-normal ${pressed ? "text-white/80" : "text-ink-2"}`}>{counts[status]}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex shrink-0 items-center justify-between px-4 pb-1 pt-3">
        <p className="text-[14px] text-ink-2" aria-live="polite">
          {filtered
            ? `${plural(visible.length, "résultat")} sur ${all.length}`
            : `${plural(all.length, "plan", "plans")} d'eau, les plus menacés d'abord`}
        </p>
        {filtered && (
          <button
            type="button"
            onClick={() => onFilters(NO_FILTERS)}
            className="inline-flex h-8 items-center gap-1 rounded-md px-2 text-[14px] font-semibold text-water hover:bg-water-soft"
          >
            <X size={15} aria-hidden="true" /> Effacer les filtres
          </button>
        )}
      </div>

      {visible.length === 0 ? (
        <div className="px-4 py-6 text-[15px] text-ink-2">
          <p className="font-semibold text-ink">Aucun plan d'eau ne correspond.</p>
          <p className="mt-1">Essayez un autre nom, ou effacez les filtres pour revoir toute la liste.</p>
        </div>
      ) : (
        <ul className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 pb-4">
          {visible.map((site) => <SiteRow key={site.key} site={site} critical={criticalFill} onSelect={onSelect} />)}
        </ul>
      )}
    </div>
  );
}

function SiteRow({ site, critical, onSelect }: { site: Site; critical: number; onSelect: (key: string) => void }) {
  const last = site.forecast.at(-1);
  return (
    <li>
      <button
        type="button"
        onClick={() => onSelect(site.key)}
        className="group flex w-full items-center gap-3 rounded-lg px-2 py-2.5 text-left hover:bg-sunken"
      >
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <StatusGlyph status={site.status} size={11} />
            <span className="truncate text-[16px] font-semibold text-ink">{site.name}</span>
            {site.zone && <span className="shrink-0 text-[14px] text-ink-2">{site.zone}</span>}
          </div>
          {site.fillNow !== null ? (
            <>
              <div className="mt-2 flex items-center gap-2.5">
                <div className="flex-1"><FillGauge fill={site.fillNow} status={site.status} critical={critical} size="sm" /></div>
                <span className="num w-12 text-right text-[15px] font-semibold text-ink">{percent(site.fillNow)}</span>
              </div>
              <p className="num mt-1.5 text-[14px] text-ink-2">
                {site.status === "actif"
                  ? last ? `Prévu à ${percent(last.fill)} en ${monthShort(last.month, false)}` : "Pas d'alerte"
                  : <span style={{ color: STATUS_META[site.status].ink }} className="font-semibold">
                      {STATUS_META[site.status].label}
                      {last && <span className="font-normal text-ink-2">, prévu à {percent(last.fill)} en {monthShort(last.month, false)}</span>}
                    </span>}
              </p>
            </>
          ) : (
            <p className="mt-1 text-[14px] text-ink-2">{STATUS_META[site.status].label}, pas de suivi mensuel</p>
          )}
        </div>
        <ChevronRight size={18} className="shrink-0 text-ink-3 group-hover:text-ink" aria-hidden="true" />
      </button>
    </li>
  );
}
