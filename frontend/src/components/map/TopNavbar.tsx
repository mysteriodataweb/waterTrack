import { Droplet, LogOut, Menu, SlidersHorizontal } from "lucide-react";

export function TopNavbar({
  onMenuClick,
  onFilterClick,
}: {
  onMenuClick?: () => void;
  onFilterClick?: () => void;
}) {
  return (
    <header className="fixed top-0 inset-x-0 z-50 h-12 bg-[#0c0f14]/60 backdrop-blur-xl border-b border-[#2a3140]/60 flex items-center gap-2 px-3 sm:px-5">
      {onMenuClick && (
        <button
          onClick={onMenuClick}
          className="flex size-9 shrink-0 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white lg:hidden"
          aria-label="Ouvrir le menu"
        >
          <Menu className="size-5" />
        </button>
      )}

      <div className="flex min-w-0 items-center gap-2 text-[11px] font-bold tracking-[0.18em] text-[#9fc9ea] sm:text-sm">
        <Droplet className="size-4 shrink-0" />
        <span className="truncate">WATERTRACKER</span>
      </div>

      <div className="ml-auto flex items-center gap-2 sm:gap-4">
        <div className="hidden items-center gap-2 rounded-md border border-[#2a3140] bg-[#13171e] px-3 py-1 sm:flex">
          <div className="size-6 rounded-full bg-[#20262d] border border-[#3a424d] flex items-center justify-center text-[10px] text-[#9fc9ea]">DM</div>
          <span className="text-[11px] tracking-widest text-white/80">DEMO_USER</span>
        </div>

        <button className="hidden items-center gap-1.5 text-[11px] tracking-widest text-[#a3afbd] transition hover:text-[#9fc9ea] sm:flex">
          <LogOut className="size-3.5" /> EXIT
        </button>

        {onFilterClick && (
          <button
            onClick={onFilterClick}
            className="flex size-9 shrink-0 items-center justify-center rounded-md text-[#a3afbd] transition hover:bg-[#20262d] hover:text-white lg:hidden"
            aria-label="Ouvrir les filtres"
          >
            <SlidersHorizontal className="size-5" />
          </button>
        )}
      </div>
    </header>
  );
}
