# Tests d'intégration à implémenter

Ces scénarios seront automatisés avec le backend et les services réels. Ils ne sont pas exécutables dans ce squelette.

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

