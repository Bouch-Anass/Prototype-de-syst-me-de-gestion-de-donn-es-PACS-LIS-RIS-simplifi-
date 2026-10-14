# Aperçu web du contrat T02

Cette interface statique ouvre les trois réponses de [contracts/examples](../contracts/examples/README.md). Elle montre la recherche par identifiant exact, la synthèse patient, une CRP manquante et l'indisponibilité du PACS. Elle ne se connecte pas encore au backend, ne fournit pas d'authentification et reste en lecture seule ; le flux applicatif complet appartient à T09.

Depuis la racine du dépôt :

```powershell
py -m http.server 8000 --bind 127.0.0.1
```

Ouvrir `http://127.0.0.1:8000/frontend/`. L'identifiant fictif est `DEMO-P001`. Arrêter le serveur avec Ctrl+C. Aucun paquet npm ni accès Internet n'est nécessaire.

## Direction de design

La référence [DESIGN.md](../DESIGN.md) guide la palette blanche, encre et violet, les bordures fines, les boutons en pilule et la hiérarchie typographique. L'interface reprend ces principes dans un espace de travail compact : recherche en haut, synthèse patient, résultats en liste et rail d'imagerie. Plus Jakarta Sans, Inter et Sometype Mono sont chargées depuis [`frontend/fonts`](fonts/) ; les licences OFL y sont incluses. Aucun logo ou contenu de la marque de référence n'est reproduit.

Décision D11 : HTML/CSS/JavaScript sans framework pour cet aperçu de contrat, afin d'ouvrir les mocks sans dépendances. Ce choix vaut pour le premier jalon ; tout changement de stack ultérieur se consigne avant T09 et garde le contrat API identique.
