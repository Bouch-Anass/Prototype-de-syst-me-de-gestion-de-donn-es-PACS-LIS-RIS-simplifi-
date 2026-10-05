# T02 — Contrats communs et scénario de référence

Date : 5 octobre 2026. Responsable : **Membre 1** (porteur du projet). Branche : `t02-contrats-communs`. Statut : **contribution préparée pour revue**, pas accord collectif ni implémentation applicative.

## Problème et résultat

Le squelette nommait les interfaces, mais la version HL7, les réponses, l'identité externe, les accès et la structure vérifiable restaient en partie ouverts. Cette contribution propose un contrat v0.1 cohérent pour que les membres puissent développer sur les mêmes exemples.

| Livraison | Preuve |
|---|---|
| Répartition retenue entre six membres et T10 partagé | [Responsabilités](REPARTITION_TRAVAIL.md), [backlog](BACKLOG.md) |
| Identifiants et écart DEMO-001 / scénario PDF | [Identifiants](../contracts/identifiants.md), [manifeste](../data/fixtures/scenario.json) |
| Réponse de synthèse et erreurs vérifiables | [API](../contracts/api.md), [schéma de synthèse](../contracts/schemas/synthese.schema.json), [schéma d'erreur](../contracts/schemas/erreur.schema.json) |
| Profil local HL7 2.5.1 : champs, cardinalités, réponses, reprises | [HL7](../contracts/hl7.md) |
| Rapprochement patient/accession/étude et panne PACS | [Imagerie](../contracts/imaging.md), [métadonnées synthétiques](../data/fixtures/rapprochement-dicom.json) |
| Proposition de session, affectations, audit et accès aux images | [Accès](../contracts/acces.md) |
| Convention française explicite | [Contribution](../CONTRIBUTING.md), [vocabulaire](../contracts/vocabulaire.md) |
| Contrôle automatisé des exemples et du schéma | [Tests](../tests/contract/README.md), workflow GitHub Actions |

## Vérifications locales

Python 3.12 dans un environnement virtuel, dépendances de contrat verrouillées. Les commandes reproductibles sont dans [le guide de démarrage](DEMARRAGE.md). Les résultats sont consignés dans [le journal de vérifications](VERIFICATIONS.md).

Les tests de schémas couvrent UUID, champs inconnus/requis, dates, états, nullabilité, valeurs et absence de fuite via une propriété supplémentaire. Les tests de DEMO-001 vérifient les identifiants communs, l'absence distincte de zéro, le rattachement et la conservation des autres données en panne. Les métadonnées DICOM sont comparées au manifeste ; elles ne constituent pas un fichier DICOM.

Aucun parseur HL7, service FastAPI, session réelle, migration SQL, instance Orthanc ou test de panne réelle n'est livré. Les tests ne prouvent pas la conformité HL7/DICOM, la sécurité d'une API ni les performances annoncées. Ces preuves appartiennent à T03–T11.

## Revue avant adoption

| Relecteur | À vérifier | Avis |
|---|---|---|
| Membre 2 | Session/CSRF, affectations, audit, erreurs et transactions | En attente |
| Membre 3 | HL7 2.5.1, groupes OML/ORU, ORL/ACK, catalogue, corrections et rejouabilité | En attente |
| Membre 4 | Domaine patient DICOM, accession, UID, récupération après autorisation | En attente |
| Membre 5 | Champs de synthèse, libellés français, nullabilité, session et erreurs | En attente |
| Membre 6 | Installation des tests, fixtures, transport local, reproductibilité | En attente |

- [ ] D08 : accepter ou modifier le transport HTTP interne initial.
- [ ] D12 : accepter ou modifier la proposition de session.
- [ ] D13 : accepter ou modifier le profil HL7 avec le Membre 3.
- [ ] D18 : valider la conservation des clés machine avec les libellés français.
- [ ] D19 : accepter DEMO-001 pour l'essai ou revenir au scénario NFS/CRP.
- [ ] Tous les consommateurs approuvent les schémas v0.1 et leurs limites.

Une proposition peut évoluer dans cette branche ; inscrire les motifs dans DECISIONS. Aucun avis ni aucune réunion n'est inventé. Fusion dans `main` après revue humaine ; ne pas marquer T02 « approuvé » sur la seule base d'une CI verte.

## Suite pour chaque membre

Membre 6 : T01 en parallèle. Membres 2–5 : relire les contrats puis préparer les services/interfaces de leur périmètre. Le framework frontend et le viewer restent D11/D14. Après accord, le Membre 1 ouvre T08 sur une autre branche, avec doubles de test conformes aux sorties de services avant connexion aux modules réels.
