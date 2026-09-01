import type { Source } from "@/components/map/types";

// Generate mock sources around Ouagadougou (12.3647, -1.5221)
function rand(seed: number) {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
}

const statuses: Source["statut"][] = ["actif", "à risque", "tari"];

export const mockSources: Source[] = Array.from({ length: 80 }, (_, i) => {
  const r1 = rand(i + 1);
  const r2 = rand(i + 100);
  const r3 = rand(i + 200);
  const statut = statuses[Math.floor(rand(i + 7) * 3)];
  const risk = statut === "tari" ? 0.85 + r3 * 0.15 : statut === "à risque" ? 0.5 + r3 * 0.4 : r3 * 0.5;
  const label = `ouagadougou-${i + 1}`;
  return {
    id: i + 1,
    label,
    zone_detail: "ouagadougou",
    lat: 12.3647 + (r1 - 0.5) * 0.4,
    lng: -1.5221 + (r2 - 0.5) * 0.4,
    statut,
    ndwi: -0.2 + r1 * 0.9,
    risk_score: risk,
    superficie: 0.001 + r2 * 0.05,
    tarissement_estime: statut === "tari" ? "—" : `202${5 + Math.floor(r3 * 3)}-S${1 + Math.floor(r3 * 2)}`,
  };
});
