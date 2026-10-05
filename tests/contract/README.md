# Contrôles exécutables des exemples

`test_examples.py` utilise uniquement la bibliothèque standard Python. Il vérifie les identifiants partagés, le rattachement de l'étude, les états d'affichage, les valeurs manquantes et l'absence de champs secrets interdits.

Les tests négatifs modifient une copie en mémoire pour vérifier que les invariants détectent une incohérence.

`example_checks.py` est un validateur ciblé du scénario DEMO-001, pas un schéma universel de réponse API ni un validateur HL7/DICOM.

`test_schemas.py` vérifie aussi les schémas JSON 2020-12 avec `jsonschema` : propriétés requises/interdites, UUID, dates avec fuseau, enums, nullabilité et représentation des valeurs. `test_manifeste.py` vérifie les métadonnées de rapprochement DICOM contre le manifeste. Ce ne sont pas des tests d'un parseur HL7, de droits ou d'un serveur Orthanc.

Depuis un environnement virtuel à la racine :

```bash
python3 -m pip install -r requirements-contrats.txt
python3 -m unittest discover -s tests/contract -v
```

