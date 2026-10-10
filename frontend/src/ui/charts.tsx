import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { ApiHistoryPoint } from "@/lib/api";
import { hectares, monthLong, monthShort, parseMonth, percent } from "@/lib/format";
import type { ForecastPoint } from "@/lib/sites";

const INK = "#14222b";
const INK_2 = "#44535d";
const GRID = "#d9dfde";
const WATER = "#0b5c8a";

/** Largeur réelle du conteneur : les graphiques sont dessinés au pixel, sans mise à l'échelle du texte. */
function useWidth<T extends HTMLElement>(): [React.RefObject<T | null>, number] {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    setWidth(element.clientWidth);
    const observer = new ResizeObserver(([entry]) => setWidth(Math.round(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

function niceMax(value: number): number {
  // Graduations de 25 % ; l'axe monte au moins à 100 %.
  return Math.max(1, Math.ceil(value / 0.25 - 1e-9) * 0.25);
}

// --------------------------------------------------------------- Prévision

export function ForecastChart({
  issueMonth,
  fillNow,
  forecast,
  critical,
}: {
  issueMonth: string;
  fillNow: number | null;
  forecast: ForecastPoint[];
  critical: number;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const height = 190;
  const pad = { top: 22, right: 18, bottom: 28, left: 42 };

  const points = [
    ...(fillNow === null ? [] : [{ month: issueMonth, fill: fillNow, low: fillNow, high: fillNow, measured: true }]),
    ...forecast.map((f) => ({ month: f.month, fill: f.fill, low: f.low, high: f.high, measured: false })),
  ];
  const yMax = niceMax(Math.max(...points.map((p) => p.high), critical));
  const innerW = Math.max(0, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const x = (i: number) => pad.left + (points.length === 1 ? innerW / 2 : (i / (points.length - 1)) * innerW);
  const y = (v: number) => pad.top + innerH - (Math.min(v, yMax) / yMax) * innerH;

  const ticks = [];
  for (let v = 0; v <= yMax + 1e-9; v += yMax > 1.5 ? 0.5 : 0.25) ticks.push(v);

  const band = points.length > 1
    ? `${points.map((p, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(p.high)}`).join(" ")} ${points
      .map((_, i) => points.length - 1 - i)
      .map((i) => `L${x(i)},${y(points[i].low)}`)
      .join(" ")} Z`
    : "";

  const summary = `Remplissage mesuré ${fillNow === null ? "non disponible" : percent(fillNow)} en ${monthLong(issueMonth)} ; prévu ${forecast
    .map((f) => `${percent(f.fill)} en ${monthLong(f.month)}`)
    .join(", ")}. Seuil critique ${percent(critical)}.`;

  return (
    <div ref={ref} className="w-full">
      {width > 0 && (
        <svg width={width} height={height} role="img" aria-label={summary} className="block">
          {ticks.map((v) => (
            <g key={v}>
              <line x1={pad.left} x2={width - pad.right} y1={y(v)} y2={y(v)} stroke={GRID} strokeWidth="1" />
              <text x={pad.left - 8} y={y(v) + 4} textAnchor="end" fontSize="12" fill={INK_2} className="num">
                {Math.round(v * 100)} %
              </text>
            </g>
          ))}

          {band && <path d={band} fill={WATER} opacity="0.14" />}

          <line
            x1={pad.left} x2={width - pad.right} y1={y(critical)} y2={y(critical)}
            stroke={INK} strokeWidth="1.5" strokeDasharray="5 4"
          />

          {points.slice(1).map((p, i) => (
            <line
              key={p.month}
              x1={x(i)} y1={y(points[i].fill)} x2={x(i + 1)} y2={y(p.fill)}
              stroke={WATER} strokeWidth="2" strokeDasharray="1 5" strokeLinecap="round"
            />
          ))}

          {points.map((p, i) => {
            const labelAbove = y(p.fill) - pad.top > 18;
            return (
              <g key={p.month}>
                <circle
                  cx={x(i)} cy={y(p.fill)} r="5"
                  fill={p.measured ? WATER : "#fff"} stroke={p.measured ? "#fff" : WATER} strokeWidth="2"
                />
                <text
                  x={x(i)} y={labelAbove ? y(p.fill) - 10 : y(p.fill) + 20}
                  textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
                  fontSize="13" fontWeight="650" fill={INK} className="num"
                  stroke="#fff" strokeWidth="3" paintOrder="stroke"
                >
                  {percent(p.fill)}
                </text>
                <text
                  x={x(i)} y={height - 8}
                  textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
                  fontSize="12" fill={INK_2}
                >
                  {monthShort(p.month, false)}{p.measured ? " (mesuré)" : ""}
                </text>
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}

// --------------------------------------------------------------- Historique

export function HistoryChart({ points, critical }: { points: ApiHistoryPoint[]; critical: number }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const height = 200;
  const pad = { top: 12, right: 12, bottom: 26, left: 42 };

  const data = useMemo(() => points.filter((p) => p.fill !== null), [points]);
  const yMax = niceMax(Math.max(...data.map((p) => p.fill ?? 0), critical));
  const innerW = Math.max(0, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const x = (i: number) => pad.left + (data.length <= 1 ? innerW / 2 : (i / (data.length - 1)) * innerW);
  const y = (v: number) => pad.top + innerH - (Math.min(v, yMax) / yMax) * innerH;

  if (data.length < 2) {
    return <p className="text-[15px] text-ink-2">Pas encore assez de mesures pour tracer l'historique.</p>;
  }

  const path = data.map((p, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(p.fill ?? 0).toFixed(1)}`).join(" ");
  const years = data
    .map((p, i) => ({ parsed: parseMonth(p.month), i }))
    .filter((d) => d.parsed?.month === 0);
  // Sur un petit écran, une année sur deux suffit.
  const yearStep = innerW / Math.max(1, years.length) < 38 ? 2 : 1;

  const move = (event: PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const ratio = (event.clientX - rect.left - pad.left) / Math.max(1, innerW);
    setActive(Math.max(0, Math.min(data.length - 1, Math.round(ratio * (data.length - 1)))));
  };
  const onKey = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const delta = event.key === "ArrowLeft" ? -1 : 1;
    setActive((current) => Math.max(0, Math.min(data.length - 1, (current ?? data.length - 1) + delta)));
  };

  const current = active === null ? null : data[active];
  const first = data[0];
  const last = data[data.length - 1];
  const tipLeft = active === null ? 0 : Math.max(0, Math.min(width - 190, x(active) - 95));

  return (
    <div ref={ref} className="relative w-full">
      {width > 0 && (
        <svg
          width={width} height={height} className="block touch-pan-y"
          role="img" tabIndex={0}
          aria-label={`Remplissage mensuel de ${monthLong(first.month)} à ${monthLong(last.month)}. Dernière mesure : ${percent(last.fill)}. Flèches gauche et droite pour parcourir les mois.`}
          onPointerMove={move} onPointerDown={move} onPointerLeave={() => setActive(null)}
          onKeyDown={onKey} onBlur={() => setActive(null)}
        >
          {[0, 0.5, 1].filter((v) => v <= yMax).map((v) => (
            <g key={v}>
              <line x1={pad.left} x2={width - pad.right} y1={y(v)} y2={y(v)} stroke={GRID} strokeWidth="1" />
              <text x={pad.left - 8} y={y(v) + 4} textAnchor="end" fontSize="12" fill={INK_2} className="num">
                {Math.round(v * 100)} %
              </text>
            </g>
          ))}
          {years.filter((_, index) => index % yearStep === 0).map(({ parsed, i }) => (
            <g key={i}>
              <line x1={x(i)} x2={x(i)} y1={pad.top + innerH} y2={pad.top + innerH + 4} stroke={INK_2} strokeWidth="1" />
              <text x={x(i)} y={height - 6} textAnchor="middle" fontSize="12" fill={INK_2} className="num">
                {parsed!.year}
              </text>
            </g>
          ))}

          <line
            x1={pad.left} x2={width - pad.right} y1={y(critical)} y2={y(critical)}
            stroke={INK} strokeWidth="1.5" strokeDasharray="5 4"
          />
          <path d={path} fill="none" stroke={WATER} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

          {current && active !== null && (
            <g>
              <line x1={x(active)} x2={x(active)} y1={pad.top} y2={pad.top + innerH} stroke={INK} strokeWidth="1" opacity="0.45" />
              <circle cx={x(active)} cy={y(current.fill ?? 0)} r="5" fill={WATER} stroke="#fff" strokeWidth="2" />
            </g>
          )}
        </svg>
      )}

      {current && (
        <div
          className="pointer-events-none absolute top-0 w-[190px] rounded-md bg-ink px-3 py-2 text-[13px] leading-snug text-white shadow-panel"
          style={{ left: tipLeft }}
        >
          <div className="font-semibold">{monthLong(current.month)}</div>
          <div className="num">Remplissage {percent(current.fill)}</div>
          <div className="num text-white/80">
            {hectares(current.area_ha)} en eau
            {current.precip_mm !== null && `, ${Math.round(current.precip_mm)} mm de pluie`}
          </div>
          {current.area_source === "interp" && <div className="text-white/80">Valeur estimée (nuages ce mois-là)</div>}
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------- NDWI par semestre

export function NdwiBars({ periods }: { periods: Array<{ periode: string; ndwi_moyen: number }> }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);
  const height = 190;
  const pad = { top: 22, right: 8, bottom: 40, left: 40 };
  const yMax = Math.max(0.5, Math.ceil(Math.max(...periods.map((p) => p.ndwi_moyen)) * 10) / 10);
  const innerW = Math.max(0, width - pad.left - pad.right);
  const innerH = height - pad.top - pad.bottom;
  const slot = innerW / Math.max(1, periods.length);
  const bar = Math.min(34, Math.max(6, slot - 6));
  const y = (v: number) => pad.top + innerH - (Math.max(0, v) / yMax) * innerH;

  return (
    <div ref={ref} className="w-full">
      {width > 0 && (
        <svg
          width={width} height={height} className="block" role="img"
          aria-label={`Indice d'eau moyen par semestre, de ${periods[0]?.periode} à ${periods.at(-1)?.periode}.`}
          onPointerLeave={() => setActive(null)}
        >
          {[0, yMax / 2, yMax].map((v) => (
            <g key={v}>
              <line x1={pad.left} x2={width - pad.right} y1={y(v)} y2={y(v)} stroke={GRID} strokeWidth="1" />
              <text x={pad.left - 8} y={y(v) + 4} textAnchor="end" fontSize="12" fill={INK_2} className="num">
                {v.toFixed(2).replace(".", ",")}
              </text>
            </g>
          ))}
          {periods.map((p, i) => {
            const cx = pad.left + slot * i + slot / 2;
            const top = y(p.ndwi_moyen);
            const [year, semester] = p.periode.split("-");
            const wet = semester === "S2";
            return (
              <g key={p.periode} onPointerEnter={() => setActive(i)}>
                <rect x={pad.left + slot * i} y={pad.top} width={slot} height={innerH + pad.bottom} fill="transparent" />
                <path
                  d={`M${cx - bar / 2},${pad.top + innerH} V${top + 3} Q${cx - bar / 2},${top} ${cx - bar / 2 + 3},${top} H${cx + bar / 2 - 3} Q${cx + bar / 2},${top} ${cx + bar / 2},${top + 3} V${pad.top + innerH} Z`}
                  fill={WATER} opacity={wet ? 1 : 0.45}
                />
                {active === i && (
                  <text x={cx} y={top - 6} textAnchor="middle" fontSize="12" fontWeight="650" fill={INK} className="num">
                    {p.ndwi_moyen.toFixed(2).replace(".", ",")}
                  </text>
                )}
                <text x={cx} y={height - 22} textAnchor="middle" fontSize="11" fill={INK_2}>{semester}</text>
                {semester === "S1" && (
                  <text x={cx + slot / 2} y={height - 6} textAnchor="middle" fontSize="12" fill={INK_2} className="num">{year}</text>
                )}
              </g>
            );
          })}
        </svg>
      )}
    </div>
  );
}
