# Projet de fin de formation (Independent Project) — WaterTracker

Ce dossier rassemble les livrables du projet indépendant de TamTam Digital School (consignes : `Independent Project Guidelines 2026.pdf` à la racine du dépôt).

## Contenu

| Fichier | Rôle |
|---|---|
| `WaterTracker_IP_2026_Report.docx` | Le rapport, au format Word demandé (Times New Roman 12, interligne 1,5, marges 1 pouce, pages i, ii… puis 1, 2…, références APA 7) |
| `WaterTracker_IP_2026_Report.pdf` | Le même rapport en PDF |
| `defense_QA.md` | Questions probables du jury et éléments de réponse (en anglais) |
| `report/*.md` | Le texte source du rapport (à modifier ici, puis reconstruire) |
| `figures/` | Figures en anglais, retracées à partir des résultats du notebook |
| `scripts/` | Génération des figures, du rapport Word, de la table des matières et du PDF |
| `../../backend/notebooks/WaterTracker_pipeline.ipynb` | Le notebook de recherche, traduit en anglais, d'où viennent tous les chiffres |
| `../../reportbackend.md` | Rapport technique du backend, mis à jour (annexe possible) |

Support de soutenance (14 diapositives avec notes de l'orateur) : https://claude.ai/artifact/Kjd4UZgkF4RvGnGbXDDDt5. Il se télécharge en PowerPoint ou en PDF.

## Correspondance avec les consignes

| Exigence des consignes | Où |
|---|---|
| Page de garde | Rapport, page 1 |
| Abstract (150-250 mots) | 241 mots |
| Listes des figures, des tableaux, des acronymes | Pages ii à vi (listes générées automatiquement) |
| Remerciements | Page vii (à compléter) |
| Executive summary (300-500 mots) | 467 mots |
| Problem statement (300-600 mots) | Section 1.1 |
| Literature review (900-1500 mots) | Section 1.2 |
| Objectives | Section 1.3, avec questions de recherche et hypothèses (tableau 1) |
| Figure 1 : diagramme des étapes du projet | Section 1.3 |
| Theoretical framework | Section 2 |
| Methodology | Section 3 |
| Results and analysis | Section 4 |
| Discussion | Section 5 |
| Conclusion and recommendations | Section 6 |
| Références APA 7 | 31 références, toutes vérifiées |
| Annexes | A à D (reproductibilité, scores complets, architecture et API, variables) |
| Table des matières automatique | Après l'executive summary |

## À faire avant de rendre

1. **Compléter les champs entre crochets** : nom de l'étudiant, programme, encadrant, date (page de garde, dans `scripts/build_report.js`, constante `COVER`), nom de l'encadrant et remerciements personnels (`report/01_front_intro.md`), et les mêmes champs sur la diapositive de couverture.
2. **Insérer le logo** de l'école sur la page de garde (à la place de « [Insert Institution Logo] »).
3. **Renommer les fichiers** selon la convention : `Nom_Prenom_IP_2026.docx`, `Nom_Prenom_IP_2026.pdf`, etc.
4. **Ouvrir le .docx dans Word et mettre à jour les champs** (Ctrl+A puis F9) : la table des matières et les listes sont déjà remplies, mais Word recalcule les numéros de page avec ses propres polices.
5. **Relire la page « Scope »** (section 1.3) et la section 5.5 : elles indiquent que les besoins des utilisateurs n'ont pas été enquêtés. Si tu as fait des entretiens, ajoute-les : c'est un point fort pour le critère « pertinence du thème ».
6. **Figures marquées « Labels in French »** (carte de la zone, surface totale, erreur par mois, fiabilité, éventail de prévision) : ce sont les sorties d'origine du notebook. Relancer le notebook (qui est maintenant en anglais) les régénère avec des libellés anglais ; il suffit ensuite de reconstruire le rapport.

## Reconstruire le rapport

Depuis la racine du dépôt :

```bash
pip install matplotlib pillow           # figures
python3 docs/independent-project/scripts/build_all.py
```

Il faut Node.js avec le paquet `docx`, et LibreOffice avec `python3-uno` (pour remplir la table des matières et produire le PDF). Le script régénère les figures anglaises, le .docx et le .pdf.

## Points d'attention pour la soutenance

- Les résultats négatifs sont présentés comme des résultats : pas de gain à 2-3 mois, aucun apport d'une prévision parfaite des pluies. C'est ce qui rend le reste crédible.
- La principale faiblesse méthodologique à assumer : la règle d'alerte « calendrier seul » n'a pas été évaluée (section 5.3).
- Les recommandations sur les utilisateurs (programmes d'irrigation et d'élevage, ONG, agences de l'eau) sont des déductions, pas une demande observée.
