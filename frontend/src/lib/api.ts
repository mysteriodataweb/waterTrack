// Client de l'API WaterTracker.
//
// En développement, VITE_API_URL reste vide : les appels partent en relatif
// (/api/...) et Vite les relaie vers le backend local (voir vite.config.ts).
// En production, VITE_API_URL pointe vers le backend déployé.
const BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");

export const API_DOCS_URL = `${BASE}/docs`;
export const BULLETIN_CSV_URL = `${BASE}/api/bulletin?format=csv`;

export type Status = "actif" | "à risque" | "tari" | "inconnu";
export type NavigationProfile = "driving-car" | "foot-walking" | "cycling-regular";
export type AdviceProfile = "ong" | "gouvernement" | "agent_terrain" | "communaute";

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface ApiWaterSource {
  id: number;
  longitude: number | null;
  latitude: number | null;
  zone: string | null;
  zone_detail: string | null;
  superficie_km2: number | null;
  ndwi_moyen: number | null;
  risk_score: number | null;
  status: string | null;
  date_analyse: string | null;
}

export interface ApiForecastHorizon {
  horizon: number;
  fill_pred: number;
  fill_lo80: number;
  fill_hi80: number;
  p_critical: number;
}

export interface ApiBulletinReservoir {
  reservoir_id: string;
  origin: "application" | "JRC";
  validation: "a_valider" | "valide" | "rejete";
  source_ids: number[];
  lat: number;
  lon: number;
  a_ref_ha: number | null;
  fill_now: number | null;
  fill_change_1m: number | null;
  area_ha: number | null;
  volume_m3: number | null;
  area_source: string | null;
  status: string;
  p_critical_max: number;
  forecast: ApiForecastHorizon[];
}

export interface ApiBulletin {
  issue_month: string;
  generated_at: string;
  critical_fill: number;
  model_version: string | null;
  n_reservoirs: number;
  status_counts: Record<string, number>;
  reservoirs: ApiBulletinReservoir[];
}

export interface ApiHistoryPoint {
  month: string;
  area_ha: number | null;
  fill: number | null;
  area_source: string;
  volume_m3: number | null;
  precip_mm: number | null;
}

export interface ApiHistory {
  reservoir_id: string;
  a_ref_ha: number | null;
  points: ApiHistoryPoint[];
}

export interface ApiAdvice {
  ndwi_actuel?: number;
  tendance?: number;
  vitesse_degradation?: string;
  date_tarissement?: string | null;
  confiance?: number;
  predictions?: Array<{ periode: string; probabilite_tarissement: number }>;
  recommandation?: string | null;
}

export interface ApiRouteStep {
  instruction: string;
  distance: number;
  duration: number;
  name?: string | null;
}

export interface ApiRoute {
  profile: NavigationProfile;
  distance: number;
  duration: number;
  /** Paires [longitude, latitude]. */
  geometry: Array<[number, number]>;
  steps: ApiRouteStep[];
}

export interface ApiReport {
  periode: string;
  nb_observations: number;
  periodes: Array<{ periode: string; ndwi_moyen: number; nb_sources: number }>;
}

export type ApiErrorKind = "network" | "timeout" | "http";

export class ApiError extends Error {
  kind: ApiErrorKind;
  status: number | null;

  constructor(kind: ApiErrorKind, message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
  }
}

export function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
  method?: "GET" | "POST";
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { signal, timeoutMs = 25_000, method = "GET", body } = options;

  // Délai maison : un backend en veille ne répond parfois ni succès ni erreur.
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort);

  try {
    const response = await fetch(`${BASE}${path}`, {
      method,
      signal: controller.signal,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });

    if (!response.ok) {
      let detail = "";
      try {
        const payload = await response.json();
        if (typeof payload?.detail === "string") detail = payload.detail;
      } catch {
        // Réponse d'erreur sans JSON (page HTML d'un proxy, par exemple).
      }
      throw new ApiError("http", detail || `Le serveur a répondu ${response.status}.`, response.status);
    }

    const contentType = response.headers.get("content-type") ?? "";
    if (!contentType.includes("json")) {
      // Typiquement : VITE_API_URL non défini en production, on reçoit index.html.
      throw new ApiError("http", "L'adresse de l'API n'est pas configurée (réponse inattendue).", response.status);
    }
    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted) throw new DOMException("Aborted", "AbortError");
    if (timedOut) throw new ApiError("timeout", "Le serveur met trop de temps à répondre.");
    throw new ApiError("network", "Le serveur de données est injoignable.");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}

/**
 * Le backend est hébergé sur une offre qui s'endort : le premier appel peut
 * demander près d'une minute. On réessaie tant que le serveur ne répond pas,
 * en prévenant l'interface pour qu'elle l'explique à l'utilisateur.
 */
export async function wakeAndFetch<T>(
  load: () => Promise<T>,
  { signal, onWaking, budgetMs = 75_000 }: { signal?: AbortSignal; onWaking?: () => void; budgetMs?: number } = {},
): Promise<T> {
  const deadline = Date.now() + budgetMs;
  for (;;) {
    try {
      return await load();
    } catch (error) {
      if (isAbort(error)) throw error;
      const retryable = error instanceof ApiError
        && (error.kind !== "http" || [502, 503, 504].includes(error.status ?? 0));
      if (!retryable || Date.now() > deadline) throw error;
      onWaking?.();
      await sleep(4000, signal);
    }
  }
}

/** Toutes les sources, page par page (l'API en renvoie 200 au plus par appel). */
export async function fetchAllSources(signal?: AbortSignal): Promise<ApiWaterSource[]> {
  const pageSize = 200;
  const items: ApiWaterSource[] = [];
  for (let page = 1; page <= 50; page += 1) {
    const payload = await request<{ total: number; items: ApiWaterSource[] }>(
      `/api/water-sources?page=${page}&page_size=${pageSize}`,
      { signal },
    );
    items.push(...payload.items);
    if (payload.items.length < pageSize || items.length >= payload.total) break;
  }
  return items;
}

/** Bulletin mensuel ; `null` si aucune prévision n'a encore été chargée côté serveur. */
export async function fetchBulletin(signal?: AbortSignal): Promise<ApiBulletin | null> {
  try {
    return await request<ApiBulletin>("/api/bulletin", { signal });
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

export function fetchHistory(reservoirId: string, signal?: AbortSignal): Promise<ApiHistory> {
  return request<ApiHistory>(`/api/reservoirs/${encodeURIComponent(reservoirId)}/history`, { signal });
}

export function fetchAdvice(sourceId: number, profile: AdviceProfile, signal?: AbortSignal): Promise<ApiAdvice> {
  // Prophet puis un modèle de langage : la réponse peut prendre une dizaine de secondes.
  return request<ApiAdvice>(`/api/water-sources/${sourceId}/prediction?profil=${profile}`, { signal, timeoutMs: 60_000 });
}

export function fetchRoute(
  start: GeoPoint,
  end: GeoPoint,
  profile: NavigationProfile,
  signal?: AbortSignal,
): Promise<ApiRoute> {
  return request<ApiRoute>("/api/navigation/route", {
    method: "POST",
    body: { start: { lat: start.lat, lng: start.lng }, end: { lat: end.lat, lng: end.lng }, profile },
    signal,
    timeoutMs: 60_000,
  });
}

export async function fetchPlaceName(point: GeoPoint, signal?: AbortSignal): Promise<string | null> {
  // Confort d'affichage uniquement : un échec ne doit jamais bloquer l'itinéraire.
  try {
    const params = new URLSearchParams({ lat: String(point.lat), lng: String(point.lng) });
    const place = await request<{ label: string }>(`/api/navigation/reverse?${params}`, { signal, timeoutMs: 10_000 });
    return place.label || null;
  } catch {
    return null;
  }
}

export function fetchReport(signal?: AbortSignal): Promise<ApiReport> {
  return request<ApiReport>("/api/report/summary", { signal });
}
