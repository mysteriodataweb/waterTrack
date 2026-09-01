import { BarChart3, Brain, CircleDot, Home, MapPin, ShieldCheck, User } from "lucide-react";
import type { SectionKey } from "./types";

const items: { key: SectionKey; icon: any; label: string; hint: string }[] = [
  { key: "accueil", icon: Home, label: "Accueil", hint: "Vue mission" },
  { key: "navigation", icon: MapPin, label: "Navigation", hint: "Terrain" },
  { key: "rapports", icon: BarChart3, label: "Rapports", hint: "Historique" },
  { key: "analyse", icon: Brain, label: "Analyse IA", hint: "Recommandations" },
];

export function Sidebar({ active, onChange }: { active: SectionKey | null; onChange: (s: SectionKey) => void }) {
  return (
    <aside className="fixed top-12 left-0 bottom-0 w-[238px] z-40 bg-[#101318]/60 backdrop-blur-xl border-r border-[#2a3140]/60 shadow-[12px_0_42px_rgba(8,10,14,0.35)] flex flex-col">
      <div className="px-4 py-5 border-b border-white/8">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-md bg-[#20262d] border border-[#3a424d] flex items-center justify-center text-[#9fc9ea]">
            <ShieldCheck className="size-5" />
          </div>
          <div>
            <div className="text-sm font-semibold text-white tracking-wide">Hydro Watch</div>
            <div className="text-[11px] text-[#a3afbd]">Mission secured</div>
          </div>
        </div>
      </div>

      <nav className="flex flex-col gap-1 p-3">
        {items.map(({ key, icon: Icon, label, hint }) => {
          const isActive = active === key;
          return (
            <button
              key={key}
              onClick={() => onChange(key)}
              className={`group relative flex h-12 w-full items-center gap-3 rounded-md px-3 text-left transition ${
                isActive
                  ? "bg-[#20262d] text-white shadow-[inset_0_0_0_1px_rgba(159,201,234,0.2)]"
                  : "text-[#b6c0cc] hover:bg-[#171b22] hover:text-white"
              }`}
            >
              {isActive && <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r bg-[#9fc9ea]" />}
              <Icon className={`size-5 ${isActive ? "text-[#9fc9ea]" : "text-[#7f8b99] group-hover:text-[#9fc9ea]"}`} />
              <span className="min-w-0">
                <span className="block text-sm font-medium leading-none">{label}</span>
                <span className="mt-1 block text-[11px] leading-none text-[#7f8b99]">{hint}</span>
              </span>
              {isActive && <CircleDot className="ml-auto size-3.5 text-[#9fc9ea]" />}
            </button>
          );
        })}
      </nav>

      <div className="mt-auto p-4">
        <div className="rounded-md border border-[#2a3140] bg-[#13171e] p-3">
          <div className="flex items-center gap-3">
            <div className="size-9 rounded-full bg-[#20262d] border border-[#3a424d] flex items-center justify-center">
              <User className="size-4 text-[#9fc9ea]" />
            </div>
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-white">Demo user</div>
              <div className="text-[11px] text-[#a3afbd]">Protection active</div>
            </div>
          </div>
        </div>
      </div>
    </aside>
  );
}
