import type { ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { LoaderCircle, RotateCw } from "lucide-react";
import { ofMonth } from "@/lib/format";
import { useMonitoring } from "@/lib/monitoring";

/** Une échelle de crue : trois graduations et le niveau d'eau. */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 26 26" aria-hidden="true" className="shrink-0">
      <rect x="1" y="1" width="24" height="24" rx="6" fill="#0b5c8a" />
      <path d="M15 6.5h4M12 10.5h7M9 14.5h10" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" fill="none" />
      <path d="M1 19c3-1.8 5-1.8 8 0s5 1.8 8 0 5-1.8 8 0a6 6 0 0 1-6 6H7a6 6 0 0 1-6-6Z" fill="#fff" />
    </svg>
  );
}

export function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2 rounded-md text-ink no-underline" aria-label="WaterTracker, accueil">
      <BrandMark />
      <span className="text-[18px] font-bold tracking-tight" style={{ fontStretch: "88%" }}>WaterTracker</span>
    </Link>
  );
}

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex h-10 items-center rounded-md px-3 text-[15px] font-semibold no-underline transition-colors ${
    isActive ? "bg-water-soft text-water-deep" : "text-ink-2 hover:bg-sunken hover:text-ink"
  }`;

export function AppHeader() {
  const { issueMonth } = useMonitoring();
  return (
    <header className="no-print z-[1100] flex h-14 shrink-0 items-center gap-3 border-b bg-surface px-3 sm:px-5">
      <Brand />
      <nav aria-label="Navigation principale" className="ml-auto flex items-center gap-1 sm:ml-6">
        <NavLink to="/carte" className={navClass}>Carte</NavLink>
        <NavLink to="/bulletin" className={navClass}>Bulletin</NavLink>
      </nav>
      {issueMonth && (
        <p className="ml-auto hidden text-[14px] text-ink-2 md:block">
          Dernières mesures : bulletin {ofMonth(issueMonth)}
        </p>
      )}
    </header>
  );
}

/** Chargement, réveil du serveur ou erreur : toujours une explication et une action. */
export function LoadState({ compact = false }: { compact?: boolean }) {
  const { phase, error, reload } = useMonitoring();
  if (phase === "ready") return null;

  if (phase === "error") {
    return (
      <div role="alert" className={`rounded-lg border border-dry/30 bg-dry-soft ${compact ? "p-3" : "p-4"}`}>
        <p className="font-semibold text-dry-ink">Données indisponibles</p>
        <p className="mt-1 text-[15px] text-ink">{error}</p>
        <button
          type="button" onClick={reload}
          className="mt-3 inline-flex h-10 items-center gap-2 rounded-md bg-ink px-4 text-[15px] font-semibold text-white hover:bg-ink/90"
        >
          <RotateCw size={16} aria-hidden="true" /> Réessayer
        </button>
      </div>
    );
  }

  return (
    <div role="status" className={`flex items-start gap-3 rounded-lg bg-sunken ${compact ? "p-3" : "p-4"}`}>
      <LoaderCircle size={20} className="spin mt-0.5 shrink-0 text-water" aria-hidden="true" />
      <div className="text-[15px]">
        <p className="font-semibold text-ink">
          {phase === "waking" ? "Le serveur de données démarre…" : "Chargement des retenues…"}
        </p>
        {phase === "waking" && (
          <p className="mt-0.5 text-ink-2">
            Il se met en veille quand personne ne l'utilise. Comptez jusqu'à une minute, la page se mettra à jour seule.
          </p>
        )}
      </div>
    </div>
  );
}

export function Notice({ tone = "info", children }: { tone?: "info" | "warn"; children: ReactNode }) {
  return (
    <div
      className={`rounded-lg px-3.5 py-3 text-[15px] leading-snug ${
        tone === "warn" ? "bg-warn-soft text-ink" : "bg-water-soft text-ink"
      }`}
    >
      {children}
    </div>
  );
}
