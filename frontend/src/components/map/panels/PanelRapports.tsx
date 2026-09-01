import { useEffect, useState } from "react";
import { AlertTriangle, Download, Droplets, Loader2, TrendingDown, TrendingUp } from "lucide-react";
import { fetchReportSummary, type ReportSummary } from "../api";

function statusColor(ndwi: number): string {
  if (ndwi > 0.35) return "#62e6a6";
  if (ndwi > 0.25) return "#e3b341";
  return "#ff6b6b";
}

function exportCsv(report: ReportSummary) {
  const rows: string[] = ["PERIODE,NDWI_MOYEN,NB_SOURCES"];

  for (const p of report.periodes) {
    rows.push(`${p.periode},${p.ndwi_moyen.toFixed(4)},${p.nb_sources}`);
  }

  rows.push("");
  rows.push("ZONE,NB_SOURCES");
  for (const z of report.zones) {
    rows.push(`${z.zone.replace(/"/g, '""')},${z.count}`);
  }

  rows.push("");
  rows.push("SOURCE,ZONE,STATUT,RISK_SCORE,NDWI");
  for (const s of report.top_risque) {
    rows.push(`${s.id},${(s.zone_detail ?? "").replace(/"/g, '""')},${s.status},${s.risk_score.toFixed(4)},${s.ndwi_moyen?.toFixed(4) ?? ""}`);
  }

  const blob = new Blob(["\ufeff" + rows.join("\r\n")], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `watertracker-rapport-${report.periode}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function PanelRapports() {
  const [report, setReport] = useState<ReportSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<string>("");

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    fetchReportSummary(controller.signal)
      .then((data) => {
        setReport(data);
        setPeriod(data.periodes.at(-1)?.periode ?? "");
      })
      .catch((err: unknown) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Rapport indisponible");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-5 text-sm text-[#a3afbd]">
        <Loader2 className="size-4 animate-spin" /> Chargement du rapport...
      </div>
    );
  }

  if (error || !report) {
    return <div className="p-5 text-sm leading-relaxed text-[#ffb4b4]">{error ?? "Rapport indisponible"}</div>;
  }

  const maxNdwi = Math.max(...report.periodes.map(p => p.ndwi_moyen), 0.5);

  return (
    <div className="p-5 space-y-5">
      <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-[#9fc9ea]">
        <Droplets className="size-4" /> Rapport historique reel
      </div>

      <div className="grid grid-cols-2 gap-2">
        <Metric label="Sources" value={report.total_sources.toString()} />
        <Metric label="Observations" value={report.nb_observations.toString()} />
        <Metric label="Superficie eau" value={`${report.superficie_totale_km2.toFixed(1)} km²`} />
        <Metric label="NDWI global" value={report.ndwi_moyen_global?.toFixed(3) ?? "-"} />
      </div>

      <div>
        <div className="mb-1.5 text-[10px] uppercase tracking-widest text-[#a3afbd]">PERIODE</div>
        <select
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="w-full rounded-md border border-[#2a3140] bg-[#151a21] px-3 py-2 text-sm text-white outline-none"
        >
          {report.periodes.map((d) => <option key={d.periode} value={d.periode}>{d.periode}</option>)}
        </select>
      </div>

      <div>
        <div className="mb-2 text-[10px] uppercase tracking-widest text-[#a3afbd]">NDWI MOYEN PAR PERIODE</div>
        <div className="flex items-end gap-1 h-32 border-b border-[#2a3140]">
          {report.periodes.map((d) => (
            <div key={d.periode} className="group relative flex flex-1 flex-col justify-end" title={`${d.periode} · ${d.ndwi_moyen.toFixed(3)} · ${d.nb_sources} sources`}>
              <div
                className="w-full rounded-t-sm transition hover:opacity-80"
                style={{
                  height: `${Math.max(4, (d.ndwi_moyen / maxNdwi) * 100)}%`,
                  background: statusColor(d.ndwi_moyen),
                  opacity: d.periode === period ? 1 : 0.45,
                }}
              />
            </div>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-2 text-[10px] uppercase tracking-widest text-[#a3afbd]">EVOLUTION DU NDWI</div>
        <div className="relative h-40 w-full border-b border-l border-[#2a3140]/80">
          {(() => {
            const data = report.periodes;
            if (!data.length) return null;
            const minY = Math.min(...data.map((p) => p.ndwi_moyen));
            const maxY = Math.max(...data.map((p) => p.ndwi_moyen));
            const padY = (maxY - minY) * 0.15 || 0.1;
            const yMin = minY - padY;
            const yMax = maxY + padY;
            const toX = (i: number) => (i / (data.length - 1)) * 100;
            const toY = (v: number) => 100 - ((v - yMin) / (yMax - yMin)) * 100;

            const pathD = data
              .map((p, i) => `${i === 0 ? "M" : "L"} ${toX(i).toFixed(1)} ${toY(p.ndwi_moyen).toFixed(1)}`)
              .join(" ");

            const areaD = `${pathD} L 100 100 L 0 100 Z`;

            return (
              <>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
                  <defs>
                    <linearGradient id="ndwi-fill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#9fc9ea" stopOpacity="0.25" />
                      <stop offset="100%" stopColor="#9fc9ea" stopOpacity="0.02" />
                    </linearGradient>
                  </defs>
                  <path d={areaD} fill="url(#ndwi-fill)" vectorEffect="non-scaling-stroke" />
                  <path d={pathD} fill="none" stroke="#9fc9ea" strokeWidth="1.8" vectorEffect="non-scaling-stroke" strokeLinejoin="round" strokeLinecap="round" />
                </svg>
                <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="absolute inset-0 h-full w-full" style={{ pointerEvents: "none" }}>
                  {data.map((p, i) => {
                    const cx = toX(i);
                    const cy = toY(p.ndwi_moyen);
                    const isHighlighted = p.periode === period;
                    return (
                      <g key={p.periode}>
                        <circle
                          cx={cx}
                          cy={cy}
                          r={isHighlighted ? "3.5" : "2"}
                          fill={isHighlighted ? statusColor(p.ndwi_moyen) : "#9fc9ea"}
                          opacity={isHighlighted ? 1 : 0.7}
                          vectorEffect="non-scaling-stroke"
                          style={{ transition: "r 0.2s, fill 0.2s, opacity 0.2s" }}
                        />
                        {isHighlighted && (
                          <circle
                            cx={cx}
                            cy={cy}
                            r="7"
                            fill="none"
                            stroke={statusColor(p.ndwi_moyen)}
                            strokeWidth="1.2"
                            opacity="0.5"
                            vectorEffect="non-scaling-stroke"
                          />
                        )}
                      </g>
                    );
                  })}
                </svg>
                <div className="absolute bottom-0 left-0 right-0 flex justify-between px-0.5 pt-1 text-[8px] text-[#a3afbd]">
                  <span>{data[0].periode}</span>
                  <span>{data.at(-1)!.periode}</span>
                </div>
              </>
            );
          })()}
        </div>
      </div>

      <div>
        <div className="mb-2 text-[10px] uppercase tracking-widest text-[#a3afbd]">REPARTITION PAR ZONE</div>
        <div className="flex flex-wrap gap-1.5">
          {report.zones.map((z) => (
            <span key={z.zone} className="rounded-md border border-[#2a3140] bg-[#151a21] px-2 py-1 text-xs text-white/85">
              {z.zone} <span className="ml-1 text-[#9fc9ea]">×{z.count}</span>
            </span>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-2 text-[10px] uppercase tracking-widest text-[#a3afbd]">STATUTS</div>
        <div className="grid grid-cols-3 gap-2">
          {[
            { k: "actif", l: "ACTIFS", c: "#62e6a6" },
            { k: "à risque", l: "A RISQUE", c: "#e3b341" },
            { k: "tari", l: "TARIES", c: "#ff6b6b" },
          ].map((s) => (
            <div key={s.k} className="rounded-md border border-[#2a3140] bg-[#151a21] p-2 text-center">
              <div className="text-lg font-bold leading-none" style={{ color: s.c }}>{report.statut[s.k] ?? 0}</div>
              <div className="mt-1 text-[9px] tracking-widest text-[#a3afbd]">{s.l}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-widest text-[#9fc9ea]">
          <AlertTriangle className="size-3.5" /> Sources les plus risquees
        </div>
        {report.top_risque.map((s, i) => (
          <div key={s.id} className="flex items-center gap-2 rounded-md border border-[#2a3140] bg-[#151a21] px-3 py-2 text-xs">
            <span className="text-[#a3afbd]">{String(i + 1).padStart(2, "0")}</span>
            <span className="min-w-0 truncate font-semibold text-white">{s.zone_detail ?? `source-${s.id}`}</span>
            <span className="text-[#a3afbd]">#{s.id}</span>
            <span className="ml-auto flex items-center gap-1 font-medium" style={{ color: statusColor(s.risk_score) }}>
              {Math.round(s.risk_score * 100)}%
            </span>
            <span className="w-8 text-right">
              {i > 0 && report.top_risque[i - 1].risk_score > s.risk_score ? (
                <TrendingDown className="ml-auto inline size-3.5 text-[#62e6a6]" />
              ) : (
                <TrendingUp className="ml-auto inline size-3.5 text-[#ff6b6b]" />
              )}
            </span>
          </div>
        ))}
      </div>

      <div className="rounded-md border border-[#2a3140]/60 bg-[#13171e]/65 backdrop-blur-sm p-3 text-[10px] leading-relaxed text-[#a3afbd]">
        Deniere periode calculee : {report.periode} · Generation : {report.date_generation} · Source : observations satellite reelles (ndwi_observations)
      </div>

      <button
        onClick={() => exportCsv(report)}
        className="flex w-full items-center justify-center gap-2 rounded-md border border-[#3a424d] py-2.5 text-[10px] font-bold tracking-widest text-[#9fc9ea] transition hover:bg-[#20262d]"
      >
        <Download className="size-3.5" /> EXPORTER CSV
      </button>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-[#2a3140] bg-[#151a21] p-2">
      <div className="text-[10px] uppercase tracking-[0.14em] text-[#a3afbd]">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-[#9fc9ea]">{value}</div>
    </div>
  );
}