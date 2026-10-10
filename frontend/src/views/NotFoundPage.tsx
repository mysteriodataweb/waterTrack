import { Link } from "react-router-dom";
import { useTitle } from "@/lib/hooks";
import { AppHeader } from "@/ui/chrome";

export default function NotFoundPage() {
  useTitle("Page introuvable");
  return (
    <div className="min-h-dvh bg-canvas">
      <AppHeader />
      <main className="mx-auto max-w-[40rem] px-4 py-20 sm:px-6">
        <h1 className="text-[36px] text-ink">Cette page n'existe pas.</h1>
        <p className="mt-4 text-[18px] leading-relaxed text-ink-2">
          L'adresse a peut-être changé, ou le lien est incomplet. Les retenues, elles, sont toujours sur la carte.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link
            to="/carte"
            className="inline-flex h-12 items-center rounded-lg bg-water px-5 text-[17px] font-semibold text-white no-underline hover:bg-water-deep"
          >
            Ouvrir la carte
          </Link>
          <Link
            to="/"
            className="inline-flex h-12 items-center rounded-lg border border-line-strong bg-surface px-5 text-[17px] font-semibold text-ink no-underline hover:bg-sunken"
          >
            Revenir à l'accueil
          </Link>
        </div>
      </main>
    </div>
  );
}
