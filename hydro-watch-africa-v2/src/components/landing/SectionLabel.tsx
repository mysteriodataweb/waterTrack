export function SectionLabel({ index, label }: { index: string; label: string }) {
  return (
    <div className="flex items-center gap-3 font-mono text-[10px] tracking-[0.3em] text-cyan">
      <span className="h-px w-8 bg-cyan/50" />
      SECTION {index} <span className="text-muted-foreground/60">//</span> {label}
    </div>
  );
}
