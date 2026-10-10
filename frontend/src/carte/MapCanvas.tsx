import { useEffect, useRef } from "react";
import L from "leaflet";
import type { GeoPoint } from "@/lib/api";
import { percent } from "@/lib/format";
import type { Position } from "@/lib/geo";
import { STATUS_META, type Shapes, type Site } from "@/lib/sites";

export interface MapRoute {
  /** Paires [longitude, latitude]. */
  geometry: Array<[number, number]>;
  origin: GeoPoint;
  destination: GeoPoint;
}

const CENTER: [number, number] = [12.3647, -1.5221];

function markerStyle(site: Site, selected: boolean): L.CircleMarkerOptions {
  const meta = STATUS_META[site.status];
  const unknown = site.status === "inconnu";
  return {
    radius: selected ? 10 : site.status === "actif" || unknown ? 6 : 8,
    color: selected ? "#14222b" : unknown ? meta.color : "#ffffff",
    weight: selected ? 3 : 2,
    fillColor: unknown ? "#ffffff" : meta.color,
    fillOpacity: 1,
  };
}

function polygonStyle(site: Site, selected: boolean): L.PathOptions {
  const meta = STATUS_META[site.status];
  return {
    color: selected ? "#14222b" : meta.ink,
    weight: selected ? 3 : 1.5,
    fillColor: meta.color,
    fillOpacity: selected ? 0.5 : 0.38,
  };
}

function tooltipText(site: Site): string {
  const fill = site.fillNow === null ? "" : ` · rempli à ${percent(site.fillNow)}`;
  return `<strong>${escapeHtml(site.name)}</strong><br>${STATUS_META[site.status].label}${fill}`;
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

export function MapCanvas({
  sites,
  shapes,
  selectedKey,
  onSelect,
  route,
  me,
  bottomInset,
}: {
  sites: Site[];
  shapes: Shapes;
  selectedKey: string | null;
  onSelect: (key: string) => void;
  route: MapRoute | null;
  me: Position | null;
  /** Hauteur masquée en bas par le panneau mobile, pour centrer dans la partie visible. */
  bottomInset: number;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const sitesLayerRef = useRef<L.LayerGroup | null>(null);
  const routeLayerRef = useRef<L.LayerGroup | null>(null);
  const meLayerRef = useRef<L.LayerGroup | null>(null);
  const featuresRef = useRef(new Map<string, { site: Site; marker: L.CircleMarker; polygons: L.Polygon[] }>());
  const fittedRef = useRef(false);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const insetRef = useRef(bottomInset);
  insetRef.current = bottomInset;
  const selectedRef = useRef(selectedKey);
  selectedRef.current = selectedKey;

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      zoomControl: false,
      // Tolérance de clic élargie : un marqueur de 12 px reste facile à toucher au doigt.
      renderer: L.canvas({ tolerance: 12, padding: 0.3 }),
    }).setView(CENTER, 10);
    map.attributionControl.setPrefix(false);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      className: "wt-tiles",
      attribution: '© contributeurs <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a>',
    }).addTo(map);
    L.control.zoom({ position: "topright", zoomInTitle: "Zoomer", zoomOutTitle: "Dézoomer" }).addTo(map);
    L.control.scale({ imperial: false, position: "bottomright" }).addTo(map);
    mapRef.current = map;

    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(containerRef.current);
    const onPan = (event: Event) => {
      const point = (event as CustomEvent<GeoPoint>).detail;
      map.setView([point.lat, point.lng], Math.max(map.getZoom(), 13));
    };
    window.addEventListener("wt:pan", onPan);
    return () => {
      window.removeEventListener("wt:pan", onPan);
      observer.disconnect();
      map.remove();
      mapRef.current = null;
      fittedRef.current = false;
    };
  }, []);

  // Retenues : contours réels quand ils existent, toujours un point au centre.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    sitesLayerRef.current?.remove();
    featuresRef.current.clear();
    const group = L.layerGroup();

    // Les plus préoccupantes sont dessinées en dernier, donc au-dessus.
    for (const site of [...sites].reverse()) {
      const selected = site.key === selectedRef.current;
      const polygons: L.Polygon[] = [];
      for (const id of site.sourceIds) {
        for (const ring of shapes.get(id)?.rings ?? []) {
          const polygon = L.polygon(ring, polygonStyle(site, selected));
          polygon.on("click", () => onSelectRef.current(site.key));
          polygon.bindTooltip(tooltipText(site), { sticky: true, className: "wt-tip", direction: "top" });
          polygon.addTo(group);
          polygons.push(polygon);
        }
      }
      const marker = L.circleMarker([site.lat, site.lng], markerStyle(site, selected));
      marker.on("click", () => onSelectRef.current(site.key));
      marker.bindTooltip(tooltipText(site), { className: "wt-tip", direction: "top", offset: [0, -8] });
      marker.addTo(group);
      featuresRef.current.set(site.key, { site, marker, polygons });
    }

    group.addTo(map);
    sitesLayerRef.current = group;

    if (!fittedRef.current && sites.length > 0 && !selectedRef.current) {
      map.fitBounds(L.latLngBounds(sites.map((s) => [s.lat, s.lng] as [number, number])).pad(0.08), {
        paddingBottomRight: [0, insetRef.current],
        animate: false,
      });
      fittedRef.current = true;
    }
  }, [sites, shapes]);

  // Sélection : on met en avant la retenue et on l'amène dans la partie visible.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    for (const [key, feature] of featuresRef.current) {
      const selected = key === selectedKey;
      feature.marker.setStyle(markerStyle(feature.site, selected));
      feature.marker.setRadius(markerStyle(feature.site, selected).radius ?? 6);
      feature.polygons.forEach((polygon) => polygon.setStyle(polygonStyle(feature.site, selected)));
      if (selected) {
        feature.polygons.forEach((polygon) => polygon.bringToFront());
        feature.marker.bringToFront();
      }
    }
    const feature = selectedKey ? featuresRef.current.get(selectedKey) : null;
    if (!feature || route) return;
    const bounds = feature.polygons.length > 0
      ? L.featureGroup(feature.polygons).getBounds()
      : L.latLng(feature.site.lat, feature.site.lng).toBounds(2500);
    fittedRef.current = true;
    map.flyToBounds(bounds.pad(0.6), {
      paddingBottomRight: [0, insetRef.current],
      maxZoom: 14,
      duration: 0.6,
    });
    // `sites` est une dépendance : une sélection arrivée par l'URL doit être
    // appliquée une fois les retenues chargées.
  }, [selectedKey, sites, route]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    routeLayerRef.current?.remove();
    routeLayerRef.current = null;
    if (!route || route.geometry.length === 0) return;

    const latLngs = route.geometry.map(([lng, lat]) => [lat, lng] as [number, number]);
    const group = L.layerGroup();
    L.polyline(latLngs, { color: "#ffffff", weight: 8, opacity: 0.95, lineCap: "round", lineJoin: "round", interactive: false }).addTo(group);
    const line = L.polyline(latLngs, { color: "#0b5c8a", weight: 4.5, lineCap: "round", lineJoin: "round", interactive: false }).addTo(group);
    L.circleMarker([route.origin.lat, route.origin.lng], {
      radius: 6, color: "#0b5c8a", weight: 3, fillColor: "#ffffff", fillOpacity: 1, interactive: false,
    }).addTo(group);
    group.addTo(map);
    routeLayerRef.current = group;
    map.fitBounds(line.getBounds().pad(0.15), { paddingBottomRight: [0, insetRef.current], maxZoom: 15 });
  }, [route]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    meLayerRef.current?.remove();
    meLayerRef.current = null;
    if (!me) return;

    const group = L.layerGroup();
    if (me.accuracy && me.accuracy > 25) {
      L.circle([me.lat, me.lng], {
        radius: me.accuracy, color: "#0b5c8a", weight: 1, opacity: 0.4, fillColor: "#0b5c8a", fillOpacity: 0.08, interactive: false,
      }).addTo(group);
    }
    L.marker([me.lat, me.lng], {
      icon: L.divIcon({ className: "", iconSize: [18, 18], iconAnchor: [9, 9], html: '<div class="wt-me"></div>' }),
      keyboard: false,
      alt: "Votre position",
    }).bindTooltip("Vous êtes ici", { className: "wt-tip", direction: "top", offset: [0, -10] }).addTo(group);
    group.addTo(map);
    meLayerRef.current = group;
  }, [me]);

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 z-0"
      role="application"
      aria-label="Carte des retenues d'eau. La même information est disponible dans la liste."
    />
  );
}

/** Recentre la carte sur un point (bouton « Me localiser »). */
export function panMapTo(point: GeoPoint) {
  window.dispatchEvent(new CustomEvent<GeoPoint>("wt:pan", { detail: point }));
}
