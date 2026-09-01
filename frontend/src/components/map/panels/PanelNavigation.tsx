import { Bike, Car, Crosshair, Footprints, Loader2, LocateFixed, Navigation, Pause, Play, Route, Square, Trash2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { fetchNavigationRoute, fetchReverseGeocode } from "../api";
import type { GeoPoint, NavigationPosition, NavigationProfile, NavigationRoute, Source } from "../types";

const profiles: Array<{ key: NavigationProfile; label: string; icon: typeof Car }> = [
  { key: "driving-car", label: "Route", icon: Car },
  { key: "foot-walking", label: "Marche", icon: Footprints },
  { key: "cycling-regular", label: "Velo", icon: Bike },
];

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

  async function guideTo(source: Source) {
    setError(null);
    setLoadingId(source.id);
    onSelect(source);
    stopTracking(false);

    try {
      const origin = await readCurrentPosition(lastPositionRef.current);
      const currentPlace = await fetchPlaceName(origin);
      setPlaceName(currentPlace);
      setPosition(origin);

      const response = await fetchNavigationRoute({
        start: origin,
        end: { lat: source.lat, lng: source.lng },
        profile,
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

      {error && (
        <div className="rounded-md border border-[#7f3535] bg-[#2a1115] p-3 text-sm text-[#ffb4b4]">
          {error}
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

function readCurrentPosition(previous: NavigationPosition | null): Promise<NavigationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("La geolocalisation n'est pas supportee par ce navigateur"));
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (position) => resolve(toNavigationPosition(position, previous)),
      () => reject(new Error("Autorise l'acces a ta position GPS pour calculer l'itineraire")),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 },
    );
  });
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
  const place = await fetchReverseGeocode(point);
  return place.label;
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
