import { useEffect, useRef, useState } from "react";
import type { NavigationRoute, Source } from "./types";

export function MapBackground({
  sources,
  navigationRoute,
  onSourceClick,
}: {
  sources: Source[];
  navigationRoute: NavigationRoute | null;
  onSourceClick: (s: Source) => void;
}) {
  const mapRef = useRef<HTMLDivElement>(null);
  const leafletMap = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const routeLayerRef = useRef<any>(null);
  const liveLayerRef = useRef<any>(null);
  const [mapReady, setMapReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const L = (await import("leaflet")).default;
      if (cancelled || !mapRef.current || leafletMap.current) return;
      const map = L.map(mapRef.current, { zoomControl: false, attributionControl: false }).setView([12.3647, -1.5221], 11);
      // OpenStreetMap est gratuit et ne nécessite AUCUNE clé API, contrairement aux
      // tuiles CartoDB (basemaps.cartocdn.com) qui affichent "API key required".
      // Un filtre CSS inverse les couleurs pour conserver le thème sombre du design.
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        className: "wt-dark-tiles",
      }).addTo(map);
      L.control.zoom({ position: "bottomright" }).addTo(map);
      leafletMap.current = map;
      setMapReady(true);
    })();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!mapReady || !leafletMap.current) return;
    (async () => {
      const L = (await import("leaflet")).default;
      if (layerRef.current) leafletMap.current.removeLayer(layerRef.current);
      const group = L.layerGroup();
      sources.forEach((s) => {
        const color = s.statut === "actif" ? "#62e6a6" : s.statut === "à risque" ? "#f6c65b" : "#ff6b6b";
        const marker = L.circleMarker([s.lat, s.lng], {
          radius: 7,
          color,
          weight: 3,
          fillColor: color,
          fillOpacity: 0.78,
        });
        marker.on("click", () => onSourceClick(s));
        marker.addTo(group);
      });
      group.addTo(leafletMap.current);
      layerRef.current = group;
    })();
  }, [mapReady, sources, onSourceClick]);

  useEffect(() => {
    if (!mapReady || !leafletMap.current) return;
    (async () => {
      const L = (await import("leaflet")).default;
      if (routeLayerRef.current) {
        leafletMap.current.removeLayer(routeLayerRef.current);
        routeLayerRef.current = null;
      }
      if (!navigationRoute || navigationRoute.geometry.length === 0) return;

      const group = L.layerGroup();
      const latLngs = navigationRoute.geometry.map(([lng, lat]) => [lat, lng] as [number, number]);
      const routeLine = L.polyline(latLngs, {
        color: "#9fc9ea",
        weight: 5,
        opacity: 0.95,
        lineCap: "round",
        lineJoin: "round",
      }).addTo(group);

      L.circleMarker([navigationRoute.destination.lat, navigationRoute.destination.lng], {
        radius: 9,
        color: "#62e6a6",
        weight: 3,
        fillColor: "#62e6a6",
        fillOpacity: 0.85,
      }).bindTooltip(navigationRoute.source.label.toUpperCase()).addTo(group);

      group.addTo(leafletMap.current);
      routeLayerRef.current = group;
      leafletMap.current.fitBounds(routeLine.getBounds().pad(0.22), { animate: true, maxZoom: 15 });
    })();
  }, [mapReady, navigationRoute?.geometry, navigationRoute?.source.id]);

  useEffect(() => {
    if (!mapReady || !leafletMap.current) return;
    (async () => {
      const L = (await import("leaflet")).default;
      if (liveLayerRef.current) {
        leafletMap.current.removeLayer(liveLayerRef.current);
        liveLayerRef.current = null;
      }
      const position = navigationRoute?.currentPosition ?? (navigationRoute ? {
        ...navigationRoute.origin,
        timestamp: Date.now(),
      } : null);
      if (!position) return;

      const heading = position.heading ?? 0;
      const group = L.layerGroup();
      L.circle([position.lat, position.lng], {
        radius: position.accuracy ?? 15,
        color: "#9fc9ea",
        weight: 1,
        fillColor: "#9fc9ea",
        fillOpacity: 0.08,
        opacity: 0.25,
      }).addTo(group);

      L.marker([position.lat, position.lng], {
        icon: L.divIcon({
          className: "",
          iconSize: [34, 34],
          iconAnchor: [17, 17],
          html: `
            <div style="
              width:34px;height:34px;border-radius:999px;
              background:#171b22;border:2px solid #9fc9ea;
              box-shadow:0 0 22px rgba(143,211,255,.55);
              display:flex;align-items:center;justify-content:center;
              transform:rotate(${heading}deg);
            ">
              <div style="
                width:0;height:0;
                border-left:6px solid transparent;
                border-right:6px solid transparent;
                border-bottom:16px solid #9fc9ea;
                transform:translateY(-2px);
              "></div>
            </div>
          `,
        }),
      }).bindTooltip(navigationRoute?.currentPlace ?? "Votre position").addTo(group);

      group.addTo(leafletMap.current);
      liveLayerRef.current = group;

      if (navigationRoute?.tracking) {
        leafletMap.current.panTo([position.lat, position.lng], { animate: true });
      }
    })();
  }, [mapReady, navigationRoute?.currentPosition, navigationRoute?.currentPlace, navigationRoute?.tracking, navigationRoute?.origin]);

  return (
    <>
      <div ref={mapRef} className="absolute inset-0 z-0" />
      <div className="pointer-events-none absolute inset-0 z-[1] bg-[radial-gradient(circle_at_48%_42%,rgba(61,133,184,0.18),transparent_35%),linear-gradient(90deg,rgba(5,13,28,0.72),transparent_28%,transparent_68%,rgba(5,13,28,0.58))]" />
    </>
  );
}
