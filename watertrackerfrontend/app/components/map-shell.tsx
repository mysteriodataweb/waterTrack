"use client";

import dynamic from "next/dynamic";

const WaterMap = dynamic(() => import("./map"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[420px] items-center justify-center rounded-[28px] border border-[var(--line)] bg-[var(--surface-strong)] text-sm text-[var(--muted)]">
      Chargement de la carte WaterTracker...
    </div>
  ),
});

export default function MapShell() {
  return <WaterMap />;
}
