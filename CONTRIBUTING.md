# Conventions de contribution

## Un changement, une responsabilité claire

Une branche porte un périmètre borné, par exemple `t02-contrats-communs`, `feat/t05-ingestion-laboratoire` ou `feat/t06-parcours-radiologie`. Les identifiants T01 à T12 sont des tâches locales, pas des numéros d'issues GitHub. Publier une pull request en brouillon dès la première contribution vérifiable, puis demander une revue avant fusion dans `main`.

## Langue du projet

Documentation, commentaires, docstrings, libellés de l'interface, messages destinés aux utilisateurs, titres d'issues, commits et descriptions de PR sont en français. Les nouveaux identifiants Python propres au projet sont en français sans accents, en `snake_case` : `composer_dossier`, `verifier_acces`, `identifiant_patient`.

Les chemins, clés JSON, noms SQL, codes d'erreur et états machine existants restent stables pour ce contrat v0.1 : `encounter`, `missing`, `LAB_RESULT_MISSING`, etc. Leur signification française est documentée dans [le vocabulaire](contracts/vocabulaire.md). Leur conservation est une décision explicite de compatibilité, pas une consigne d'écrire les nouveaux libellés en anglais. Les symboles imposés par Python, les bibliothèques, HL7 et DICOM restent inchangés. Toute traduction future de l'interface machine modifie ensemble contrat, producteurs, consommateurs et tests.

Une pull request indique le comportement ajouté, les contrats modifiés, les migrations, les tests et les limites connues. Les modifications transversales sont revues par les lots producteurs et consommateurs.

## Fichiers partagés

`contracts/`, `data/fixtures/scenario.json` et le modèle de données constituent les points de coordination. Une incompatibilité est annoncée avant intégration, pas découverte par le frontend à l'exécution.

Chaque domaine est propriétaire de ses tables et services. Le lot A coordonne l'ordre des migrations. Il n'y a pas de réécriture d'une migration déjà appliquée.

## Validation

```bash
python3 -m pip install -r requirements-contrats.txt
python3 scripts/check_repo.py
python3 -m unittest discover -s tests/contract -v
```

Ces contrôles sont la base initiale. Chaque lot ajoute ses tests applicatifs au fur et à mesure. Une CI documentaire verte ne signifie pas que le système clinique fonctionne.

## Hygiène du dépôt

- Ne commiter ni secret, ni dump de base, ni données réelles.
- N'utiliser que les données synthétiques convenues.
- Ne pas déposer de gros fichiers DICOM dans Git par défaut.
- Conserver les dépendances et versions reproductibles une fois l'outillage choisi.
- Éviter de mêler un changement fonctionnel et une réorganisation générale.
- Ne pas modifier les six documents de conception pour masquer une différence d'implémentation ; consigner la décision.

## Fermeture d'une tâche

La preuve attendue associe un comportement, une assertion automatisée et une documentation exacte. Les captures d'écran peuvent compléter cette preuve, mais ne remplacent pas les tests d'intégrité, de droits et de rejouabilité.

