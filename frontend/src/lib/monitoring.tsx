import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { ApiError, fetchAllSources, fetchBulletin, isAbort, wakeAndFetch, type ApiBulletin } from "./api";
import { buildSites, parseShapes, type Shapes, type Site } from "./sites";

type Phase = "loading" | "waking" | "ready" | "error";

interface Monitoring {
  phase: Phase;
  error: string | null;
  sites: Site[];
  shapes: Shapes;
  bulletin: ApiBulletin | null;
  /** Mois du dernier bulletin, "AAAA-MM". */
  issueMonth: string | null;
  criticalFill: number;
  reload: () => void;
}

const MonitoringContext = createContext<Monitoring | null>(null);

function describe(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === "network") {
      return "Le serveur de données ne répond pas. Vérifiez votre connexion, puis réessayez.";
    }
    if (error.kind === "timeout") {
      return "Le serveur met trop de temps à répondre. Réessayez dans un instant.";
    }
    return error.message;
  }
  return "Les données n'ont pas pu être chargées.";
}

async function loadShapes(): Promise<Shapes> {
  // Contours réels des plans d'eau (OpenStreetMap). Facultatif : sans eux,
  // la carte affiche de simples points.
  try {
    const response = await fetch(`${import.meta.env.BASE_URL}water-polygons.geojson`);
    return response.ok ? parseShapes(await response.json()) : new Map();
  } catch {
    return new Map();
  }
}

export function MonitoringProvider({ children }: { children: ReactNode }) {
  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [shapes, setShapes] = useState<Shapes>(() => new Map());
  const [bulletin, setBulletin] = useState<ApiBulletin | null>(null);
  const [attempt, setAttempt] = useState(0);
  const hasData = useRef(false);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    if (!hasData.current) setPhase("loading");
    setError(null);

    (async () => {
      try {
        const [sources, nextBulletin, nextShapes] = await Promise.all([
          wakeAndFetch(() => fetchAllSources(signal), {
            signal,
            onWaking: () => { if (!hasData.current) setPhase("waking"); },
          }),
          // Sans bulletin, la carte reste utilisable (inventaire sans prévision).
          wakeAndFetch(() => fetchBulletin(signal), { signal }).catch((err: unknown) => {
            if (isAbort(err)) throw err;
            return null;
          }),
          loadShapes(),
        ]);
        if (signal.aborted) return;
        setShapes(nextShapes);
        setBulletin(nextBulletin);
        setSites(buildSites(sources, nextBulletin, nextShapes));
        hasData.current = true;
        setPhase("ready");
      } catch (err) {
        if (isAbort(err) || signal.aborted) return;
        // Un rechargement raté ne doit pas effacer des données déjà affichées.
        if (hasData.current) return;
        setError(describe(err));
        setPhase("error");
      }
    })();

    return () => controller.abort();
  }, [attempt]);

  const reload = useCallback(() => setAttempt((value) => value + 1), []);

  const value = useMemo<Monitoring>(() => ({
    phase,
    error,
    sites,
    shapes,
    bulletin,
    issueMonth: bulletin?.issue_month ?? null,
    criticalFill: bulletin?.critical_fill ?? 0.2,
    reload,
  }), [phase, error, sites, shapes, bulletin, reload]);

  return <MonitoringContext.Provider value={value}>{children}</MonitoringContext.Provider>;
}

export function useMonitoring(): Monitoring {
  const value = useContext(MonitoringContext);
  if (!value) throw new Error("useMonitoring doit être utilisé sous <MonitoringProvider>");
  return value;
}
