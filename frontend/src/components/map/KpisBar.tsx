export function KpisBar({ total, alerts, area, topSource }: { total: number; alerts: number; area: number; topSource?: { label: string; risk: number } }) {
  const items = [
    { v: total.toString(), l: "SOURCES DÉTECTÉES" },
    { v: topSource ? topSource.label.toUpperCase() : "-", l: topSource ? `+ CRITIQUE · RISK ${Math.round(topSource.risk * 100)}%` : "+ CRITIQUE" },
    { v: `${area.toFixed(1)} km²`, l: "SUPERFICIE TOTALE EAU" },
    { v: alerts.toString(), l: "EN ALERTE CRITIQUE" },
  ];
  return (
<div className="fixed top-12 left-[238px] right-[340px] z-30 h-16 bg-[#13171e]/55 backdrop-blur-xl border-b border-[#2a3140]/60 grid grid-cols-4">
        {items.map((it, i) => (
          <div key={i} className={`px-5 flex flex-col justify-center ${i > 0 ? "border-l border-[#2a3140]/70" : ""}`}>
            <div className="text-lg font-bold text-[#9fc9ea] leading-none">{it.v}</div>
            <div className="mt-1.5 text-[10px] uppercase tracking-[0.16em] text-[#a3afbd]">{it.l}</div>
        </div>
      ))}
    </div>
  );
}
