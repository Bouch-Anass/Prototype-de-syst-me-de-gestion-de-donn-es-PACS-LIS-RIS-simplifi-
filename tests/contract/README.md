# Contrôles exécutables des exemples

`test_examples.py` utilise uniquement la bibliothèque standard Python. Il vérifie les identifiants partagés, le rattachement de l'étude, les états d'affichage, les valeurs manquantes et l'absence de champs secrets interdits.

Les tests négatifs modifient une copie en mémoire pour vérifier que les invariants détectent une incohérence.

`example_checks.py` est un validateur ciblé du scénario DEMO-001, pas un schéma universel de réponse API ni un validateur HL7/DICOM.

Commande depuis la racine : `python3 -m unittest discover -s tests/contract -v`.

