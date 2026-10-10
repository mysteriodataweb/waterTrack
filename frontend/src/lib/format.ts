const MONTHS = [
  "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];
const MONTHS_SHORT = [
  "janv.", "févr.", "mars", "avr.", "mai", "juin",
  "juil.", "août", "sept.", "oct.", "nov.", "déc.",
];

const nf0 = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 });
const nf1 = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** "2026-08" -> { year: 2026, month: 7 } (mois indexé à partir de 0). */
export function parseMonth(value: string): { year: number; month: number } | null {
  const match = /^(\d{4})-(\d{2})/.exec(value);
  if (!match) return null;
  const month = Number(match[2]) - 1;
  if (month < 0 || month > 11) return null;
  return { year: Number(match[1]), month };
}

export function addMonths(value: string, delta: number): string {
  const parsed = parseMonth(value);
  if (!parsed) return value;
  const total = parsed.year * 12 + parsed.month + delta;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

/** "2026-08" -> "août 2026" */
export function monthLong(value: string): string {
  const parsed = parseMonth(value);
  return parsed ? `${MONTHS[parsed.month]} ${parsed.year}` : value;
}

/** "2026-08" -> "août 2026" ; "2026-09" -> "sept. 2026" */
export function monthShort(value: string, withYear = true): string {
  const parsed = parseMonth(value);
  if (!parsed) return value;
  return withYear ? `${MONTHS_SHORT[parsed.month]} ${parsed.year}` : MONTHS_SHORT[parsed.month];
}

/** « d'août 2026 » / « de mars 2026 » : l'élision dépend du mois. */
export function ofMonth(value: string): string {
  const label = monthLong(value);
  return /^[aeiouâéèo]/i.test(label) ? `d'${label}` : `de ${label}`;
}

/** Taux de remplissage 0..1 -> "34 %". Au-delà de la surface de référence on l'affiche tel quel. */
export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return `${nf0.format(Math.round(value * 100))} %`;
}

export function signedPoints(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const points = Math.round(value * 100);
  if (points === 0) return "stable";
  return `${points > 0 ? "+" : "−"}${nf0.format(Math.abs(points))} ${Math.abs(points) > 1 ? "points" : "point"}`;
}

/** Surface en hectares, précision adaptée à l'ordre de grandeur. */
export function hectares(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value >= 100) return `${nf0.format(value)} ha`;
  return `${nf1.format(value)} ha`;
}

export function volume(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value >= 1_000_000) return `${nf1.format(value / 1_000_000)} millions de m³`;
  return `${nf0.format(value)} m³`;
}

export function distance(meters: number): string {
  if (meters < 1000) return `${nf0.format(Math.round(meters / 10) * 10)} m`;
  return `${nf1.format(meters / 1000)} km`;
}

export function duration(seconds: number): string {
  const minutes = Math.max(1, Math.round(seconds / 60));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours} h` : `${hours} h ${String(rest).padStart(2, "0")}`;
}

export function coordinates(lat: number, lng: number): string {
  const ns = lat >= 0 ? "N" : "S";
  const ew = lng >= 0 ? "E" : "O";
  return `${Math.abs(lat).toFixed(4)}° ${ns}, ${Math.abs(lng).toFixed(4)}° ${ew}`;
}

export function plural(count: number, singular: string, pluralForm?: string): string {
  return `${nf0.format(count)} ${count > 1 ? (pluralForm ?? `${singular}s`) : singular}`;
}

/** Recherche tolérante : sans accents ni casse. */
export function fold(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Probabilité 0..1 : jamais « 0 % » ni « 100 % », un modèle n'est pas certain. */
export function risk(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  if (value > 0.99) return "> 99 %";
  if (value < 0.01) return "< 1 %";
  return `${Math.round(value * 100)} %`;
}

/** Nombre de mois écoulés entre un mois "AAAA-MM" et aujourd'hui. */
export function monthsSince(value: string, now: Date = new Date()): number {
  const parsed = parseMonth(value);
  if (!parsed) return 0;
  return (now.getFullYear() - parsed.year) * 12 + now.getMonth() - parsed.month;
}
