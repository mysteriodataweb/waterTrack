import type { NavigationRoute, SectionKey, Source } from "./types";
import { PanelAccueil } from "./panels/PanelAccueil";
import { PanelNavigation } from "./panels/PanelNavigation";
import { PanelRapports } from "./panels/PanelRapports";
import { PanelAnalyse } from "./panels/PanelAnalyse";
import { X } from "lucide-react";

const titles: Record<SectionKey, string> = {
  accueil: "Accueil",
  navigation: "Navigation terrain",
  rapports: "Rapports",
  analyse: "Analyse IA",
};

export function SectionPanel({
  section, sources, targetSource, actionNonce, onSelect, onRouteChange, onClose,
}: {
  section: SectionKey;
  sources: Source[];
  targetSource: Source | null;
  actionNonce: number;
  onSelect: (s: Source) => void;
  onRouteChange: (route: NavigationRoute | null) => void;
  onClose: () => void;
}) {
  return (
    <div
      key={section}
      className="fixed inset-x-0 bottom-0 top-[124px] z-40 flex flex-col overflow-hidden rounded-t-xl border border-[#2c3442]/70 bg-[#13171e]/95 backdrop-blur-xl text-white shadow-[0_24px_80px_rgba(5,7,10,0.4)] sm:top-[132px] lg:inset-x-auto lg:bottom-auto lg:left-[266px] lg:top-[128px] lg:max-h-[calc(100vh-156px)] lg:w-[560px] lg:max-w-[calc(100vw-620px)] lg:rounded-md lg:bg-[#13171e]/70"
      style={{ animation: "panel-pop 0.22s ease-out" }}
    >
      <style>{`@keyframes panel-pop { from { transform: translateY(10px) scale(0.98); opacity: 0; } to { transform: translateY(0) scale(1); opacity: 1; } }`}</style>
      <div className="flex shrink-0 items-center justify-between border-b border-[#2a3140]/70 bg-[#151a21]/60 px-4 py-3">
        <div>
          <div className="text-sm font-semibold tracking-wide">{titles[section]}</div>
          <div className="text-[11px] text-[#a3afbd]">Panneau contextuel</div>
        </div>
        <button
          onClick={onClose}
          className="flex size-8 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white"
          aria-label="Fermer le panneau"
        >
          <X className="size-4" />
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain lg:max-h-[calc(100vh-224px)] lg:flex-none">
        {section === "accueil" && <PanelAccueil sources={sources} onSelect={onSelect} />}
        {section === "navigation" && (
          <PanelNavigation
            sources={sources}
            targetSource={targetSource}
            actionNonce={actionNonce}
            onSelect={onSelect}
            onRouteChange={onRouteChange}
          />
        )}
        {section === "rapports" && <PanelRapports />}
        {section === "analyse" && <PanelAnalyse sources={sources} targetSource={targetSource} actionNonce={actionNonce} />}
      </div>
    </div>
  );
}
