import { Droplet, LogOut } from "lucide-react";

export function TopNavbar() {
  return (
<header className="fixed top-0 inset-x-0 z-50 h-12 bg-[#0c0f14]/60 backdrop-blur-xl border-b border-[#2a3140]/60 flex items-center px-5">
      <div className="flex items-center gap-2 text-sm tracking-[0.18em] text-[#9fc9ea] font-bold">
        <Droplet className="size-4" /> WATERTRACKER
      </div>
      <div className="ml-auto flex items-center gap-4">
        <div className="flex items-center gap-2 rounded-md border border-[#2a3140] bg-[#13171e] px-3 py-1">
          <div className="size-6 rounded-full bg-[#20262d] border border-[#3a424d] flex items-center justify-center text-[10px] text-[#9fc9ea]">DM</div>
          <span className="text-[11px] tracking-widest text-white/80">DEMO_USER</span>
        </div>
        <button className="flex items-center gap-1.5 text-[11px] tracking-widest text-[#a3afbd] hover:text-[#9fc9ea] transition">
          <LogOut className="size-3.5" /> EXIT
        </button>
      </div>
    </header>
  );
}
