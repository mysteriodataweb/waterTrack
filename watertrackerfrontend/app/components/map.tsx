"use client";

import axios from "axios";
import L from "leaflet";
import { useEffect, useState } from "react";
import { GeoJSON, MapContainer, TileLayer, useMap } from "react-leaflet";

type Geometry = GeoJSON.Geometry;

type WaterSource = {
  id: number;
  geometry: Geometry | null;
  ndwi_moyen: number | null;
  risk_score: number | null;
  status: string | null;
  zone: string | null;
  date_analyse: string | null;
};

type FeatureProperties = Omit<WaterSource, "geometry">;
type Feature = GeoJSON.Feature<Geometry, FeatureProperties>;

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000/api/water-sources";

const DEFAULT_CENTER: [number, number] = [12.3714, -1.5197];

function normalizeStatus(status: string | null) {
  return (status ?? "actif").trim().toLowerCase();
}

function statusColor(status: string | null) {
  const normalized = normalizeStatus(status);

  if (normalized === "tari") {
    return "#cc3d2d";
  }

  if (
    normalized === "a risque" ||
    normalized === "à risque" ||
    normalized === "risque"
  ) {
    return "#d47a1f";
  }

  return "#1d6fd6";
}

function formatNumber(value: number | null, digits = 3) {
  if (value === null || Number.isNaN(value)) {
    return "N/A";
  }

  return value.toFixed(digits);
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function popupMarkup(source: FeatureProperties) {
  const zone = escapeHtml(source.zone ?? "N/A");
  const status = escapeHtml(source.status ?? "actif");
  const ndwi = escapeHtml(formatNumber(source.ndwi_moyen));
  const risk = escapeHtml(formatNumber(source.risk_score, 2));
  const dateAnalyse = escapeHtml(source.date_analyse ?? "N/A");
  const color = statusColor(source.status);

  return `
    <div style="min-width:220px;border-radius:16px;background:#ffffff;padding:16px;color:#1e293b;">
      <div style="margin-bottom:12px;display:flex;align-items:center;justify-content:space-between;gap:12px;">
        <div>
          <p style="margin:0 0 4px;font-size:11px;font-weight:700;letter-spacing:0.24em;text-transform:uppercase;color:#64748b;">
            Source
          </p>
          <h3 style="margin:0;font-size:18px;font-weight:700;">#${source.id}</h3>
        </div>
        <span style="border-radius:999px;background:${color};padding:6px 12px;font-size:11px;font-weight:700;letter-spacing:0.18em;text-transform:uppercase;color:white;">
          ${status}
        </span>
      </div>
      <div style="display:grid;gap:8px;font-size:14px;">
        <p style="margin:0;"><strong>ID :</strong> ${source.id}</p>
        <p style="margin:0;"><strong>Zone :</strong> ${zone}</p>
        <p style="margin:0;"><strong>NDWI moyen :</strong> ${ndwi}</p>
        <p style="margin:0;"><strong>Risk score :</strong> ${risk}</p>
        <p style="margin:0;"><strong>Date analyse :</strong> ${dateAnalyse}</p>
      </div>
    </div>
  `;
}

function summarizeStatuses(sources: WaterSource[]) {
  const summary = {
    active: 0,
    risk: 0,
    dry: 0,
  };

  for (const source of sources) {
    const normalized = normalizeStatus(source.status);

    if (normalized === "tari") {
      summary.dry += 1;
      continue;
    }

    if (
      normalized === "a risque" ||
      normalized === "à risque" ||
      normalized === "risque"
    ) {
      summary.risk += 1;
      continue;
    }

    summary.active += 1;
  }

  return summary;
}

function FitToSources({ features }: { features: Feature[] }) {
  const map = useMap();

  useEffect(() => {
    if (!features.length) {
      return;
    }

    const layer = L.geoJSON(features as GeoJSON.GeoJsonObject);
    const bounds = layer.getBounds();

    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [28, 28] });
    }
  }, [features, map]);

  return null;
}

export default function WaterMap() {
  const [sources, setSources] = useState<WaterSource[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSources() {
      try {
        const response = await axios.get<WaterSource[]>(API_URL);

        if (!isMounted) {
          return;
        }

        setSources(response.data);
        setError(null);
      } catch {
        if (!isMounted) {
          return;
        }

        setError(
          "Impossible de charger les sources d'eau. Verifiez que l'API FastAPI tourne sur http://127.0.0.1:8000."
        );
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadSources();

    return () => {
      isMounted = false;
    };
  }, []);

  const features: Feature[] = sources
    .filter((source) => source.geometry)
    .map((source) => ({
      type: "Feature",
      geometry: source.geometry as Geometry,
      properties: {
        id: source.id,
        ndwi_moyen: source.ndwi_moyen,
        risk_score: source.risk_score,
        status: source.status,
        zone: source.zone,
        date_analyse: source.date_analyse,
      },
    }));

  const summary = summarizeStatuses(sources);

  return (
    <div className="overflow-hidden rounded-[28px] border border-[var(--line)] bg-[#d9ebe6]">
      <div className="flex items-center justify-between gap-4 border-b border-[var(--line)] bg-[rgba(253,252,247,0.92)] px-5 py-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[var(--muted)]">
            Ouagadougou
          </p>
          <p className="text-sm text-[var(--muted)]">
            {isLoading ? "Chargement..." : `${features.length} sources affichees`}
          </p>
        </div>
        <div className="rounded-full border border-[var(--line)] bg-white/80 px-3 py-1 text-xs text-[var(--muted)]">
          Sentinel-2 / NDWI
        </div>
      </div>

      <div className="grid gap-3 border-b border-[var(--line)] bg-[rgba(253,252,247,0.88)] px-5 py-3 text-sm text-[var(--muted)] sm:grid-cols-3">
        <div className="rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3">
          <span className="font-semibold text-[var(--active)]">{summary.active}</span>{" "}
          actives
        </div>
        <div className="rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3">
          <span className="font-semibold text-[var(--risk)]">{summary.risk}</span>{" "}
          a risque
        </div>
        <div className="rounded-2xl border border-[var(--line)] bg-white/70 px-4 py-3">
          <span className="font-semibold text-[var(--dry)]">{summary.dry}</span>{" "}
          taries
        </div>
      </div>

      {error ? (
        <div className="flex h-[520px] items-center justify-center px-6 text-center text-sm text-[var(--dry)]">
          {error}
        </div>
      ) : (
        <div className="h-[520px] w-full">
          <MapContainer
            center={DEFAULT_CENTER}
            zoom={11}
            scrollWheelZoom
            className="h-full w-full"
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitToSources features={features} />
            {features.map((feature) => (
              <GeoJSON
                key={feature.properties.id}
                data={feature}
                onEachFeature={(currentFeature, layer) => {
                  layer.bindPopup(popupMarkup(currentFeature.properties));
                }}
                pathOptions={{
                  color: statusColor(feature.properties.status),
                  weight: 2,
                  fillColor: statusColor(feature.properties.status),
                  fillOpacity: 0.32,
                }}
              />
            ))}
          </MapContainer>
        </div>
      )}
    </div>
  );
}
