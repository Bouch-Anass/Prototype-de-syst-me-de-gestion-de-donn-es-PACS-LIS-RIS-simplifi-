# Suggestions pour présenter la démonstration

## Préparer avant la présentation

- Construire et démarrer les trois services avec le [guide Docker](../infra/README.md), puis vérifier qu'ils sont `healthy`. Faire le téléchargement des images et dépendances avant la séance.
- Ouvrir **http://127.0.0.1:8000/frontend/**, choisir **API locale** et vérifier le compte `demo-doctor`. Utiliser exactement cette origine, configurée pour la session et les contrôles CSRF.
- Préparer `DEMO-P001` et lancer `python3 scripts/smoke_live.py --username demo-doctor`. Le script demande le mot de passe sans l'afficher.
- Garder les identifiants hors des diapositives et du terminal projeté. Sur le poste déjà préparé, ils sont conservés dans `infra/.secrets/demo_accounts.json` ; sur un clone vierge, créer les comptes selon le [guide](DEMO.md).
- Préparer une capture de la synthèse nominale pour expliquer le résultat si un problème matériel survient. Présenter explicitement une capture comme telle.

## Déroulé conseillé : 5 à 7 minutes

| Durée indicative | Action | Message à expliquer |
| --- | --- | --- |
| 30 secondes | Présenter le besoin | Réunir biologie, radiologie et imagerie autour d'un même patient fictif et d'une rencontre. |
| 45 secondes | Montrer les trois services Docker sains | L'application sert l'interface et l'API ; PostgreSQL conserve les données métier ; Orthanc conserve les images. |
| 1 minute | Se connecter, rechercher `DEMO-P001`, ouvrir la rencontre | Le dossier est consulté avec une session et un droit d'accès à la rencontre. |
| 1 minute | Montrer les résultats biologiques et le compte rendu RIS | Les informations de plusieurs domaines apparaissent dans une synthèse commune. |
| 1 minute | Ouvrir **Afficher l'aperçu** | Le PNG est récupéré via une route authentifiée du backend ; le navigateur ne reçoit pas les identifiants Orthanc. |
| 1 minute | Expliquer l'architecture et le résultat du smoke test | Le contrôle a vérifié connexion, recherche, synthèse et aperçu sur les données existantes. |
| 30 secondes | Présenter les limites et la suite | Données fictives, aperçu non diagnostique, initialisation depuis un clone vierge et mesures complètes encore à valider. |

Phrase possible pour décrire la correction : « PostgreSQL et Orthanc fonctionnaient déjà, mais l'application web n'était pas dans Docker. J'ai ajouté son image, son service Compose et le démarrage avec migrations. Le test a ensuite révélé un fichier de métadonnées oublié dans l'image ; je l'ai ajouté et j'ai vérifié le dossier et l'aperçu de bout en bout sur les données existantes. »

## Variantes à répéter avant de les montrer en direct

**Panne PACS :** après le parcours nominal, arrêter uniquement Orthanc avec `docker compose -f infra/compose.yaml stop orthanc`, puis recharger la synthèse. Le comportement attendu est de conserver LIS/RIS et de signaler l'imagerie indisponible. Relancer avec `docker compose -f infra/compose.yaml start orthanc`, attendre `healthy`, puis vérifier le retour de l'aperçu. Sur Compose V1, utiliser le préfixe compatible documenté dans le guide infrastructure en remplaçant la commande finale. Ce scénario n'a pas été rejoué pendant la mise en route du 10 novembre.

**CRP absente :** utiliser le scénario mock prévu par l'interface, en annonçant clairement le mode mocks, ou une base isolée préparée à l'avance. Expliquer qu'une valeur absente n'est jamais remplacée par zéro. Éviter de mélanger cette variante avec le scénario nominal déjà ingéré.

**Échanges HL7/DICOM :** si la présentation porte sur l'interopérabilité, réserver une séance répétée avec les simulateurs du [guide](DEMO.md). Montrer un ACK HL7 et le rapprochement d'étude seulement après les avoir testés sur cette installation. Le smoke test de consultation ne prouve pas une nouvelle ingestion.

## Améliorations proposées après la démonstration

1. Rendre l'initialisation complète d'une base vierge reproductible, avec création explicite des comptes et ingestion synthétique.
2. Répéter le parcours complet cinq fois et consigner les résultats.
3. Tester la panne Orthanc et la persistance après arrêt/redémarrage de la stack sans supprimer les volumes.
4. Ajouter une vérification du parcours réel dans le navigateur, puis mesurer le p95 de la synthèse et le délai d'intégration HL7.

Ces éléments sont des propositions de validation, pas des fonctionnalités ou des résultats déjà acquis. Les [preuves de la mise en route](DOCKER_FIX.md) distinguent les contrôles réalisés des étapes restantes.
