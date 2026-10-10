import { useEffect, useState } from "react";

export function useTitle(title: string) {
  useEffect(() => {
    document.title = title ? `${title} · WaterTracker` : "WaterTracker";
  }, [title]);
}

export function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return matches;
}
