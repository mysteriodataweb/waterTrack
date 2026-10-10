import { STATUS_META, type Status } from "@/lib/sites";

/**
 * Chaque état a sa forme en plus de sa couleur, pour rester lisible sans
 * distinguer les couleurs (daltonisme, impression en noir et blanc).
 */
export function StatusGlyph({ status, size = 12 }: { status: Status; size?: number }) {
  const color = STATUS_META[status].color;
  return (
    <svg width={size} height={size} viewBox="0 0 12 12" aria-hidden="true" className="shrink-0">
      {status === "actif" && <circle cx="6" cy="6" r="5" fill={color} />}
      {status === "à risque" && <path d="M6 0.8 11.6 11H0.4Z" fill={color} />}
      {status === "tari" && <rect x="1" y="1" width="10" height="10" rx="1.5" fill={color} />}
      {status === "inconnu" && <circle cx="6" cy="6" r="4" fill="none" stroke={color} strokeWidth="2" />}
    </svg>
  );
}

export function StatusBadge({ status }: { status: Status }) {
  const meta = STATUS_META[status];
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[13px] font-semibold leading-none whitespace-nowrap"
      style={{ background: meta.soft, color: meta.ink }}
    >
      <StatusGlyph status={status} size={10} />
      {meta.label}
    </span>
  );
}
