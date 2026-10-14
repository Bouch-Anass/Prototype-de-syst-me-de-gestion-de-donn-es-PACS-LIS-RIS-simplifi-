# Vérifications du pack initial

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

## Contrôles T01/T02 — 13 octobre 2026

Sur Python 3.13.2, `python scripts/check_repo.py` a réussi et `python -m unittest discover -s tests/contract -v` a exécuté 17 tests avec succès. `node --check frontend/app.js` a réussi. Un serveur HTTP local a servi l'aperçu frontend et les trois mocks avec des réponses 200. Le YAML Compose a été parsé localement et ses trois ports sont liés à `127.0.0.1`. Les quatre fixtures HL7 générées sont terminées par `CR` et comparées au manifeste par les tests.

Docker n'est pas disponible sur ce poste : `docker compose config`, les healthchecks, la persistance des volumes et la connexion Orthanc restent à vérifier dans un environnement Docker. L'aperçu frontend a ensuite été inspecté dans Edge aux formats bureau et mobile : chargement des polices, absence de débordement horizontal à 390 px et affichage des états CRP absente/PACS indisponible. Le frontend statique utilise des mocks et ne prouve pas encore les droits, l'audit ou l'intégration métier.
