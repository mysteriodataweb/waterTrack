export type Status = "actif" | "à risque" | "tari";

export interface Source {
  id: number;
  lat: number;
  lng: number;
  zone?: string;
  zone_detail?: string;
  label: string;
  statut: Status;
  ndwi: number;
  risk_score: number;
  superficie: number;
  tarissement_estime?: string;
}

export type NavigationProfile = "driving-car" | "foot-walking" | "cycling-regular";

export interface GeoPoint {
  lat: number;
  lng: number;
}

export interface NavigationPosition extends GeoPoint {
  accuracy?: number;
  heading?: number | null;
  speed?: number | null;
  timestamp: number;
}

export interface NavigationStep {
  instruction: string;
  distance: number;
  duration: number;
  name?: string;
  way_points?: [number, number];
}

export interface NavigationRoute {
  source: Source;
  origin: GeoPoint;
  destination: GeoPoint;
  profile: NavigationProfile;
  distance: number;
  duration: number;
  geometry: Array<[number, number]>;
  steps: NavigationStep[];
  currentPosition?: NavigationPosition;
  currentPlace?: string;
  remainingDistance?: number;
  remainingDuration?: number;
  currentInstruction?: string;
  activeStepIndex?: number;
  tracking?: boolean;
}

export type SectionKey = "accueil" | "navigation" | "rapports" | "analyse";
