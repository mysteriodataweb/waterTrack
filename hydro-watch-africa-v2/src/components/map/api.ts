import type { GeoPoint, NavigationProfile, NavigationStep, Source, Status } from "./types";

type BackendGeometry = {
  type: string;
  coordinates: unknown;
};

type BackendWaterSource = {
  id: number;
  geometry: BackendGeometry | null;
  longitude: number | null;
  latitude: number | null;
  zone: string | null;
  zone_detail: string | null;
  superficie_km2: number | null;
  ndwi_moyen: number | null;
  risk_score: number | null;
  status: string | null;
  date_analyse: string | null;
};

type PaginatedSourcesResponse = {
  total: number;
  page: number;
  page_size: number;
  items: BackendWaterSource[];
};

export type PredictionProfile = "ong" | "gouvernement" | "agent_terrain" | "communaute";

export type SourcePrediction = {
  water_source?: number;
  ndwi_actuel?: number;
  tendance?: number;
  vitesse_degradation?: string;
  date_tarissement?: string | null;
  confiance?: number;
  predictions?: Array<{
    periode: string;
    ndwi_predit: number;
    ndwi_min: number;
    ndwi_max: number;
    probabilite_tarissement: number;
  }>;
  recommandation?: string;
  recommandations?: Record<string, string>;
  erreur?: string;
};

export type NavigationRouteResponse = {
  profile: NavigationProfile;
  distance: number;
  duration: number;
  geometry: Array<[number, number]>;
  steps: NavigationStep[];
};

export type ReverseGeocodeResponse = {
  label: string;
  name?: string | null;
  street?: string | null;
  locality?: string | null;
  region?: string | null;
  country?: string | null;
};

export type ReportPeriod = {
  periode: string;
  ndwi_moyen: number;
  nb_sources: number;
};

export type ReportTopSource = {
  id: number;
  zone_detail?: string | null;
  status: string;
  risk_score: number;
  ndwi_moyen?: number | null;
};

export type ReportSummary = {
  periode: string;
  date_generation: string;
  total_sources: number;
  statut: Record<string, number>;
  superficie_totale_km2: number;
  ndwi_moyen_global: number | null;
  nb_observations: number;
  periodes: ReportPeriod[];
  zones: Array<{ zone: string; count: number }>;
  top_risque: ReportTopSource[];
};

const configuredApiUrl = import.meta.env.VITE_API_URL?.replace(/\/$/, "");
const API_BASE_URLS = configuredApiUrl
  ? [configuredApiUrl]
  : ["http://127.0.0.1:8000", "http://localhost:8000"];

export async function fetchWaterSources(signal?: AbortSignal): Promise<Source[]> {
  let lastError: unknown = null;

  for (const baseUrl of API_BASE_URLS) {
    try {
      const response = await fetch(`${baseUrl}/api/water-sources`, { signal });

      if (!response.ok) {
        throw new Error(`API WaterTracker indisponible (${response.status})`);
      }

      const payload = await response.json() as PaginatedSourcesResponse;
      const items = Array.isArray(payload) ? payload as unknown as BackendWaterSource[] : payload.items;
      const parsed = items.map(toSource).filter((source): source is Source => source !== null);
      return applyZoneLabels(parsed);
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      lastError = err;
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Impossible de joindre l'API WaterTracker");
}

export async function fetchSourcePrediction(
  sourceId: number,
  profile: PredictionProfile,
  signal?: AbortSignal,
): Promise<SourcePrediction> {
  let lastError: unknown = null;

  for (const baseUrl of API_BASE_URLS) {
    try {
      const response = await fetch(
        `${baseUrl}/api/water-sources/${sourceId}/prediction?profil=${profile}`,
        { signal },
      );
      const payload = await response.json();

      if (!response.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : `Prediction indisponible (${response.status})`;
        throw new Error(detail);
      }

      return payload as SourcePrediction;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      lastError = err;
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Impossible de joindre le service de prediction");
}

export async function fetchNavigationRoute({
  start,
  end,
  profile,
  signal,
}: {
  start: GeoPoint;
  end: GeoPoint;
  profile: NavigationProfile;
  signal?: AbortSignal;
}): Promise<NavigationRouteResponse> {
  let lastError: unknown = null;

  for (const baseUrl of API_BASE_URLS) {
    try {
      const response = await fetch(`${baseUrl}/api/navigation/route`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start, end, profile }),
        signal,
      });
      const payload = await response.json();

      if (!response.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : `Navigation indisponible (${response.status})`;
        throw new Error(detail);
      }

      return payload as NavigationRouteResponse;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      lastError = err;
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Impossible de joindre le service de navigation");
}

export async function fetchReverseGeocode(
  point: GeoPoint,
  signal?: AbortSignal,
): Promise<ReverseGeocodeResponse> {
  let lastError: unknown = null;
  const params = new URLSearchParams({
    lat: point.lat.toString(),
    lng: point.lng.toString(),
  });

  for (const baseUrl of API_BASE_URLS) {
    try {
      const response = await fetch(`${baseUrl}/api/navigation/reverse?${params.toString()}`, { signal });
      const payload = await response.json();

      if (!response.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : `Position indisponible (${response.status})`;
        throw new Error(detail);
      }

      return payload as ReverseGeocodeResponse;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      lastError = err;
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Impossible de trouver le nom du lieu actuel");
}

export async function fetchReportSummary(signal?: AbortSignal): Promise<ReportSummary> {
  let lastError: unknown = null;

  for (const baseUrl of API_BASE_URLS) {
    try {
      const response = await fetch(`${baseUrl}/api/report/summary`, { signal });
      const payload = await response.json();

      if (!response.ok) {
        const detail = typeof payload?.detail === "string" ? payload.detail : `Rapport indisponible (${response.status})`;
        throw new Error(detail);
      }

      return payload as ReportSummary;
    } catch (err) {
      if (err instanceof DOMException && err.name === "AbortError") throw err;
      lastError = err;
    }
  }

  throw lastError instanceof Error
    ? lastError
    : new Error("Impossible de joindre le service de rapport");
}

function toSource(source: BackendWaterSource): Source | null {
  // Privilégier les colonnes explicites du backend, sinon centroid de la géométrie.
  let lat: number | null = source.latitude ?? null;
  let lng: number | null = source.longitude ?? null;
  if (lat === null || lng === null) {
    const centroid = getCentroid(source.geometry);
    if (!centroid) return null;
    lng = centroid.lng;
    lat = centroid.lat;
  }

  const riskScore = clamp01(source.risk_score ?? inferRiskFromNdwi(source.ndwi_moyen));

  return {
    id: source.id,
    lat,
    lng,
    zone: source.zone ?? undefined,
    zone_detail: source.zone_detail?.toLowerCase() ?? undefined,
    statut: normalizeStatus(source.status, riskScore),
    ndwi: source.ndwi_moyen ?? 0,
    risk_score: riskScore,
    superficie: source.superficie_km2 ?? estimateAreaKm2(source.geometry),
    tarissement_estime: source.date_analyse ?? undefined,
    label: `#${source.id}`,
  };
}

/** Numérote les sources par zone précise : kadiogo-1, kadiogo-2, oubritenga-1... */
function applyZoneLabels(sources: Source[]): Source[] {
  const counters = new Map<string, number>();
  return [...sources]
    .sort((a, b) => a.id - b.id)
    .map((source) => {
      const zone = normalizeZoneKey(source.zone_detail ?? source.zone ?? "ouagadougou");
      const index = (counters.get(zone) ?? 0) + 1;
      counters.set(zone, index);
      const finalZone = source.zone_detail?.toLowerCase() || zone;
      return { ...source, label: `${finalZone}-${index}` };
    });
}

function normalizeZoneKey(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function normalizeStatus(status: string | null, riskScore: number): Status {
  const normalized = (status ?? "").toLowerCase();
  if (normalized.includes("tari")) return "tari";
  if (normalized.includes("risque")) return "à risque";
  if (normalized.includes("actif")) return "actif";

  if (riskScore >= 0.6) return "tari";
  if (riskScore >= 0.3) return "à risque";
  return "actif";
}

function getCentroid(geometry: BackendGeometry | null): { lat: number; lng: number } | null {
  const points = collectLngLatPairs(geometry?.coordinates);
  if (points.length === 0) return null;

  const sums = points.reduce(
    (acc, [lng, lat]) => ({ lng: acc.lng + lng, lat: acc.lat + lat }),
    { lng: 0, lat: 0 },
  );

  return {
    lng: sums.lng / points.length,
    lat: sums.lat / points.length,
  };
}

function collectLngLatPairs(value: unknown): Array<[number, number]> {
  if (!Array.isArray(value)) return [];

  if (
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number"
  ) {
    return [[value[0], value[1]]];
  }

  return value.flatMap(collectLngLatPairs);
}

function estimateAreaKm2(geometry: BackendGeometry | null): number {
  if (!geometry || geometry.type !== "Polygon" || !Array.isArray(geometry.coordinates)) {
    return 0;
  }

  const ring = geometry.coordinates[0];
  const points = collectLngLatPairs(ring);
  if (points.length < 4) return 0;

  const meanLat = points.reduce((sum, [, lat]) => sum + lat, 0) / points.length;
  const kmPerLng = 111.32 * Math.cos((meanLat * Math.PI) / 180);
  const projected = points.map(([lng, lat]) => [lng * kmPerLng, lat * 110.57] as const);

  let area = 0;
  for (let i = 0; i < projected.length; i += 1) {
    const [x1, y1] = projected[i];
    const [x2, y2] = projected[(i + 1) % projected.length];
    area += x1 * y2 - x2 * y1;
  }

  return Math.abs(area) / 2;
}

function inferRiskFromNdwi(ndwi: number | null): number {
  if (ndwi === null) return 0.5;
  if (ndwi > 0.4) return 0.1;
  if (ndwi > 0.2) return 0.5;
  return 0.9;
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}
