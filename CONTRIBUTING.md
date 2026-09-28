# Conventions de contribution

## Un changement, une responsabilité claire

Une branche porte un périmètre borné, par exemple `feat/lab-ingestion`, `feat/ris-workflow` ou `docs/api-contract`. Les identifiants T01 à T12 peuvent être mentionnés dans les descriptions sans être confondus avec les numéros GitHub.

Une pull request indique le comportement ajouté, les contrats modifiés, les migrations, les tests et les limites connues. Les modifications transversales sont revues par les lots producteurs et consommateurs.

## Fichiers partagés

`contracts/`, `data/fixtures/scenario.json` et le modèle de données constituent les points de coordination. Une incompatibilité est annoncée avant intégration, pas découverte par le frontend à l'exécution.

Chaque domaine est propriétaire de ses tables et services. Le lot A coordonne l'ordre des migrations. Il n'y a pas de réécriture d'une migration déjà appliquée.

## Validation

```bash
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

