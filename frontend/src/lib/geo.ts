import type { GeoPoint } from "./api";

export interface Position extends GeoPoint {
  accuracy?: number;
  timestamp: number;
}

/** Centre de Ouagadougou : départ de substitution, proposé explicitement quand le GPS échoue. */
export const OUAGADOUGOU: GeoPoint = { lat: 12.3647, lng: -1.5221 };

/** Un seul essai de géolocalisation, avec un garde-temps qui ne peut pas rester bloqué. */
function requestPosition(options: PositionOptions, timeoutMs: number): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    // Si l'utilisateur ignore la fenêtre de permission, plusieurs navigateurs
    // n'appellent aucun des deux callbacks et l'option `timeout` native ne se
    // déclenche pas : sans ce garde-fou la promesse ne se résout jamais.
    let settled = false;
    const finish = (action: () => void) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      action();
    };
    const timer = setTimeout(() => finish(() => reject({ code: 3 })), timeoutMs);

    navigator.geolocation.getCurrentPosition(
      (position) => finish(() => resolve(position)),
      (error) => finish(() => reject(error)),
      options,
    );
  });
}

export function toPosition(position: GeolocationPosition): Position {
  return {
    lat: position.coords.latitude,
    lng: position.coords.longitude,
    accuracy: position.coords.accuracy,
    timestamp: position.timestamp,
  };
}

export async function readCurrentPosition(): Promise<Position> {
  if (!("geolocation" in navigator)) {
    throw new Error("Ce navigateur ne permet pas de vous localiser.");
  }
  if (!window.isSecureContext) {
    throw new Error("La localisation exige une connexion sécurisée (adresse en https).");
  }

  // Deux tentatives : le GPS précis, puis le positionnement réseau (Wi-Fi),
  // bien plus fiable sur un poste fixe ou en intérieur.
  const attempts: Array<{ options: PositionOptions; timeout: number }> = [
    { options: { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 }, timeout: 11_000 },
    { options: { enableHighAccuracy: false, timeout: 20_000, maximumAge: 300_000 }, timeout: 21_000 },
  ];

  let lastError: unknown = null;
  for (const attempt of attempts) {
    try {
      return toPosition(await requestPosition(attempt.options, attempt.timeout));
    } catch (error) {
      lastError = error;
      // Permission explicitement refusée : réessayer ne sert à rien.
      if (errorCode(error) === 1) break;
    }
  }
  throw new Error(await describeGeolocationError(lastError));
}

function errorCode(error: unknown): number | undefined {
  return typeof error === "object" && error !== null ? (error as { code?: number }).code : undefined;
}

/** Message précis selon la cause réelle, plutôt qu'un texte générique. */
export async function describeGeolocationError(error: unknown): Promise<string> {
  const code = errorCode(error);

  // Cause la plus fréquente sur téléphone : la page est ouverte dans le
  // navigateur intégré d'une application, qui bloque la localisation.
  const embedded = detectEmbeddedBrowser();
  if (embedded) return `${embedded} Ouvrez ce lien dans Chrome ou Safari pour obtenir l'itinéraire.`;

  if (code === 1) {
    return "Vous avez refusé l'accès à votre position. Autorisez la localisation pour ce site (icône de cadenas dans la barre d'adresse), puis réessayez.";
  }

  // L'API Permissions distingue un refus mémorisé d'une panne.
  try {
    const status = await navigator.permissions?.query({ name: "geolocation" as PermissionName });
    if (status?.state === "denied") {
      return "La localisation est bloquée pour ce site. iPhone : Réglages > Safari > Position > Autoriser. Android : icône de cadenas > Autorisations > Position. Puis réessayez.";
    }
  } catch {
    // API Permissions indisponible : on continue avec les messages génériques.
  }

  if (code === 2) return "Aucun signal de localisation. Activez le GPS ou le Wi-Fi, puis réessayez.";
  if (code === 3) return "La recherche de votre position a pris trop de temps. Réessayez, de préférence à l'extérieur.";
  return "Votre position n'a pas pu être déterminée. Vérifiez que la localisation est activée, puis réessayez.";
}

function detectEmbeddedBrowser(): string | null {
  try {
    if (window.self !== window.top) {
      return "Cette page est affichée dans un cadre qui ne permet pas la localisation.";
    }
  } catch {
    return "Cette page est affichée dans un cadre qui ne permet pas la localisation.";
  }

  const ua = navigator.userAgent || "";
  if (/WhatsApp|Instagram|FBAN|FBAV|TikTok|Telegram|MicroMessenger|snapchat|Line\/|JSBridge|okhttp|; ?wv\)?/i.test(ua)) {
    return "Cette page est ouverte dans le navigateur intégré d'une application, qui bloque souvent la position.";
  }
  return null;
}

export function distanceMeters(a: GeoPoint, b: GeoPoint): number {
  const radius = 6_371_000;
  const toRad = (value: number) => (value * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * radius * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}

/**
 * Avancement le long d'un itinéraire : distance restante et étape en cours.
 * `geometry` est en [lng, lat] ; `stepDistances` donne la longueur de chaque étape.
 */
export function routeProgress(
  geometry: Array<[number, number]>,
  stepDistances: number[],
  totalDistance: number,
  position: GeoPoint,
): { remaining: number; stepIndex: number; offRoute: number } {
  if (geometry.length === 0) return { remaining: totalDistance, stepIndex: 0, offRoute: 0 };

  let nearest = 0;
  let nearestDistance = Number.POSITIVE_INFINITY;
  geometry.forEach(([lng, lat], index) => {
    const d = distanceMeters(position, { lat, lng });
    if (d < nearestDistance) {
      nearestDistance = d;
      nearest = index;
    }
  });

  let remaining = 0;
  for (let i = nearest; i < geometry.length - 1; i += 1) {
    remaining += distanceMeters(
      { lat: geometry[i][1], lng: geometry[i][0] },
      { lat: geometry[i + 1][1], lng: geometry[i + 1][0] },
    );
  }
  remaining = Math.min(totalDistance, remaining);

  // L'étape en cours est celle qui contient la distance déjà parcourue.
  const travelled = Math.max(0, totalDistance - remaining);
  let cumulative = 0;
  let stepIndex = Math.max(0, stepDistances.length - 1);
  for (let i = 0; i < stepDistances.length; i += 1) {
    cumulative += stepDistances[i];
    if (travelled < cumulative - 1) {
      stepIndex = i;
      break;
    }
  }

  return { remaining, stepIndex, offRoute: nearestDistance };
}
