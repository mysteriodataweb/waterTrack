import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Bike, Car, ExternalLink, Footprints, LoaderCircle, LocateFixed, Pause } from "lucide-react";
import { ApiError, fetchPlaceName, fetchRoute, isAbort, type ApiRoute, type GeoPoint, type NavigationProfile } from "@/lib/api";
import { distance, duration } from "@/lib/format";
import { OUAGADOUGOU, readCurrentPosition, routeProgress, toPosition, type Position } from "@/lib/geo";
import type { Site } from "@/lib/sites";
import { Notice } from "@/ui/chrome";
import type { MapRoute } from "./MapCanvas";

const MODES: Array<{ key: NavigationProfile; label: string; icon: typeof Car; google: string }> = [
  { key: "driving-car", label: "Voiture", icon: Car, google: "driving" },
  { key: "foot-walking", label: "À pied", icon: Footprints, google: "walking" },
  { key: "cycling-regular", label: "Vélo", icon: Bike, google: "bicycling" },
];

type Phase =
  | { kind: "locating" }
  | { kind: "geo-error"; message: string }
  | { kind: "routing" }
  | { kind: "route-error"; message: string }
  | { kind: "ready" };

export function RoutePanel({
  site,
  onBack,
  onRoute,
  onPosition,
}: {
  site: Site;
  onBack: () => void;
  onRoute: (route: MapRoute | null) => void;
  onPosition: (position: Position | null) => void;
}) {
  const [mode, setMode] = useState<NavigationProfile>("driving-car");
  const [phase, setPhase] = useState<Phase>({ kind: "locating" });
  const [origin, setOrigin] = useState<GeoPoint | null>(null);
  const [originLabel, setOriginLabel] = useState<string | null>(null);
  const [manualOrigin, setManualOrigin] = useState(false);
  const [route, setRoute] = useState<ApiRoute | null>(null);
  const [following, setFollowing] = useState(false);
  const [progress, setProgress] = useState<{ remaining: number; stepIndex: number; offRoute: number } | null>(null);
  const [followError, setFollowError] = useState<string | null>(null);

  const watchRef = useRef<number | null>(null);
  const requestRef = useRef<AbortController | null>(null);
  const routeRef = useRef<ApiRoute | null>(null);
  routeRef.current = route;
  const destination = { lat: site.lat, lng: site.lng };

  const stopFollowing = useCallback(() => {
    if (watchRef.current !== null) {
      navigator.geolocation.clearWatch(watchRef.current);
      watchRef.current = null;
    }
    setFollowing(false);
    setProgress(null);
  }, []);

  const computeRoute = useCallback(async (from: GeoPoint, profile: NavigationProfile) => {
    requestRef.current?.abort();
    const controller = new AbortController();
    requestRef.current = controller;
    setPhase({ kind: "routing" });
    setProgress(null);
    try {
      const next = await fetchRoute(from, { lat: site.lat, lng: site.lng }, profile, controller.signal);
      if (controller.signal.aborted) return;
      setRoute(next);
      onRoute({ geometry: next.geometry, origin: from, destination: { lat: site.lat, lng: site.lng } });
      setPhase({ kind: "ready" });
    } catch (err) {
      if (isAbort(err)) return;
      setRoute(null);
      onRoute(null);
      const noRoad = err instanceof ApiError && err.kind === "http" && err.status !== null && err.status < 500;
      setPhase({
        kind: "route-error",
        message: noRoad
          ? "Aucune route praticable n'a été trouvée entre ces deux points pour ce mode de déplacement."
          : "Le calcul d'itinéraire ne répond pas. Réessayez dans un instant.",
      });
    }
  }, [site.lat, site.lng, onRoute]);

  const locate = useCallback(async (profile: NavigationProfile) => {
    setPhase({ kind: "locating" });
    setManualOrigin(false);
    try {
      const position = await readCurrentPosition();
      onPosition(position);
      setOrigin(position);
      setOriginLabel(null);
      fetchPlaceName(position).then(setOriginLabel);
      await computeRoute(position, profile);
    } catch (err) {
      // On n'invente pas de point de départ : on explique et on laisse choisir.
      setPhase({ kind: "geo-error", message: err instanceof Error ? err.message : "Position indisponible." });
    }
  }, [computeRoute, onPosition]);

  // Ouvrir le panneau lance la recherche ; le quitter nettoie la carte.
  useEffect(() => {
    locate("driving-car");
    return () => {
      requestRef.current?.abort();
      if (watchRef.current !== null) navigator.geolocation.clearWatch(watchRef.current);
      onRoute(null);
    };
    // Volontairement une seule fois par retenue.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [site.key]);

  const changeMode = (next: NavigationProfile) => {
    setMode(next);
    stopFollowing();
    if (origin) computeRoute(origin, next);
  };

  const startFromCity = () => {
    setManualOrigin(true);
    setOrigin(OUAGADOUGOU);
    setOriginLabel("Centre de Ouagadougou");
    onPosition(null);
    computeRoute(OUAGADOUGOU, mode);
  };

  const startFollowing = () => {
    setFollowError(null);
    stopFollowing();
    watchRef.current = navigator.geolocation.watchPosition(
      (raw) => {
        const position = toPosition(raw);
        setFollowError(null);
        onPosition(position);
        const current = routeRef.current;
        if (current) {
          setProgress(routeProgress(current.geometry, current.steps.map((s) => s.distance), current.distance, position));
        }
      },
      (error) => {
        // Seul un refus d'autorisation arrête le suivi. Une perte de signal est
        // passagère : on garde l'écoute, la position reprendra d'elle-même.
        if (error.code === error.PERMISSION_DENIED) {
          setFollowError("Le suivi s'est arrêté : la localisation n'est plus autorisée pour ce site.");
          stopFollowing();
        } else {
          setFollowError("Signal GPS faible. Le suivi reprendra dès que la position sera retrouvée.");
        }
      },
      { enableHighAccuracy: true, timeout: 15_000, maximumAge: 4000 },
    );
    setFollowing(true);
  };

  const remaining = progress?.remaining ?? route?.distance ?? 0;
  const remainingTime = route && route.distance > 0 ? route.duration * (remaining / route.distance) : route?.duration ?? 0;
  const arrived = following && progress !== null && progress.remaining < 60;
  const googleMode = MODES.find((m) => m.key === mode)?.google ?? "driving";
  const googleUrl = `https://www.google.com/maps/dir/?api=1&destination=${destination.lat},${destination.lng}&travelmode=${googleMode}`;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="shrink-0 border-b px-4 pb-3 pt-2">
        <button
          type="button" onClick={onBack}
          className="-ml-2 inline-flex h-10 items-center gap-1.5 rounded-md px-2 text-[15px] font-semibold text-water hover:bg-water-soft"
        >
          <ArrowLeft size={17} aria-hidden="true" /> Retour à la fiche
        </button>
        <h2 className="mt-1 text-[22px] text-ink">Itinéraire vers {site.name}</h2>

        <div className="mt-3 grid grid-cols-3 gap-1 rounded-lg bg-sunken p-1" role="group" aria-label="Mode de déplacement">
          {MODES.map((item) => (
            <button
              key={item.key}
              type="button"
              aria-pressed={mode === item.key}
              onClick={() => changeMode(item.key)}
              className={`flex h-10 items-center justify-center gap-1.5 rounded-md text-[15px] font-semibold transition-colors ${
                mode === item.key ? "bg-surface text-ink shadow-sm" : "text-ink-2 hover:text-ink"
              }`}
            >
              <item.icon size={17} aria-hidden="true" /> {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-4" aria-live="polite">
        {(phase.kind === "locating" || phase.kind === "routing") && (
          <div role="status" className="flex items-center gap-3 rounded-lg bg-sunken p-4 text-[15px] text-ink">
            <LoaderCircle size={20} className="spin shrink-0 text-water" aria-hidden="true" />
            {phase.kind === "locating"
              ? "Recherche de votre position… Acceptez la demande de localisation du navigateur."
              : "Calcul de l'itinéraire…"}
          </div>
        )}

        {phase.kind === "geo-error" && (
          <div role="alert" className="rounded-lg border border-warn/40 bg-warn-soft p-4">
            <p className="font-semibold text-ink">Position introuvable</p>
            <p className="mt-1 text-[15px] text-ink">{phase.message}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button" onClick={() => locate(mode)}
                className="inline-flex h-10 items-center rounded-md bg-ink px-4 text-[15px] font-semibold text-white hover:bg-ink/90"
              >
                Réessayer
              </button>
              <button
                type="button" onClick={startFromCity}
                className="inline-flex h-10 items-center rounded-md border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink hover:bg-sunken"
              >
                Partir du centre de Ouagadougou
              </button>
            </div>
          </div>
        )}

        {phase.kind === "route-error" && (
          <div role="alert" className="rounded-lg border border-warn/40 bg-warn-soft p-4">
            <p className="font-semibold text-ink">Itinéraire indisponible</p>
            <p className="mt-1 text-[15px] text-ink">{phase.message}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {origin && (
                <button
                  type="button" onClick={() => computeRoute(origin, mode)}
                  className="inline-flex h-10 items-center rounded-md bg-ink px-4 text-[15px] font-semibold text-white hover:bg-ink/90"
                >
                  Réessayer
                </button>
              )}
              <a
                href={googleUrl} target="_blank" rel="noreferrer"
                className="inline-flex h-10 items-center gap-1.5 rounded-md border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink no-underline hover:bg-sunken"
              >
                Ouvrir dans Google Maps <ExternalLink size={15} aria-hidden="true" />
              </a>
            </div>
          </div>
        )}

        {phase.kind === "ready" && route && (
          <>
            <div className="flex items-end gap-6">
              <div>
                <p className="text-[14px] text-ink-2">{following ? "Reste" : "Distance"}</p>
                <p className="num text-[30px] font-bold leading-none text-ink">{distance(remaining)}</p>
              </div>
              <div>
                <p className="text-[14px] text-ink-2">Durée estimée</p>
                <p className="num text-[30px] font-bold leading-none text-ink">{duration(remainingTime)}</p>
              </div>
            </div>
            <p className="text-[15px] text-ink-2">
              Départ : {originLabel ?? (manualOrigin ? "centre de Ouagadougou" : "votre position")}
            </p>

            {manualOrigin && (
              <Notice tone="warn">
                Itinéraire calculé depuis le centre de Ouagadougou, faute de position. Le suivi GPS n'est pas disponible.
              </Notice>
            )}
            {arrived && <Notice>Vous êtes arrivé à proximité de la retenue.</Notice>}
            {following && !arrived && progress && progress.offRoute > 250 && (
              <Notice tone="warn">
                Vous êtes à {distance(progress.offRoute)} du tracé.{" "}
                <button type="button" onClick={() => locate(mode)} className="font-semibold text-water underline">
                  Recalculer depuis ici
                </button>
              </Notice>
            )}
            {followError && <Notice tone="warn">{followError}</Notice>}

            <div className="flex flex-wrap gap-2">
              {!manualOrigin && (
                following ? (
                  <button
                    type="button" onClick={stopFollowing}
                    className="inline-flex h-11 items-center gap-2 rounded-lg border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink hover:bg-sunken"
                  >
                    <Pause size={17} aria-hidden="true" /> Arrêter le suivi
                  </button>
                ) : (
                  <button
                    type="button" onClick={startFollowing}
                    className="inline-flex h-11 items-center gap-2 rounded-lg bg-water px-4 text-[15px] font-semibold text-white hover:bg-water-deep"
                  >
                    <LocateFixed size={17} aria-hidden="true" /> Suivre ma position
                  </button>
                )
              )}
              <a
                href={googleUrl} target="_blank" rel="noreferrer"
                className="inline-flex h-11 items-center gap-1.5 rounded-lg border border-line-strong bg-surface px-4 text-[15px] font-semibold text-ink no-underline hover:bg-sunken"
              >
                Ouvrir dans Google Maps <ExternalLink size={15} aria-hidden="true" />
              </a>
            </div>

            {route.steps.length > 0 && (
              <div>
                <h3 className="text-[17px] text-ink">Étapes</h3>
                <ol className="mt-2 space-y-0.5">
                  {route.steps.map((step, index) => {
                    const current = following && progress?.stepIndex === index;
                    const done = following && progress !== null && index < progress.stepIndex;
                    return (
                      <li
                        key={index}
                        aria-current={current ? "step" : undefined}
                        className={`flex gap-3 rounded-md px-2 py-2 text-[15px] ${current ? "bg-water-soft" : ""} ${done ? "text-ink-3" : "text-ink"}`}
                      >
                        <span className="num w-5 shrink-0 text-right text-ink-3">{index + 1}</span>
                        <span className={`min-w-0 flex-1 ${current ? "font-semibold" : ""}`}>{step.instruction}</span>
                        {step.distance > 0 && <span className="num shrink-0 text-ink-2">{distance(step.distance)}</span>}
                      </li>
                    );
                  })}
                </ol>
              </div>
            )}

            <p className="text-[14px] text-ink-3">
              Le tracé s'arrête à la route la plus proche de la retenue ; les derniers mètres peuvent se faire hors piste.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
