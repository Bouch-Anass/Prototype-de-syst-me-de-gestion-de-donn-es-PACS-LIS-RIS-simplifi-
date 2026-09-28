# Interface web

Lot D. Le framework reste à confirmer en T02 ; React avec TypeScript est une option. Aucun projet frontend exécutable ni dépendance npm n'est encore fourni.

| Domaine d'écran | Fonction |
|---|---|
| Authentification | Connexion, expiration et refus d'accès |
| Recherche patient | Recherche exacte et sélection d'une rencontre |
| Dossier | Composition des sections et avertissements |
| Laboratoire | Valeurs, unités, états manquant/invalide et versions affichées |
| Radiologie | Demandes, examens et compte rendu |
| Imagerie | Disponibilité et ouverture contrôlée du viewer |

Les [mocks JSON](../contracts/examples/README.md) permettent un démarrage indépendant. Le client HTTP partagé appelle uniquement le backend. Les messages d'erreur et les états de chargement sont des comportements à tester.

Les fonctions de validation biologique ou de comptes rendus ne sont pas implicitement incluses dans le premier écran médecin ; elles nécessitent leurs routes et droits propres.

