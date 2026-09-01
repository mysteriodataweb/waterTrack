import { Globe, Mail, MessageCircle } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background/60">
      <div className="mx-auto max-w-[1400px] px-6 py-10 grid grid-cols-1 md:grid-cols-3 items-center gap-6">
        <div className="font-mono text-sm tracking-[0.25em] text-cyan font-bold">▲ WATERTRACKER</div>
        <nav className="flex items-center justify-center gap-8 font-mono text-[10px] tracking-[0.25em] text-muted-foreground">
          <a className="hover:text-cyan transition">PRIVACY</a>
          <a className="hover:text-cyan transition">CONDITIONS</a>
          <a className="hover:text-cyan transition">API DOCS</a>
        </nav>
        <div className="flex items-center justify-end gap-5 text-muted-foreground">
          <Globe className="size-4 hover:text-cyan transition cursor-pointer" />
          <MessageCircle className="size-4 hover:text-cyan transition cursor-pointer" />
          <Mail className="size-4 hover:text-cyan transition cursor-pointer" />
        </div>
      </div>
      <div className="border-t border-border py-4">
        <div className="mx-auto max-w-[1400px] px-6 font-mono text-[10px] tracking-[0.2em] text-muted-foreground/60 text-center">
          © 2026 WATERTRACKER — INSTITUT 2IE, OUAGADOUGOU
        </div>
      </div>
    </footer>
  );
}
