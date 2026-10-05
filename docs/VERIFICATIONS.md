# Vérifications du pack initial

## T02 — vérifications du 5 octobre 2026

- Dépendances de tests installées depuis `requirements-contrats.txt` ; `pip check` sans conflit.
- Suite de contrat : **26 tests réussis** (13 historiques et 13 nouveaux).
- Les nouveaux tests couvrent les schémas JSON, les erreurs, la nullabilité et les métadonnées communes de rapprochement.
- Documentation et liens locaux vérifiés avec `scripts/check_repo.py` après intégration.
- Validation locale seulement à ce stade ; aucun test d'API, de droits réels, de parseur HL7 ou d'instance Orthanc. L'état du workflow distant est à consulter sur GitHub après publication.

## Historique du 28 septembre 2026

Contrôles réalisés le 28 septembre 2026 avec Python 3.12.14.

| Vérification | Résultat |
|---|---|
| Présence des fichiers requis | Réussite |
| Résolution des liens Markdown locaux | Réussite |
| Parsing des quatre fichiers JSON | Réussite |
| Tests ciblés des exemples | 13 tests réussis |
| Contrôles négatifs sur valeurs manquantes, identité, accession et rattachement | Réussite |

Ces vérifications concernent uniquement les documents et les données d'exemple. Elles ne prouvent pas le fonctionnement d'une API, l'intégration à Orthanc ou la conformité d'un message HL7.

Les diagrammes sont fournis en Mermaid, modifiables dans les fichiers Markdown et destinés au rendu GitHub. Leur rendu sur GitHub n'a pas été contrôlé ici.

Le workflow GitHub Actions est fourni mais n'a pas été exécuté à distance. Aucune application, base de données, instance Orthanc ou infrastructure Docker n'a été démarrée pour valider ce squelette.

Les six PDF existants n'ont pas été modifiés. Aucun commit, push, ticket ou dépôt GitHub distant n'a été créé.
