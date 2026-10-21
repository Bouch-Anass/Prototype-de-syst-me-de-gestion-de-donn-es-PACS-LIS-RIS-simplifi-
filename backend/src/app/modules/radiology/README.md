# Module radiology

Lot C.

Responsabilité : Workflow RIS, demandes, examens et compte rendu courant.

Tables : radiology_order, radiology_exam, radiology_report.

Invariants : Examen et étude distincts ; validation réservée au rôle autorisé ; historique textuel à décider avant de le revendiquer.

Le service interne `service.py` crée une demande et son examen programmé pour une rencontre synthétique autorisée. Un médecin ou radiologue peut créer la demande ; seul un radiologue disposant de l'accès explicite à la rencontre peut marquer l'examen réalisé, rédiger puis valider le compte rendu. Les transitions sont `scheduled → performed` pour l'examen et `draft → final` pour le compte rendu. La date de réalisation doit être dans la rencontre ; la validation doit lui être postérieure. L'accession est unique globalement dans la base. La validation termine la demande.

Le compte rendu final est immuable : le schéma actuel conserve uniquement le compte rendu courant et ne permet pas de revendiquer un historique de corrections. Chaque mutation et son audit sont dans la même transaction. `get_encounter_exams` prépare la projection pour T08 après contrôle d'accès par le service appelant.

Les routes d'écriture proposées dans `contracts/api.md` ne sont pas encore exposées ; elles devront reprendre session, CSRF, erreurs et audit de refus de T03. Le seed `seed-radiology-demo` reste une préparation technique des fixtures T07. Les transitions concurrentes et PostgreSQL restent à tester.

