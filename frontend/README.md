# Interface web synthétique

L'interface propose deux modes. **Scénarios fictifs** lit les trois réponses de [contracts/examples](../contracts/examples/README.md) sans backend. **API locale** utilise une session du backend, recherche l'identifiant exact, charge les rencontres autorisées et la synthèse, puis affiche un aperçu PNG si l'étude est disponible. Le mot de passe et les identifiants Orthanc ne sont pas conservés dans le code frontend. L'interface reste en lecture seule ; les écritures RIS passent par les routes API.

Depuis la racine du dépôt :

```powershell
py -m http.server 8000 --bind 127.0.0.1
```

Ouvrir `http://127.0.0.1:8000/frontend/`. L'identifiant fictif est `DEMO-P001`. Arrêter le serveur avec Ctrl+C. Aucun paquet npm ni accès Internet n'est nécessaire.

Pour le mode API, ouvrir la même URL servie par FastAPI après la procédure de [démonstration locale](../docs/DEMO.md). La recherche et l'affichage utilisent l'origine du serveur : pas de CORS ni de requête directe à Orthanc. Les contrôles d'accès ont été testés côté API sur SQLite ; le parcours dans un navigateur avec PostgreSQL/Orthanc réel reste à vérifier.

## Direction de design

La référence [DESIGN.md](../DESIGN.md) guide la palette blanche, encre et violet, les bordures fines, les boutons en pilule et la hiérarchie typographique. L'interface reprend ces principes dans un espace de travail compact : recherche en haut, synthèse patient, résultats en liste et rail d'imagerie. Plus Jakarta Sans, Inter et Sometype Mono sont chargées depuis [`frontend/fonts`](fonts/) ; les licences OFL y sont incluses. Aucun logo ou contenu de la marque de référence n'est reproduit.

Décision D11 : HTML/CSS/JavaScript sans framework pour conserver les mocks sans dépendances. Le mode API T09 réutilise les mêmes composants d'affichage et le contrat de synthèse.
