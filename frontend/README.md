# Interface web synthétique

Après la connexion, cliquez dans la barre de recherche pour dérouler les dossiers autorisés. Saisissez un nom ou un identifiant pour filtrer les patients affichés. Le médecin consulte les trois domaines ; le technicien de laboratoire peut enregistrer jusqu'à 200 observations par version de rapport (dont des analyses supplémentaires à code local) ; le radiologue peut créer et valider un examen RIS ; le technicien d'imagerie peut sélectionner plusieurs fichiers DICOM et les importer un par un dans le PACS. Les autres domaines restent lisibles pour chaque rôle autorisé à la rencontre. Le mot de passe et les identifiants Orthanc ne sont pas conservés dans le code frontend.

Pour utiliser l'interface, démarrer le backend selon la [démonstration Docker](../docs/DOCKER.md), puis ouvrir `http://127.0.0.1:8000/frontend/`. Une fois `DEMO-P001` et les comptes de démonstration prêts, `python -m app.cli seed-demo-patients` ajoute les dossiers fictifs `DEMO-P002` à `DEMO-P025` dans la base configurée. Aucun paquet npm ni accès Internet n'est nécessaire au frontend. Le serveur HTTP statique seul ne permet plus de se connecter ni de consulter le dossier.

La recherche et l'affichage utilisent l'origine du serveur : pas de CORS ni de requête directe à Orthanc. La session existante est restaurée après actualisation via `/api/v1/auth/me`.

## Direction de design

L’interface reprend la grille compacte, les filets pointillés et la palette olive de la [référence Pulmify](https://dribbble.com/shots/26451832-AI-Powered-Platform-for-Proactive-Health-Monitoring). La barre supérieure contient la recherche. La vue d’ensemble présente les analyses, les examens, les images et les événements de la prise en charge. Les onglets ouvrent le détail de chaque section. Inter et Sometype Mono sont chargées depuis [`frontend/fonts`](fonts/), avec leurs licences OFL.

Décision D11 : HTML/CSS/JavaScript sans framework. Le frontend utilise désormais uniquement le contrat API authentifié ; les exemples JSON restent disponibles pour les tests de contrat.

Le badge « Données fictives » a été retiré de l'en-tête. Le caractère synthétique des données reste indiqué dans la notice du dossier et dans la documentation du projet ; cette modification est uniquement visuelle.
