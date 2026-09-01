export function KpisBar({ total, alerts, area, topSource }: { total: number; alerts: number; area: number; topSource?: { label: string; risk: number } }) {
  const items = [
    { v: total.toString(), l: "SOURCES DÉTECTÉES" },
    { v: topSource ? topSource.label.toUpperCase() : "-", l: topSource ? `+ CRITIQUE · RISK ${Math.round(topSource.risk * 100)}%` : "+ CRITIQUE" },
    { v: `${area.toFixed(1)} km²`, l: "SUPERFICIE TOTALE EAU" },
    { v: alerts.toString(), l: "EN ALERTE CRITIQUE" },
  ];
  return (
    <div className="fixed top-12 inset-x-0 z-30 h-14 overflow-x-auto bg-[#13171e]/55 backdrop-blur-xl border-b border-[#2a3140]/60 sm:h-16 lg:left-[238px] lg:right-[340px] lg:overflow-visible">
      <div className="flex h-full min-w-max lg:grid lg:min-w-0 lg:grid-cols-4">
        {items.map((it, i) => (
          <div
            key={i}
            className={`flex min-w-[150px] flex-col justify-center px-4 sm:min-w-[180px] sm:px-5 lg:min-w-0 ${
              i > 0 ? "border-l border-[#2a3140]/70" : ""
            }`}
          >
            <div className="truncate text-base font-bold leading-none text-[#9fc9ea] sm:text-lg">{it.v}</div>
            <div className="mt-1.5 truncate text-[9px] uppercase tracking-[0.14em] text-[#a3afbd] sm:text-[10px] sm:tracking-[0.16em]">{it.l}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
