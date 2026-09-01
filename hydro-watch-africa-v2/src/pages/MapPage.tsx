import { useEffect, useMemo, useState } from "react";
import { MapBackground } from "@/components/map/MapBackground";
import { TopNavbar } from "@/components/map/TopNavbar";
import { KpisBar } from "@/components/map/KpisBar";
import { Sidebar } from "@/components/map/Sidebar";
import { SectionPanel } from "@/components/map/SectionPanel";
import { FilterPanel } from "@/components/map/FilterPanel";
import { SourcePopup } from "@/components/map/SourcePopup";
import { fetchWaterSources } from "@/components/map/api";
import type { NavigationRoute, SectionKey, Source, Status } from "@/components/map/types";

export default function MapPage() {
  const [activeSection, setActiveSection] = useState<SectionKey | null>(null);
  const [selected, setSelected] = useState<Source | null>(null);
  const [filtreStatut, setFiltreStatut] = useState<Status[]>(["actif", "à risque", "tari"]);
  const [sources, setSources] = useState<Source[]>([]);
  const [navigationRoute, setNavigationRoute] = useState<NavigationRoute | null>(null);
  const [panelTarget, setPanelTarget] = useState<Source | null>(null);
  const [panelActionNonce, setPanelActionNonce] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    setLoading(true);
    setError(null);
    fetchWaterSources(controller.signal)
      .then(setSources)
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Impossible de charger les sources d'eau");
        setSources([]);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, []);

  const filtered = useMemo(() => sources.filter(s => filtreStatut.includes(s.statut)), [sources, filtreStatut]);
  const totalArea = useMemo(() => filtered.reduce((a, s) => a + s.superficie, 0), [filtered]);
  const alerts = useMemo(() => filtered.filter(s => s.statut === "tari").length, [filtered]);
  const topSource = useMemo(() => {
    const max = filtered.reduce<Source | null>((acc, s) => (acc === null || s.risk_score > acc.risk_score ? s : acc), null);
    return max ? { label: max.label, risk: max.risk_score } : undefined;
  }, [filtered]);

  const openPanelForSource = (section: Extract<SectionKey, "navigation" | "analyse">, source: Source) => {
    setPanelTarget(source);
    setPanelActionNonce((value) => value + 1);
    setActiveSection(section);
    setSelected(null);
  };

  return (
    <div className="h-screen w-screen overflow-hidden bg-background text-foreground">
      <MapBackground sources={filtered} navigationRoute={navigationRoute} onSourceClick={setSelected} />
      <TopNavbar />
      <KpisBar total={filtered.length} alerts={alerts} area={totalArea} topSource={topSource} />
      <Sidebar active={activeSection} onChange={(section) => setActiveSection(activeSection === section ? null : section)} />
      {activeSection && (
        <SectionPanel
          section={activeSection}
          sources={filtered}
          targetSource={panelTarget}
          actionNonce={panelActionNonce}
          onSelect={(source) => {
            // Sélection depuis un panneau : ne rouvre PAS le popup.
            if (activeSection === "accueil") openPanelForSource("analyse", source);
            else setPanelTarget(source);
          }}
          onRouteChange={setNavigationRoute}
          onClose={() => setActiveSection(null)}
        />
      )}
      <FilterPanel sources={sources} filtreStatut={filtreStatut} setFiltreStatut={setFiltreStatut} />
      {(loading || error) && (
        <div className="fixed left-1/2 top-[132px] z-40 -translate-x-1/2 rounded-md border border-[#3a424d]/60 bg-[#13171e]/65 backdrop-blur-xl px-4 py-3 text-sm text-white shadow-[0_18px_60px_rgba(5,7,10,0.4)]">
          {loading ? "Chargement des sources depuis le backend..." : error}
        </div>
      )}
      {selected && (
        <SourcePopup
          source={selected}
          onAnalyze={(source) => openPanelForSource("analyse", source)}
          onNavigate={(source) => openPanelForSource("navigation", source)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
