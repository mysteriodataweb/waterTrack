# WaterTracker — frontend

Interface web du suivi des retenues d'eau autour de Ouagadougou : carte, fiche par retenue
(remplissage mesuré, prévision à trois mois, historique, itinéraire, conseil) et bulletin mensuel.

React 19, TypeScript, Vite, Tailwind CSS 4, Leaflet. Interface en français.

## Démarrer

```bash
npm install
npm run dev        # http://localhost:5173
```

Le backend doit tourner sur `http://127.0.0.1:8000` (voir `../backend/README.md`). En local, les
appels `/api/...` partent en relatif et Vite les relaie vers le backend : aucune variable
d'environnement ni réglage CORS n'est nécessaire.

En production, définir `VITE_API_URL` (adresse du backend déployé) au moment du build.

```bash
npm run build      # vérification TypeScript puis build dans dist/
npm run lint
```

## Pages

| Adresse | Contenu |
|---|---|
| `/` | Présentation, et les cinq retenues les plus menacées du dernier bulletin |
| `/carte` | Carte et liste des plans d'eau ; `?retenue=R16` ouvre une fiche, `&vue=itineraire` l'itinéraire |
| `/bulletin` | Tableau de toutes les retenues suivies, export CSV, impression |

`/map` (ancienne adresse) redirige vers `/carte`.

## Organisation

```
src/
  lib/      accès API, modèle « plan d'eau », formats, géolocalisation, état partagé
  ui/       jauge de remplissage, graphiques, états, en-tête
  carte/    carte Leaflet, liste, fiche, itinéraire, conseil
  views/    une page par fichier
```

## Données affichées

- `/api/bulletin` : état et prévision de chaque retenue (source principale).
- `/api/water-sources` : inventaire des points d'eau, lu page par page.
- `/api/reservoirs/{id}/history` : série mensuelle d'une retenue.
- `/api/water-sources/{id}/prediction` : conseil rédigé, demandé à la main depuis la fiche.
- `/api/navigation/route` et `/reverse` : itinéraire.
- `public/water-polygons.geojson` : contours OpenStreetMap des plans d'eau.

Sans bulletin côté serveur, la carte reste utilisable avec l'inventaire seul.
