# Références

## Documents de conception existants

Les six PDF du projet constituent la source de ses besoins, de ses scénarios et de son modèle métier. Le présent pack les traduit en frontières de code et tâches ; il ne prétend pas qu'un projet externe a été copié.

Les références techniques ci-dessous éclairent les mécanismes utilisés. Elles ne prouvent ni l'exactitude du futur code ni sa conformité.

## Sites consultés pour ce squelette

| Source officielle | Usage dans la proposition |
|---|---|
| [FastAPI : Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) | Organisation d'une même application en modules et routeurs |
| [Orthanc : REST API](https://orthanc.uclouvain.be/book/users/rest.html) | Accès privé au PACS et distinction avec les interfaces DICOM |
| [Orthanc : Security](https://orthanc.uclouvain.be/book/faq/security.html) | Prudence sur l'exposition et les accès au service |
| [PostgreSQL : Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) | Clés, unicité et intégrité relationnelle |
| [Docker Compose : Startup order](https://docs.docker.com/compose/how-tos/startup-order/) | Préparation du futur environnement et vérifications de santé |
| [GitHub : Creating an issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/creating-an-issue) | Transformation du backlog en tâches suivies |
| [GitHub Actions : checkout](https://github.com/actions/checkout) | Récupération du dépôt dans le workflow initial |
| [GitHub Actions : setup-python](https://github.com/actions/setup-python) | Installation de Python pour les contrôles |

Consultation : 28 septembre 2026. Les versions applicatives exactes restent à verrouiller au moment de l'implémentation.

## Références à compléter avec le profil retenu

La version et les sections normatives HL7 et DICOM effectivement implémentées devront être citées dans leurs profils de test lors de T02/T07. Aucune version précise n'est déduite du seul mot « HL7 v2 » ou « DICOM ».

Les questions juridiques et de confidentialité relèvent du document de conception correspondant et d'une revue spécifique avant tout usage réel.

