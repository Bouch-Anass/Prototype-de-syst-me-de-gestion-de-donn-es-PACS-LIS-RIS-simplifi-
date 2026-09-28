# Persistance et migrations

Lot A pour la coordination ; B et C pour les migrations de leurs domaines.

Prévoir une session et une frontière transactionnelle explicites par unité de travail, et un historique ordonné de migrations. Les clés étrangères et contraintes matérialisent le modèle documenté.

Ne pas créer les tables silencieusement à chaque requête. Ne pas réécrire une migration déjà utilisée. Les messages HL7 rejetés et l'audit doivent rester traçables malgré un rollback métier.

L'outil de migrations est à choisir en T03 ; aucun script SQL opérationnel n'est livré ici.

