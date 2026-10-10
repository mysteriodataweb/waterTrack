import type { ApiBulletin, ApiWaterSource, Status } from "./api";
import { addMonths, fold } from "./format";

export type { Status };

export interface ForecastPoint {
  horizon: number;
  /** Mois visé, "AAAA-MM". */
  month: string;
  fill: number;
  low: number;
  high: number;
  /** Probabilité de passer sous le seuil critique. */
  pCritical: number;
}

/**
 * Un plan d'eau affiché à l'utilisateur. La plupart sont des retenues suivies
 * chaque mois (avec prévision) ; quelques points d'eau de l'inventaire ne sont
 * rattachés à aucune retenue modélisée et n'ont donc pas de prévision.
 */
export interface Site {
  key: string;
  reservoirId: string | null;
  sourceIds: number[];
  name: string;
  zone: string | null;
  lat: number;
  lng: number;
  status: Status;
  fillNow: number | null;
  fillChange: number | null;
  areaHa: number | null;
  refAreaHa: number | null;
  volumeM3: number | null;
  pCriticalMax: number | null;
  forecast: ForecastPoint[];
  /** Plan d'eau repéré automatiquement (catalogue JRC) et pas encore confirmé par un gestionnaire. */
  toValidate: boolean;
  origin: "application" | "JRC" | null;
  ndwi: number | null;
}

export interface Shape {
  /** Anneaux extérieurs en [lat, lng], prêts pour Leaflet. */
  rings: Array<Array<[number, number]>>;
  name: string | null;
}

export type Shapes = Map<number, Shape>;

export const STATUS_ORDER: Status[] = ["tari", "à risque", "actif", "inconnu"];

export const STATUS_META: Record<Status, {
  label: string;
  plural: string;
  hint: string;
  color: string;
  ink: string;
  soft: string;
}> = {
  tari: {
    label: "À sec",
    plural: "À sec",
    hint: "Remplissage prévu quasi nul le mois prochain",
    color: "#b3261e",
    ink: "#8f1d17",
    soft: "#f9e4e2",
  },
  "à risque": {
    label: "À risque",
    plural: "À risque",
    hint: "Plus d'une chance sur deux de passer sous le seuil critique",
    color: "#c27c0e",
    ink: "#875306",
    soft: "#fbefd9",
  },
  actif: {
    label: "Niveau normal",
    plural: "Niveau normal",
    hint: "Pas d'alerte pour le mois prochain",
    color: "#0e8a5f",
    ink: "#0a6647",
    soft: "#e1f3ec",
  },
  inconnu: {
    label: "Non évalué",
    plural: "Non évalués",
    hint: "Pas de prévision disponible pour ce point d'eau",
    color: "#6b7684",
    ink: "#4d5661",
    soft: "#eceff1",
  },
};

// Provinces de la zone suivie, avec leur orthographe officielle.
const ZONE_NAMES: Record<string, string> = {
  kadiogo: "Kadiogo",
  oubritenga: "Oubritenga",
  bazega: "Bazèga",
  kourweogo: "Kourwéogo",
  boulkiemde: "Boulkiemdé",
  ouagadougou: "Ouagadougou",
  ganzourgou: "Ganzourgou",
};

// Étiquettes génériques d'OpenStreetMap, qui ne sont pas des noms propres.
const GENERIC_OSM_NAMES = new Set(["water", "reservoir", "basin", "pond", "river", "lake", "wetland"]);

export function zoneLabel(raw: string | null | undefined): string | null {
  const value = raw?.trim();
  if (!value) return null;
  return ZONE_NAMES[fold(value)] ?? value.charAt(0).toUpperCase() + value.slice(1);
}

export function normalizeStatus(raw: string | null | undefined): Status {
  const value = (raw ?? "").toLowerCase();
  if (value.includes("tari")) return "tari";
  if (value.includes("risque")) return "à risque";
  if (value.includes("actif")) return "actif";
  return "inconnu";
}

export function parseShapes(geojson: unknown): Shapes {
  const shapes: Shapes = new Map();
  const features = (geojson as { features?: unknown[] } | null)?.features;
  if (!Array.isArray(features)) return shapes;

  for (const raw of features) {
    const feature = raw as {
      properties?: { source_id?: number; name?: string | null };
      geometry?: { type?: string; coordinates?: unknown } | null;
    };
    const id = feature.properties?.source_id;
    if (typeof id !== "number" || !feature.geometry) continue;

    const polygons = feature.geometry.type === "Polygon"
      ? [feature.geometry.coordinates]
      : feature.geometry.type === "MultiPolygon" && Array.isArray(feature.geometry.coordinates)
        ? feature.geometry.coordinates
        : [];

    const rings: Shape["rings"] = [];
    for (const polygon of polygons as unknown[]) {
      const outer = Array.isArray(polygon) ? polygon[0] : null;
      if (!Array.isArray(outer) || outer.length < 4) continue;
      rings.push(outer.map((pair: [number, number]) => [pair[1], pair[0]]));
    }
    if (rings.length === 0) continue;

    const osmName = feature.properties?.name?.trim() ?? "";
    shapes.set(id, {
      rings,
      name: osmName && !GENERIC_OSM_NAMES.has(osmName.toLowerCase()) ? osmName : null,
    });
  }
  return shapes;
}

function mostCommon(values: string[]): string | null {
  const counts = new Map<string, number>();
  let best: string | null = null;
  for (const value of values) {
    const next = (counts.get(value) ?? 0) + 1;
    counts.set(value, next);
    if (best === null || next > (counts.get(best) ?? 0)) best = value;
  }
  return best;
}

/** Les plus préoccupantes d'abord ; les points sans évaluation à la fin. */
export function compareSites(a: Site, b: Site): number {
  const unknownA = a.status === "inconnu" ? 1 : 0;
  const unknownB = b.status === "inconnu" ? 1 : 0;
  if (unknownA !== unknownB) return unknownA - unknownB;
  const risk = (b.pCriticalMax ?? -1) - (a.pCriticalMax ?? -1);
  if (Math.abs(risk) > 1e-9) return risk;
  const fill = (a.fillNow ?? 9) - (b.fillNow ?? 9);
  if (Math.abs(fill) > 1e-9) return fill;
  return a.key.localeCompare(b.key, "fr", { numeric: true });
}

export function buildSites(
  sources: ApiWaterSource[],
  bulletin: ApiBulletin | null,
  shapes: Shapes,
): Site[] {
  const byId = new Map(sources.map((source) => [source.id, source]));
  const covered = new Set<number>();
  const sites: Site[] = [];

  for (const reservoir of bulletin?.reservoirs ?? []) {
    reservoir.source_ids.forEach((id) => covered.add(id));
    const linked = reservoir.source_ids.map((id) => byId.get(id)).filter((s): s is ApiWaterSource => Boolean(s));
    const zone = zoneLabel(mostCommon(
      linked.map((s) => s.zone_detail ?? s.zone ?? "").filter(Boolean),
    ));
    const osmName = reservoir.source_ids.map((id) => shapes.get(id)?.name).find(Boolean) ?? null;

    sites.push({
      key: reservoir.reservoir_id,
      reservoirId: reservoir.reservoir_id,
      sourceIds: reservoir.source_ids,
      name: osmName ?? `Retenue ${reservoir.reservoir_id}`,
      zone,
      lat: reservoir.lat,
      lng: reservoir.lon,
      status: normalizeStatus(reservoir.status),
      fillNow: reservoir.fill_now,
      fillChange: reservoir.fill_change_1m,
      areaHa: reservoir.area_ha,
      refAreaHa: reservoir.a_ref_ha,
      volumeM3: reservoir.volume_m3,
      pCriticalMax: reservoir.p_critical_max,
      // L'intervalle publié n'encadre pas toujours la valeur centrale (bornes
      // tronquées à zéro côté modèle) : on le rend cohérent pour l'affichage.
      forecast: reservoir.forecast.map((f) => ({
        horizon: f.horizon,
        month: addMonths(bulletin!.issue_month, f.horizon),
        fill: Math.max(0, f.fill_pred),
        low: Math.max(0, Math.min(f.fill_lo80, f.fill_pred)),
        high: Math.max(f.fill_hi80, f.fill_pred),
        pCritical: f.p_critical,
      })),
      toValidate: reservoir.validation === "a_valider",
      origin: reservoir.origin,
      ndwi: null,
    });
  }

  for (const source of sources) {
    if (covered.has(source.id)) continue;
    if (source.latitude === null || source.longitude === null) continue;
    sites.push({
      key: `S${source.id}`,
      reservoirId: null,
      sourceIds: [source.id],
      name: shapes.get(source.id)?.name ?? `Point d'eau n° ${source.id}`,
      zone: zoneLabel(source.zone_detail ?? source.zone),
      lat: source.latitude,
      lng: source.longitude,
      // Sans bulletin, on garde le statut calculé par le serveur ; avec bulletin,
      // un point non rattaché à une retenue n'a simplement pas de prévision.
      status: bulletin ? "inconnu" : normalizeStatus(source.status),
      fillNow: null,
      fillChange: null,
      areaHa: source.superficie_km2 === null ? null : source.superficie_km2 * 100,
      refAreaHa: null,
      volumeM3: null,
      pCriticalMax: bulletin ? null : source.risk_score,
      forecast: [],
      toValidate: false,
      origin: null,
      ndwi: source.ndwi_moyen,
    });
  }

  return sites.sort(compareSites);
}

export function countByStatus(sites: Site[]): Record<Status, number> {
  const counts: Record<Status, number> = { tari: 0, "à risque": 0, actif: 0, inconnu: 0 };
  for (const site of sites) counts[site.status] += 1;
  return counts;
}

export function matchesQuery(site: Site, query: string): boolean {
  const needle = fold(query);
  if (!needle) return true;
  const haystack = fold(`${site.name} ${site.key} ${site.zone ?? ""} ${STATUS_META[site.status].label}`);
  return needle.split(/\s+/).every((word) => haystack.includes(word));
}

/** Premier mois où la retenue a plus d'une chance sur deux de passer sous le seuil. */
export function firstCriticalMonth(site: Site): ForecastPoint | null {
  return site.forecast.find((point) => point.pCritical >= 0.5) ?? null;
}
