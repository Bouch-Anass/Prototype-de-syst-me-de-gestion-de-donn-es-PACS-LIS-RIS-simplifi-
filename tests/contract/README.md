# Contrôles exécutables des exemples

`test_examples.py` utilise uniquement la bibliothèque standard Python. Il vérifie les identifiants partagés, le rattachement de l'étude, les états d'affichage, les valeurs manquantes et l'absence de champs secrets interdits.

Les tests négatifs modifient une copie en mémoire pour vérifier que les invariants détectent une incohérence.

`example_checks.py` est un validateur ciblé du scénario DEMO-001, pas un schéma universel de réponse API ni un validateur HL7/DICOM.

`test_shared_contracts.py` compare les trois messages HL7 générés, les réponses JSON, le manifeste et les clés DICOM. `test_local_env.py` vérifie que l'initialisation des secrets est idempotente et silencieuse sur leurs valeurs. Ces contrôles ne remplacent pas un parseur HL7 ou un test Docker en fonctionnement.

Commande depuis la racine : `python3 -m unittest discover -s tests/contract -v`.

