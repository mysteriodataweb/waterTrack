import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Search, X } from "lucide-react";
import type { Source, Status } from "./types";

const cities = [
  { name: "Ouagadougou", count: 278, active: true },
  { name: "Bobo-Dioulasso", count: 0, active: false },
  { name: "Koudougou", count: 0, active: false },
  { name: "Ouahigouya", count: 0, active: false },
];

export function FilterPanel({
  sources, filtreStatut, setFiltreStatut, open = false, onClose,
}: {
  sources: Source[];
  filtreStatut: Status[];
  setFiltreStatut: (s: Status[]) => void;
  open?: boolean;
  onClose?: () => void;
}) {
  const [expanded, setExpanded] = useState(true);
  const [ndwiMin, setNdwiMin] = useState(-0.5);
  const [ndwiMax, setNdwiMax] = useState(1);
  const [search, setSearch] = useState("");

  const toggle = (s: Status) => setFiltreStatut(filtreStatut.includes(s) ? filtreStatut.filter(x => x !== s) : [...filtreStatut, s]);
  const zones = useMemo(() => {
    if (sources.length === 0) return cities;

    const counts = sources.reduce<Record<string, number>>((acc, source) => {
const zone = (source.zone_detail ?? source.zone)?.trim() || "Ouagadougou";
    const label = zone.charAt(0).toUpperCase() + zone.slice(1);
    acc[label] = (acc[label] ?? 0) + 1;
    return acc;
    }, {});

    return Object.entries(counts).map(([name, count], index) => ({
      name,
      count,
      active: index === 0,
    }));
  }, [sources]);
  const filteredCities = zones.filter((city) => city.name.toLowerCase().includes(search.toLowerCase()));

  const statuses: { s: Status; c: string; l: string }[] = [
    { s: "actif", c: "#62e6a6", l: "ACTIVES" },
    { s: "à risque", c: "#f6c65b", l: "A RISQUE" },
    { s: "tari", c: "#ff6b6b", l: "TARIES" },
  ];

  return (
    <aside
      className={`fixed top-12 right-0 bottom-0 z-[45] w-[300px] max-w-[86vw] overflow-hidden border-l border-[#2c3442]/70 bg-[#13171e]/95 backdrop-blur-xl text-white shadow-[0_24px_80px_rgba(5,7,10,0.4)] transition-transform duration-200 ease-out lg:right-5 lg:top-[132px] lg:bottom-5 lg:max-w-none lg:translate-x-0 lg:rounded-md lg:border lg:bg-[#13171e]/70 ${
        open ? "translate-x-0" : "translate-x-full"
      }`}
    >
      <div className="h-full overflow-y-auto overscroll-contain p-4 space-y-5">
        <div>
          <div className="mb-3 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-wide">Zones d'analyse</div>
              <div className="text-[11px] text-[#a3afbd]">Sources et filtres actifs</div>
            </div>
            {onClose && (
              <button
                onClick={onClose}
                className="flex size-8 shrink-0 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white lg:hidden"
                aria-label="Fermer les filtres"
              >
                <X className="size-4" />
              </button>
            )}
          </div>

          <label className="mb-3 flex h-10 items-center gap-2 rounded-md border border-[#2a3140] bg-[#151a21] px-3 text-[#a3afbd] focus-within:border-[#9fc9ea]">
            <Search className="size-4" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Rechercher une zone"
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-[#79869a]"
            />
          </label>

          <button onClick={() => setExpanded(!expanded)} className="w-full flex items-center gap-2 rounded-md p-2 text-left transition hover:bg-[#171b22]">
            {expanded ? <ChevronDown className="size-4 text-[#9fc9ea]" /> : <ChevronRight className="size-4 text-[#9fc9ea]" />}
            <span className="text-sm font-medium">Burkina Faso</span>
            <span className="ml-auto rounded bg-[#20262d] px-2 py-0.5 text-[11px] text-[#9fc9ea]">{sources.length}</span>
          </button>
          {expanded && (
            <div className="mt-2 space-y-1">
              {filteredCities.map(c => (
                <div key={c.name} className={`flex items-center justify-between rounded-md px-3 py-2 text-xs ${c.active ? "bg-[#20262d] text-white shadow-[inset_3px_0_0_#9fc9ea]" : "text-[#8d9aa9]"}`}>
                  <span className="flex items-center gap-2">
                    <span className={`size-2 rounded-full ${c.active ? "bg-[#9fc9ea]" : "bg-[#4a5566]"}`} />
                    {c.name}
                  </span>
                  <span>{c.active ? `${c.count}` : "BIENTOT"}</span>
                </div>
              ))}
              {filteredCities.length === 0 && (
                <div className="rounded-md border border-[#2a3140] bg-[#151a21] px-3 py-3 text-xs text-[#a3afbd]">
                  Aucune zone trouvee
                </div>
              )}
            </div>
          )}
          <div className="mt-3 space-y-1">
            {["Mali", "Niger"].map(n => (
              <div key={n} className="flex items-center justify-between rounded-md p-2 text-xs text-[#6d7a8c]">
                <span>{n}</span><span>BIENTOT</span>
              </div>
            ))}
          </div>
        </div>

        <div className="border-t border-[#2a3140]/80 pt-5">
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#9fc9ea]">Filtrer par statut</div>
          <div className="space-y-2">
            {statuses.map(({ s, c, l }) => {
              const checked = filtreStatut.includes(s);
              return (
                <label key={s} className="flex cursor-pointer items-center gap-3 rounded-md p-2 text-xs transition hover:bg-[#171b22]">
                  <span className={`size-4 rounded border flex items-center justify-center transition ${checked ? "bg-[#9fc9ea] border-[#9fc9ea]" : "border-[#3a424d]"}`}>
                    {checked && <span className="size-1.5 rounded-sm bg-[#13171e]" />}
                  </span>
                  <span className="size-2 rounded-full" style={{ background: c, boxShadow: `0 0 6px ${c}` }} />
                  <span className="tracking-wide">{l}</span>
                  <input type="checkbox" checked={checked} onChange={() => toggle(s)} className="hidden" />
                </label>
              );
            })}
          </div>
        </div>

        <div className="border-t border-[#2a3140]/80 pt-5">
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.16em] text-[#9fc9ea]">Filtre NDWI</div>
          <div className="mb-2 text-[11px] uppercase tracking-widest text-[#a3afbd]">Indice eau min / max</div>
          <div className="space-y-3">
            <input type="range" min="-1" max="1" step="0.01" value={ndwiMin} onChange={e => setNdwiMin(+e.target.value)} className="w-full accent-[#9fc9ea]" />
            <input type="range" min="-1" max="1" step="0.01" value={ndwiMax} onChange={e => setNdwiMax(+e.target.value)} className="w-full accent-[#9fc9ea]" />
          </div>
          <div className="mt-2 flex justify-between text-xs text-[#9fc9ea]">
            <span>{ndwiMin.toFixed(2)}</span>
            <span className="text-[#79869a]">min / max</span>
            <span>{ndwiMax.toFixed(2)}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
