# Plan d'intégration

Les tests backend couvrent sur SQLite, avec faux Orthanc, une partie de ces scénarios : ingestion HL7, versions, CRP manquante, rapprochement, panne PACS, synthèse, droits, audit et aperçu. `test_postgres_concurrency.py` exécute les courses et le parcours API sur une base PostgreSQL locale fraîche lorsque `PG_TEST_DATABASE_URL` est défini. L'URL doit viser `127.0.0.1` ou `localhost` et une base nommée `*_test`, migrée à `0002_domains` et vide de patients ; sans cette variable, le test est ignoré. Le parcours PostgreSQL 17/Orthanc Docker et les pannes de vrais services restent à exécuter. La [procédure locale](../../docs/DEMO.md) décrit leur préparation.

| ID | Scénario | Assertions attendues |
|---|---|---|
| I01 | Seed synthétique | Identités et rencontres cohérentes |
| I02 | OML puis ORU valides | Demande et résultats rattachés ; ACK après commit |
| I03 | Rejeu identique | Compteurs métier inchangés ; tentative tracée |
| I04 | Même ID, contenu différent | Conflit ; aucune altération métier |
| I05 | Deux réceptions concurrentes | Un seul traitement métier réussi |
| I06 | Correction biologique | Nouvelle version ; précédente conservée |
| I07 | CRP manquante | Valeur nulle, avertissement, glucose inchangé |
| I08 | Patient inconnu | Rejet contrôlé ; aucune création implicite |
| I09 | Import DICOM nominal | Patient/accession/UID concordants |
| I10 | Identité DICOM contradictoire | Aucun rattachement automatique |
| I11 | Étude partielle | État incomplet selon l'attente du scénario |
| I12 | Orthanc arrêté | Synthèse HTTP 200 dégradée, laboratoire intact |
| I13 | PostgreSQL arrêté | Readiness 503 et pas de fausse réponse métier |
| I14 | Accès interdit | Refus, absence de données et audit |
| I15 | Audit indisponible | Opération clinique refusée selon D10 |
| I16 | Accès viewer hors contexte | Refus même avec un identifiant connu |

Isoler les données de chaque essai. Les pannes simulées visent exclusivement les services de démonstration.

Mesurer séparément latence de synthèse sans pixels et temps d'ingestion HL7. Conserver environnement, nombre d'essais et percentiles, pas seulement une mesure unique.

