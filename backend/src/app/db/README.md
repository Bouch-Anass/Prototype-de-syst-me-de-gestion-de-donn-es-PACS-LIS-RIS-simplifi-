# Persistance et migrations

Lot A pour la coordination ; B et C pour les migrations de leurs domaines.

Prévoir une session et une frontière transactionnelle explicites par unité de travail, et un historique ordonné de migrations. Les clés étrangères et contraintes matérialisent le modèle documenté.

Ne pas créer les tables silencieusement à chaque requête. Ne pas réécrire une migration déjà utilisée. Les messages HL7 rejetés et l'audit doivent rester traçables malgré un rollback métier.

T03 utilise SQLAlchemy 2 et Alembic. La migration `0001_t03` crée les tables transversales et l'identité ; `0002_domains` ajoute les tables laboratoire, radiologie et imagerie dans le même historique. La migration est lancée explicitement avant le service, jamais implicitement lors d'une requête.

