import { Bike, Car, Crosshair, Footprints, Loader2, LocateFixed, Navigation, Pause, Play, Route, Square, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchNavigationRoute, fetchReverseGeocode } from "../api";
import type { GeoPoint, NavigationPosition, NavigationProfile, NavigationRoute, Source } from "../types";

const profiles: Array<{ key: NavigationProfile; label: string; icon: typeof Car }> = [
  { key: "driving-car", label: "Route", icon: Car },
  { key: "foot-walking", label: "Marche", icon: Footprints },
  { key: "cycling-regular", label: "Velo", icon: Bike },
];

// Centre de Ouagadougou : origine de repli quand le GPS est indisponible.
const FALLBACK_ORIGIN = { lat: 12.3647, lng: -1.5221 };

// Le backend est heberge sur une offre gratuite qui se met en veille : le
// premier appel peut demander une cinquantaine de secondes. On borne quand
// meme l'attente pour ne jamais laisser l'interface bloquee indefiniment.
const ROUTE_TIMEOUT_MS = 60000;

function createTimeoutSignal(ms: number): AbortSignal | undefined {
  const ctor = AbortSignal as unknown as { timeout?: (ms: number) => AbortSignal };
  return typeof ctor.timeout === "function" ? ctor.timeout(ms) : undefined;
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.round(seconds))} s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${rest} min`;
}

export function PanelNavigation({
  sources,
  targetSource,
  actionNonce,
  onSelect,
  onRouteChange,
}: {
  sources: Source[];
  targetSource: Source | null;
  actionNonce: number;
  onSelect: (s: Source) => void;
  onRouteChange: (route: NavigationRoute | null) => void;
}) {
  const [position, setPosition] = useState<NavigationPosition | null>(null);
  const [placeName, setPlaceName] = useState<string | null>(null);
  const [route, setRoute] = useState<NavigationRoute | null>(null);
  const [profile, setProfile] = useState<NavigationProfile>("driving-car");
  const [loadingId, setLoadingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [originNotice, setOriginNotice] = useState<string | null>(null);
  const [fallbackTarget, setFallbackTarget] = useState<Source | null>(null);
  const [geoStatus, setGeoStatus] = useState<string | null>(null);

  const routeRef = useRef<NavigationRoute | null>(null);
  const watchRef = useRef<number | null>(null);
  const lastPositionRef = useRef<NavigationPosition | null>(null);
  const lastGeocodeRef = useRef<{ point: GeoPoint; time: number } | null>(null);

  const sorted = useMemo(() => [...sources].sort((a, b) => b.risk_score - a.risk_score).slice(0, 8), [sources]);

  useEffect(() => () => stopTracking(false), []);

  useEffect(() => {
    if (!targetSource || actionNonce === 0) return;
    guideTo(targetSource);
  }, [targetSource, actionNonce]);

  function commitRoute(nextRoute: NavigationRoute | null) {
    routeRef.current = nextRoute;
    setRoute(nextRoute);
    onRouteChange(nextRoute);
  }

  async function guideTo(source: Source, forcedOrigin?: NavigationPosition) {
    setError(null);
    setLoadingId(source.id);
    onSelect(source);
    stopTracking(false);

    try {
      // La position reelle est la regle. Si elle echoue, on n'invente PAS un
      // point de depart : on explique la cause et on laisse l'utilisateur
      // choisir explicitement un depart de substitution.
      let origin: NavigationPosition;
      if (forcedOrigin) {
        origin = forcedOrigin;
        setOriginNotice("Depart choisi manuellement : centre de Ouagadougou (position reelle indisponible).");
      } else {
        try {
          setGeoStatus("Recherche de ta position (GPS puis reseau)...");
          origin = await readCurrentPosition(lastPositionRef.current);
          setGeoStatus(null);
          setOriginNotice(null);
          setFallbackTarget(null);
        } catch (geoError) {
          setGeoStatus(null);
          setError(geoError instanceof Error ? geoError.message : "Position indisponible");
          setFallbackTarget(source);
          return;
        }
      }
      const currentPlace = await fetchPlaceName(origin);
      setPlaceName(currentPlace);
      setPosition(origin);

      const response = await fetchNavigationRoute({
        start: origin,
        end: { lat: source.lat, lng: source.lng },
        profile,
        signal: createTimeoutSignal(ROUTE_TIMEOUT_MS),
      });
      const nextRoute: NavigationRoute = {
        ...response,
        source,
        origin,
        destination: { lat: source.lat, lng: source.lng },
        currentPosition: origin,
        currentPlace,
        currentInstruction: response.steps[0]?.instruction ?? "Continuer",
        remainingDistance: response.distance,
        remainingDuration: response.duration,
        activeStepIndex: 0,
        tracking: false,
      };

      commitRoute(nextRoute);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de calculer l'itineraire");
    } finally {
      setLoadingId(null);
    }
  }

  // Changer de mode de transport recalcule l'itineraire si une destination est prete.
  async function handleProfileChange(nextProfile: NavigationProfile) {
    setProfile(nextProfile);
    const current = routeRef.current;
    if (!current) return;
    setError(null);
    try {
      const response = await fetchNavigationRoute({
        start: current.origin,
        end: { lat: current.destination.lat, lng: current.destination.lng },
        profile: nextProfile,
      });
      commitRoute({
        ...current,
        ...response,
        currentInstruction: response.steps[0]?.instruction ?? "Continuer",
        remainingDistance: response.distance,
        remainingDuration: response.duration,
        activeStepIndex: 0,
        tracking: false,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Impossible de recalculer l'itineraire");
    }
  }

  function startNavigation() {
    startTracking();
  }

  function stopNavigation() {
    stopTracking(false);
    const current = routeRef.current;
    if (current) {
      // Revient a l'ecran "pret" (Start) en gardant l'itineraire affiche.
      commitRoute({
        ...current,
        tracking: false,
        currentPosition: { ...current.origin, timestamp: Date.now() },
        remainingDistance: current.distance,
        remainingDuration: current.duration,
        activeStepIndex: 0,
        currentInstruction: current.steps[0]?.instruction ?? "Continuer",
      });
    }
  }

  function startTracking() {
    if (!navigator.geolocation) {
      setError("La geolocalisation n'est pas supportee par ce navigateur");
      return;
    }

    stopTracking(false);
    watchRef.current = navigator.geolocation.watchPosition(
      (gpsPosition) => handleLivePosition(toNavigationPosition(gpsPosition, lastPositionRef.current)),
      () => setError("Position GPS indisponible. Verifie l'autorisation du navigateur."),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 4000 },
    );

    const currentRoute = routeRef.current;
    if (currentRoute) commitRoute({ ...currentRoute, tracking: true });
  }

  function stopTracking(updateRoute = true) {
    if (watchRef.current !== null) {
      navigator.geolocation.clearWatch(watchRef.current);
      watchRef.current = null;
    }

    if (updateRoute && routeRef.current) {
      commitRoute({ ...routeRef.current, tracking: false });
    }
  }

  function clearRoute() {
    stopTracking(false);
    lastPositionRef.current = null;
    lastGeocodeRef.current = null;
    setPosition(null);
    setPlaceName(null);
    commitRoute(null);
  }

  function handleLivePosition(livePosition: NavigationPosition) {
    const currentRoute = routeRef.current;
    lastPositionRef.current = livePosition;
    setPosition(livePosition);

    if (!currentRoute) return;

    const progress = computeProgress(currentRoute, livePosition);
    const updatedRoute: NavigationRoute = {
      ...currentRoute,
      currentPosition: livePosition,
      remainingDistance: progress.remainingDistance,
      remainingDuration: progress.remainingDuration,
      currentInstruction: progress.currentInstruction,
      activeStepIndex: progress.activeStepIndex,
      tracking: true,
    };
    commitRoute(updatedRoute);
    refreshPlaceName(livePosition);
  }

  async function refreshPlaceName(point: GeoPoint) {
    const now = Date.now();
    const last = lastGeocodeRef.current;
    if (last && now - last.time < 20000 && distanceMeters(last.point, point) < 70) return;

    lastGeocodeRef.current = { point, time: now };
    try {
      const currentPlace = await fetchPlaceName(point);
      setPlaceName(currentPlace);
      if (routeRef.current) {
        commitRoute({ ...routeRef.current, currentPlace });
      }
    } catch {
      // Keep the last known place if reverse geocoding temporarily fails.
    }
  }

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#9fc9ea]">
        <Route className="size-4" /> Navigation terrain
      </div>

      <div className="rounded-md border border-[#2a3140] bg-[#151a21] p-3 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs uppercase tracking-[0.14em] text-[#a3afbd]">Position live</span>
          <button
            onClick={async () => {
              setError(null);
              try {
                const current = await readCurrentPosition(lastPositionRef.current);
                lastPositionRef.current = current;
                setPosition(current);
                refreshPlaceName(current);
              } catch (err) {
                setError(err instanceof Error ? err.message : "Position GPS indisponible");
              }
            }}
            className="flex items-center gap-1 rounded border border-[#3a424d] px-2 py-1 text-[11px] text-[#9fc9ea] transition hover:bg-[#20262d]"
          >
            <Crosshair className="size-3" /> Actualiser
          </button>
        </div>

        <div>
          <div className="text-sm font-medium text-white">
            {position ? `${position.lat.toFixed(5)}, ${position.lng.toFixed(5)}` : "Autorisation GPS requise"}
          </div>
          <div className="mt-1 text-xs text-[#a3afbd]">
            {route?.currentPlace ?? placeName ?? "Le nom du lieu apparaitra apres le guidage"}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {profiles.map((item) => (
          <button
            key={item.key}
            onClick={() => handleProfileChange(item.key)}
            className={`flex items-center justify-center gap-1.5 rounded-md border px-3 py-2 text-xs font-medium transition ${
              profile === item.key
                ? "border-[#9fc9ea] bg-[#20262d] text-white"
                : "border-[#2a3140] text-[#a3afbd] hover:bg-[#171b22] hover:text-white"
            }`}
          >
            <item.icon className="size-3.5" /> {item.label}
          </button>
        ))}
      </div>

      {route && !route.tracking && (
        <div className="rounded-md border border-[#3a424d]/80 bg-[#171b22] p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.14em] text-[#9fc9ea]">Itineraire vers {route.source.label}</div>
              <div className="mt-1 text-[11px] text-[#a3afbd]">
                {(() => { const item = profiles.find((p) => p.key === profile); return item ? <item.icon className="mr-1 inline size-3" /> : null; })()}
                {profiles.find((p) => p.key === profile)?.label}
              </div>
            </div>
            <button
              onClick={clearRoute}
              className="flex size-8 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white"
              aria-label="Arreter l'itineraire"
            >
              <Trash2 className="size-4" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Metric label="Distance" value={`${((route.remainingDistance ?? route.distance) / 1000).toFixed(1)} km`} />
            <Metric label="Temps estime" value={formatDuration(route.remainingDuration ?? route.duration)} />
          </div>

          <button
            onClick={startNavigation}
            className="flex w-full items-center justify-center gap-2 rounded-md bg-[#9fc9ea] py-3 text-sm font-bold tracking-widest text-[#101318] transition hover:bg-[#9fc9ea]"
          >
            <Play className="size-4" /> DEMARRER LA NAVIGATION
          </button>
        </div>
      )}

      {route && route.tracking && (
        <div className="rounded-md border border-[#3a424d]/80 bg-[#171b22] p-4 space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.14em] text-[#9fc9ea]">Guidage vers {route.source.label}</div>
              <div className="mt-1 text-[11px] text-[#a3afbd]">
                {route.tracking ? "Suivi GPS actif" : "Suivi GPS en pause"}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => route.tracking ? stopTracking() : startTracking()}
                className="flex size-8 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white"
                aria-label={route.tracking ? "Mettre en pause" : "Reprendre"}
              >
                {route.tracking ? <Pause className="size-4" /> : <Play className="size-4" />}
              </button>
              <button onClick={clearRoute} className="flex size-8 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white" aria-label="Arreter l'itineraire">
                <Trash2 className="size-4" />
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Metric label="Restant" value={`${((route.remainingDistance ?? route.distance) / 1000).toFixed(1)} km`} />
            <Metric label="Temps" value={formatDuration(route.remainingDuration ?? route.duration)} />
          </div>

          <div className="rounded-md border border-[#2a3140] bg-[#151a21] p-3">
            <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-[#a3afbd]">
              <LocateFixed className="size-3" /> Instruction actuelle
            </div>
            <div className="text-sm font-medium text-white">{route.currentInstruction ?? route.steps[0]?.instruction ?? "Continuer"}</div>
          </div>

          <button
            onClick={stopNavigation}
            className="flex w-full items-center justify-center gap-2 rounded-md border border-[#ff6b6b]/60 bg-[#3a151a] py-3 text-sm font-bold tracking-widest text-[#ff9b9b] transition hover:bg-[#4d1d23]"
          >
            <Square className="size-4" /> STOP NAVIGATION
          </button>
        </div>
      )}

      <div className="space-y-2">
        <div className="text-xs uppercase tracking-[0.14em] text-[#a3afbd]">Sources prioritaires</div>
        {sorted.map((source) => (
          <div key={source.id} className="flex items-center justify-between gap-3 rounded-md border border-[#2a3140] bg-[#151a21] p-3">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-white">{source.label}</div>
              <div className="mt-1 text-[11px] text-[#a3afbd]">{(source.zone_detail ?? source.zone ?? "Ouagadougou")} · {source.statut} · risque {Math.round(source.risk_score * 100)}%</div>
            </div>
            <button
              onClick={() => guideTo(source)}
              disabled={loadingId !== null}
              className="flex min-w-[92px] items-center justify-center gap-1 rounded-md border border-[#9fc9ea]/60 px-3 py-2 text-xs font-medium text-[#9fc9ea] transition hover:bg-[#20262d] disabled:cursor-wait disabled:opacity-60"
            >
              {loadingId === source.id ? <Loader2 className="size-3 animate-spin" /> : <Navigation className="size-3" />}
              Guider
            </button>
          </div>
        ))}
      </div>

      {geoStatus && !error && (
        <div className="flex items-center gap-2 rounded-md border border-[#3a424d] bg-[#1d2229] p-3 text-sm text-[#a3afbd]">
          <Loader2 className="size-4 animate-spin text-[#9fc9ea]" />
          {geoStatus}
        </div>
      )}

      {originNotice && !error && (
        <div className="rounded-md border border-[#7a6220] bg-[#251f0f] p-3 text-sm text-[#e3b341]">
          {originNotice}
        </div>
      )}

      {error && (
        <div className="space-y-3 rounded-md border border-[#7f3535] bg-[#2a1115] p-3 text-sm text-[#ffb4b4]">
          <div>{error}</div>
          {fallbackTarget && (
            <div className="flex flex-wrap gap-2">
              <button
                onClick={() => guideTo(fallbackTarget)}
                className="rounded-md border border-[#9fc9ea]/60 px-3 py-2 text-xs font-medium text-[#9fc9ea] transition hover:bg-[#20262d]"
              >
                Reessayer avec ma position
              </button>
              <button
                onClick={() => guideTo(fallbackTarget, {
                  ...FALLBACK_ORIGIN, accuracy: undefined, heading: 0, speed: null, timestamp: Date.now(),
                })}
                className="rounded-md border border-[#3a424d] px-3 py-2 text-xs font-medium text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white"
              >
                Partir du centre de Ouagadougou
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#2a3140] bg-[#151a21] p-3">
      <div className="text-[10px] uppercase tracking-[0.14em] text-[#a3afbd]">{label}</div>
      <div className="mt-1 text-lg font-semibold text-[#9fc9ea]">{value}</div>
    </div>
  );
}

/** Un seul essai de geolocalisation, avec garde-temps qui ne peut pas rester bloque. */
function requestPosition(options: PositionOptions, timeoutMs: number): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    // Garde-temps maison : si l'utilisateur IGNORE la fenetre de permission
    // (fermeture sans repondre), plusieurs navigateurs n'appellent aucun des
    // deux callbacks et l'option `timeout` native ne se declenche pas. Sans
    // ce garde-fou la promesse ne se resout jamais.
    let settled = false;
    const finish = (action: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      action();
    };

    const timer = setTimeout(
      () => finish(() => reject(new GeolocationPositionErrorLike(3))),
      timeoutMs,
    );

    navigator.geolocation.getCurrentPosition(
      (position) => finish(() => resolve(position)),
      (error) => finish(() => reject(error)),
      options,
    );
  });
}

/** Erreur equivalente a GeolocationPositionError (code 3 = TIMEOUT). */
class GeolocationPositionErrorLike extends Error {
  code: number;
  constructor(code: number) {
    super("Geolocalisation indisponible");
    this.code = code;
  }
}

async function readCurrentPosition(previous: NavigationPosition | null): Promise<NavigationPosition> {
  if (!navigator.geolocation) {
    throw new Error("La geolocalisation n'est pas supportee par ce navigateur");
  }
  if (!window.isSecureContext) {
    throw new Error("La geolocalisation exige une connexion securisee (HTTPS)");
  }

  // Deux tentatives : d'abord le GPS precis, puis - s'il echoue - le
  // positionnement reseau (Wi-Fi / IP), bien plus fiable sur un poste fixe
  // ou en interieur. C'est l'echec de la 1re tentative, seule utilisee
  // auparavant, qui declenchait le repli sur une position simulee.
  const attempts: Array<{ options: PositionOptions; timeout: number }> = [
    { options: { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }, timeout: 11000 },
    { options: { enableHighAccuracy: false, timeout: 20000, maximumAge: 300000 }, timeout: 21000 },
  ];

  let lastError: unknown = null;
  for (const attempt of attempts) {
    try {
      const position = await requestPosition(attempt.options, attempt.timeout);
      return toNavigationPosition(position, previous);
    } catch (error) {
      lastError = error;
      // Permission explicitement refusee : reessayer ne sert a rien.
      if (typeof error === "object" && error !== null && (error as { code?: number }).code === 1) break;
    }
  }

  throw new Error(await describeGeolocationError(lastError));
}

/** Message precis selon la cause reelle, plutot qu'un texte generique. */
async function describeGeolocationError(error: unknown): Promise<string> {
  const code = typeof error === "object" && error !== null ? (error as { code?: number }).code : undefined;

  // Cause reelle la plus frequente sur telephone : la page est ouverte dans
  // le navigateur integre d'une app (WhatsApp, Messenger, Instagram, TikTok,
  // Telegram...) qui bloque la geolocalisation.
  const webview = detectEmbeddedBrowser();
  if (webview) {
    return `${webview} Pour utiliser l'itineraire, ouvre ce lien dans un vrai navigateur (Chrome ou Safari).`;
  }

  if (code === 1) {
    return "Acces a la position refuse. Autorise la localisation pour ce site (icone de cadenas dans la barre d'adresse, ou Reglages > Donnees du site / > Localisation), puis reessaie.";
  }

  // L'API Permissions permet de distinguer un refus memorise d'une panne.
  try {
    const status = await navigator.permissions?.query({ name: "geolocation" as PermissionName });
    if (status?.state === "denied") {
      return "La localisation est bloquee pour ce site. Sur iPhone : Reglages > Safari > Localisation > Autoriser. Sur Android : icone cadenas > Autorisations > Localisation. Puis reessaie.";
    }
  } catch {
    // API Permissions indisponible : on continue avec le message generique.
  }

  if (code === 2) return "Position indisponible : aucun signal de localisation. Active le GPS ou le Wi-Fi, puis reessaie.";
  if (code === 3) return "Delai depasse pour obtenir la position. Reessaie, de preference a l'exterieur ou avec le Wi-Fi actif.";
  return "Impossible d'obtenir ta position. Verifie que la localisation est activee, puis reessaie.";
}

/** Lance la page dans un environnement qui bloque la geolocalisation ? */
function detectEmbeddedBrowser(): string | null {
  // Page ouverte dans un cadre (<iframe>`geolocation` non accordé) : Chrome
  // et Android bloquent la géolocalisation des iframes sans autorisation.
  try {
    if (window.self !== window.top) {
      return "Cette page est ouverte dans un encart integre qui ne permet pas la geolocalisation.";
    }
  } catch {
    return "Cette page est ouverte dans un cadre integre qui ne permet pas la geolocalisation.";
  }

  // Navigateurs embarqués des messageries / réseaux sociaux (WebView).
  const ua = navigator.userAgent || "";
  const embedded = /WhatsApp|Instagram|FBAN|FBAV|TikTok|Telegram|MicroMessenger|snapchat|Line\/|JSBridge|okhttp|; ?wv\)?/i.test(ua);
  if (embedded) {
    return "Cette page s'ouvre dans le navigateur integre d'une application, qui bloque souvent la position.";
  }

  return null;
}

function toNavigationPosition(position: GeolocationPosition, previous: NavigationPosition | null): NavigationPosition {
  const current = {
    lat: position.coords.latitude,
    lng: position.coords.longitude,
  };
  const computedHeading = previous && distanceMeters(previous, current) > 2 ? bearingDegrees(previous, current) : previous?.heading ?? 0;

  return {
    ...current,
    accuracy: position.coords.accuracy,
    heading: typeof position.coords.heading === "number" && Number.isFinite(position.coords.heading)
      ? position.coords.heading
      : computedHeading,
    speed: position.coords.speed,
    timestamp: position.timestamp,
  };
}

async function fetchPlaceName(point: GeoPoint): Promise<string> {
  // Le nom du lieu est un confort d'affichage : s'il echoue (quota du
  // geocodeur, reseau...), on retombe sur les coordonnees plutot que de
  // faire echouer tout le calcul d'itineraire.
  try {
    const place = await fetchReverseGeocode(point);
    return place.label;
  } catch {
    return `${point.lat.toFixed(4)}, ${point.lng.toFixed(4)}`;
  }
}

function computeProgress(route: NavigationRoute, position: GeoPoint) {
  const nearestIndex = nearestGeometryIndex(route.geometry, position);
  const remainingDistance = Math.min(
    route.distance,
    distanceFromIndexToEnd(route.geometry, nearestIndex, position),
  );
  const remainingDuration = route.distance > 0 ? route.duration * (remainingDistance / route.distance) : route.duration;
  const activeStepIndex = route.steps.findIndex((step) => {
    if (!step.way_points) return false;
    return nearestIndex <= step.way_points[1];
  });
  const currentStep = route.steps[Math.max(0, activeStepIndex)];

  return {
    remainingDistance,
    remainingDuration,
    activeStepIndex: Math.max(0, activeStepIndex),
    currentInstruction: currentStep?.instruction ?? "Continuer",
  };
}

function nearestGeometryIndex(geometry: Array<[number, number]>, point: GeoPoint): number {
  let bestIndex = 0;
  let bestDistance = Number.POSITIVE_INFINITY;

  geometry.forEach(([lng, lat], index) => {
    const distance = distanceMeters(point, { lat, lng });
    if (distance < bestDistance) {
      bestDistance = distance;
      bestIndex = index;
    }
  });

  return bestIndex;
}

function distanceFromIndexToEnd(geometry: Array<[number, number]>, startIndex: number, point: GeoPoint): number {
  if (geometry.length === 0) return 0;
  const [nearestLng, nearestLat] = geometry[startIndex];
  let total = distanceMeters(point, { lat: nearestLat, lng: nearestLng });

  for (let i = startIndex; i < geometry.length - 1; i += 1) {
    const [lngA, latA] = geometry[i];
    const [lngB, latB] = geometry[i + 1];
    total += distanceMeters({ lat: latA, lng: lngA }, { lat: latB, lng: lngB });
  }

  return total;
}

function distanceMeters(a: GeoPoint, b: GeoPoint): number {
  const radius = 6371000;
  const lat1 = degreesToRadians(a.lat);
  const lat2 = degreesToRadians(b.lat);
  const deltaLat = degreesToRadians(b.lat - a.lat);
  const deltaLng = degreesToRadians(b.lng - a.lng);
  const h = Math.sin(deltaLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;
  return 2 * radius * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

function bearingDegrees(a: GeoPoint, b: GeoPoint): number {
  const lat1 = degreesToRadians(a.lat);
  const lat2 = degreesToRadians(b.lat);
  const deltaLng = degreesToRadians(b.lng - a.lng);
  const y = Math.sin(deltaLng) * Math.cos(lat2);
  const x = Math.cos(lat1) * Math.sin(lat2) - Math.sin(lat1) * Math.cos(lat2) * Math.cos(deltaLng);
  return (radiansToDegrees(Math.atan2(y, x)) + 360) % 360;
}

function degreesToRadians(value: number): number {
  return (value * Math.PI) / 180;
}

function radiansToDegrees(value: number): number {
  return (value * 180) / Math.PI;
}
