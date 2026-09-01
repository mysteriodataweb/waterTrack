import { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import { Search, Bell, Settings, User } from "lucide-react";

const navLinks = ["DASHBOARD", "MISSION", "SATELLITE", "TÉLÉMÉTRIE"];

export function Navbar() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <header className="fixed top-0 inset-x-0 z-50 h-14 border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="mx-auto h-full max-w-[1400px] px-6 flex items-center justify-between">
        <Link to="/" className="font-mono text-sm tracking-[0.25em] text-cyan text-glow font-bold">
          ▲ WATERTRACKER
        </Link>
        <nav className="hidden md:flex items-center gap-8 font-mono text-[11px] tracking-[0.2em] text-muted-foreground">
          {navLinks.map((l) => (
            <span key={l} className="opacity-60 cursor-default hover:opacity-100 transition">{l}</span>
          ))}
        </nav>
        <div className="flex items-center gap-4 text-muted-foreground">
          <Search className="size-4 hover:text-cyan transition cursor-pointer" />
          <Bell className="size-4 hover:text-cyan transition cursor-pointer" />
          <Settings className="size-4 hover:text-cyan transition cursor-pointer" />
          <div className="relative" ref={ref}>
            <button
              onClick={() => setOpen(!open)}
              className="size-8 rounded-full border border-cyan/40 bg-cyan/10 flex items-center justify-center hover:bg-cyan/20 transition"
            >
              <User className="size-4 text-cyan" />
            </button>
            {open && (
              <div className="absolute right-0 top-11 w-56 border border-border bg-background/95 backdrop-blur-xl rounded-sm shadow-2xl shadow-cyan/10 overflow-hidden">
                {[
                  { label: "SE CONNECTER", to: "/map" },
                  { label: "S'INSCRIRE", to: "/map" },
                  { label: "ACCÈS DÉMO", to: "/map" },
                ].map((item, i) => (
                  <Link
                    key={i}
                    to={item.to}
                    className="block px-4 py-3 font-mono text-[11px] tracking-[0.2em] text-foreground/80 hover:bg-cyan/10 hover:text-cyan transition border-b border-border last:border-0"
                  >
                    › {item.label}
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
