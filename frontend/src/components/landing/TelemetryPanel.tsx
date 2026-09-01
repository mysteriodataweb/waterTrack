import { Satellite, Wifi } from "lucide-react";

const stats = [
  ["ALTITUDE", "786 KM"],
  ["VITESSE", "7.66 KM/S"],
  ["SURFACE_EAU", "2.8 KM²"],
  ["NDWI_INDEX", "HIGH_PRECISION"],
];

export function TelemetryPanel() {
  return (
    <div className="relative border border-cyan/30 bg-background/60 backdrop-blur-xl rounded-sm overflow-hidden glow-cyan">
      {/* Corner brackets */}
      <CornerBrackets />

      <div className="flex items-center justify-between px-4 py-2.5 border-b border-cyan/20 bg-cyan/5">
        <div className="flex items-center gap-2 font-mono text-[10px] tracking-[0.2em] text-cyan">
          <Satellite className="size-3" />
          TELEMETRY_STREAM [SENTINEL-2]
        </div>
        <Wifi className="size-3 text-status-active animate-pulse" />
      </div>

      <div className="grid grid-cols-2 gap-px bg-cyan/10">
        {stats.map(([label, value]) => (
          <div key={label} className="bg-background/80 p-4">
            <div className="font-mono text-[9px] tracking-[0.25em] text-muted-foreground mb-1.5">{label}</div>
            <div className="font-mono text-base font-bold text-cyan">{value}</div>
          </div>
        ))}
      </div>

      {/* Animated chart */}
      <div className="p-4 border-t border-cyan/20">
        <div className="flex items-center justify-between font-mono text-[9px] tracking-[0.2em] text-muted-foreground mb-2">
          <span>SIGNAL_TRACE</span>
          <span className="text-status-active">● LIVE</span>
        </div>
        <svg viewBox="0 0 300 80" className="w-full h-20">
          <defs>
            <linearGradient id="grad" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#00d4ff" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#00d4ff" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path
            d="M0,50 L30,40 L60,55 L90,30 L120,45 L150,20 L180,38 L210,25 L240,40 L270,15 L300,30 L300,80 L0,80 Z"
            fill="url(#grad)"
          />
          <path
            d="M0,50 L30,40 L60,55 L90,30 L120,45 L150,20 L180,38 L210,25 L240,40 L270,15 L300,30"
            fill="none"
            stroke="#00d4ff"
            strokeWidth="1.5"
            strokeDasharray="600"
            style={{ animation: "draw-line 4s linear infinite" }}
          />
        </svg>
        <div className="flex justify-between font-mono text-[8px] text-muted-foreground/60 mt-1 tracking-widest">
          <span>00:00</span><span>06:00</span><span>12:00</span><span>18:00</span><span>NOW</span>
        </div>
      </div>
    </div>
  );
}

function CornerBrackets() {
  const c = "absolute size-3 border-cyan";
  return (
    <>
      <span className={`${c} top-0 left-0 border-t border-l`} />
      <span className={`${c} top-0 right-0 border-t border-r`} />
      <span className={`${c} bottom-0 left-0 border-b border-l`} />
      <span className={`${c} bottom-0 right-0 border-b border-r`} />
    </>
  );
}
