import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { MonitoringProvider } from "./lib/monitoring";
import LandingPage from "./views/LandingPage";
import NotFoundPage from "./views/NotFoundPage";

// La carte embarque Leaflet : elle n'est chargée que lorsqu'on l'ouvre.
const CartePage = lazy(() => import("./views/CartePage"));
const BulletinPage = lazy(() => import("./views/BulletinPage"));

/** Ancienne adresse de la carte : on conserve les liens déjà partagés. */
function LegacyMapRedirect() {
  const { search } = useLocation();
  return <Navigate to={`/carte${search}`} replace />;
}

export default function App() {
  return (
    <MonitoringProvider>
      <Suspense fallback={<div className="min-h-dvh bg-canvas" />}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/carte" element={<CartePage />} />
          <Route path="/bulletin" element={<BulletinPage />} />
          <Route path="/map" element={<LegacyMapRedirect />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </MonitoringProvider>
  );
}
