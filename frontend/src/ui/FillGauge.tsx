import { percent } from "@/lib/format";
import { STATUS_META, type Status } from "@/lib/sites";

/**
 * Jauge de remplissage, graduée comme une échelle limnimétrique : un trait tous
 * les 20 %, et le seuil critique marqué d'un repère qui dépasse de la jauge.
 */
export function FillGauge({
  fill,
  status,
  critical,
  size = "md",
  showThresholdLabel = false,
}: {
  fill: number | null;
  status: Status;
  critical: number;
  size?: "sm" | "md" | "lg";
  showThresholdLabel?: boolean;
}) {
  const height = size === "lg" ? 18 : size === "md" ? 12 : 8;
  const clamped = fill === null ? 0 : Math.max(0, Math.min(1, fill));
  const color = STATUS_META[status].color;
  const label = fill === null
    ? "Remplissage non mesuré"
    : `Remplissage ${percent(fill)}, seuil critique ${percent(critical)}`;

  return (
    <div className={showThresholdLabel ? "pb-5" : ""}>
      <div
        role="img"
        aria-label={label}
        className="relative w-full rounded-[3px] bg-sunken"
        style={{ height, boxShadow: "inset 0 0 0 1px var(--color-line-strong)" }}
      >
        {fill !== null && (
          <div
            className="absolute inset-y-0 left-0 rounded-l-[3px]"
            // Une retenue presque vide reste visible : au moins 3 px de couleur.
            style={{ width: `max(3px, ${clamped * 100}%)`, background: color, borderRadius: clamped >= 0.995 ? 3 : undefined }}
          />
        )}
        {[0.4, 0.6, 0.8].map((tick) => (
          <span
            key={tick}
            className="absolute inset-y-0 w-px"
            style={{ left: `${tick * 100}%`, background: "rgb(20 34 43 / 0.16)" }}
          />
        ))}
        <span
          className="absolute w-0.5 bg-ink"
          style={{ left: `calc(${critical * 100}% - 1px)`, top: -3, bottom: -3 }}
        />
        {showThresholdLabel && (
          <span
            className="num absolute text-[12px] leading-none text-ink-2 whitespace-nowrap"
            style={{ left: `calc(${critical * 100}% + 5px)`, top: height + 6 }}
          >
            seuil critique {percent(critical)}
          </span>
        )}
      </div>
    </div>
  );
}
