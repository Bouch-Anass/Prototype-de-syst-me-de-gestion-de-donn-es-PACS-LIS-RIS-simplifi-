# Interface web synthétique

L'interface demande d'abord une connexion au backend, recherche l'identifiant exact et charge la synthèse autorisée. Le médecin consulte les trois domaines ; le technicien de laboratoire peut enregistrer jusqu'à 200 observations par version de rapport (dont des analyses supplémentaires à code local) ; le radiologue peut créer et valider un examen RIS ; le technicien d'imagerie peut sélectionner plusieurs fichiers DICOM et les importer un par un dans le PACS. Les autres domaines restent lisibles pour chaque rôle autorisé à la rencontre. Le mot de passe et les identifiants Orthanc ne sont pas conservés dans le code frontend.

Pour utiliser l'interface, démarrer le backend selon la [démonstration Docker](../docs/DOCKER.md), puis ouvrir `http://127.0.0.1:8000/frontend/`. L'identifiant fictif est `DEMO-P001`. Aucun paquet npm ni accès Internet n'est nécessaire au frontend. Le serveur HTTP statique seul ne permet plus de se connecter ni de consulter le dossier.

La recherche et l'affichage utilisent l'origine du serveur : pas de CORS ni de requête directe à Orthanc. La session existante est restaurée après actualisation via `/api/v1/auth/me`.

## Direction de design

La référence [DESIGN.md](../DESIGN.md) guide la palette blanche, encre et violet, les bordures fines, les boutons en pilule et la hiérarchie typographique. L'interface reprend ces principes dans un espace de travail compact : recherche en haut, synthèse patient, résultats en liste et rail d'imagerie. Plus Jakarta Sans, Inter et Sometype Mono sont chargées depuis [`frontend/fonts`](fonts/) ; les licences OFL y sont incluses. Aucun logo ou contenu de la marque de référence n'est reproduit.

Décision D11 : HTML/CSS/JavaScript sans framework. Le frontend utilise désormais uniquement le contrat API authentifié ; les exemples JSON restent disponibles pour les tests de contrat.

Le badge « Données fictives » a été retiré de l'en-tête. Le caractère synthétique des données reste indiqué dans la notice du dossier et dans la documentation du projet ; cette modification est uniquement visuelle.
