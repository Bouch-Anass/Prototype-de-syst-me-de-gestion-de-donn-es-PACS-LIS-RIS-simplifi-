# Contrat HL7 v2 ciblé

## Périmètre

Le premier parcours importe une demande de laboratoire puis ses résultats depuis un simulateur. Les messages ciblés sont `OML^O21` et `ORU^R01`.

Le premier [profil local](hl7-profile.md) fixe HL7 v2.5.1, les segments et champs acceptés, l'encodage, le fuseau, les acquittements et le transport. Les [messages synthétiques](../data/hl7/README.md) sont vérifiés par les tests de contrat ; ils ne prouvent pas une conformité universelle HL7.

## Mapping sémantique du premier jalon

| Information HL7 | Destination | Vérification |
|---|---|---|
| Émetteur et identifiant de contrôle du message, notamment MSH-10 | `inbound_message` | Unicité par source, présence et cohérence |
| Identifiant patient et autorité d'affectation dans PID | `patient` | Correspondance exacte domaine/identifiant |
| Référence de rencontre selon le profil retenu | `encounter` | Rencontre existante du bon patient |
| Références de demande et d'examen dans les groupes ORC/OBR du profil | `lab_order`, `lab_report` | Aucun rattachement par simple ordre d'arrivée |
| Code, type, valeur, unité et état d'observation dans OBX | `lab_observation` | Type, code local et cohérence de valeur |
| État de résultat et correction selon le profil | Version du rapport | Pas d'écrasement silencieux |

Ce tableau n'est pas une grammaire de message. Les positions et cardinalités du sous-ensemble DEMO-001 sont fixées dans le [profil local](hl7-profile.md), notamment pour OML. Les tests de parsing devront utiliser ce profil, pas une liste de segments supposée universelle.

## Chaîne de traitement

1. Vérifier l'origine et la taille autorisée avant parsing.
2. Parser et valider le profil ciblé.
3. Résoudre l'identité et la rencontre.
4. Contrôler source, identifiant de message et hash du contenu.
5. Transformer en commande métier.
6. Enregistrer demande ou résultats dans une transaction.
7. Produire un ACK conforme au profil après le commit.
8. Conserver une trace minimale de résultat de traitement.

Si la transaction échoue, aucun ACK de réussite métier n'est envoyé. Le profil local fixe `AA` après commit, `AE` pour un échec temporaire et `AR` pour un rejet ; la stratégie de retransmission du simulateur sera mise en œuvre et testée avec T05.

## Rejeu et corrections

| Cas | Résultat |
|---|---|
| Nouveau message valide | Traitement et commit, puis ACK positif |
| Message déjà traité, contenu identique | Même résultat logique, aucun nouveau rapport |
| Même source et même ID, contenu différent | Conflit contrôlé, données inchangées |
| Message précédemment rejeté | Même motif ou procédure de reprise explicitement autorisée ; jamais succès automatique |
| Deux réceptions concurrentes | La contrainte en base arbitre ; pas de doublon métier |
| Correction avec nouvel ID | Nouvelle version du rapport, ancien rapport conservé |

Le hash est calculé de façon déterministe sur le contenu reçu après retrait éventuel de l'enveloppe de transport, sans transformation métier qui ferait disparaître une différence. La règle exacte fait partie du profil local.

## Résultat manquant

Le manifeste synthétique annonce les analyses attendues. Si la CRP attendue n'est pas fournie, l'application produit son état `missing`, avec valeurs nulles et avertissement. Elle ne fabrique pas un résultat clinique et ne rejette pas nécessairement les observations valides du même rapport.

Une analyse non demandée, inconnue ou mal typée est rejetée par le profil local du premier jalon.

## Transport et confidentialité

L'endpoint HTTP interne est un adaptateur de test, non un remplacement universel de MLLP. Son enveloppe, type de contenu, authentification de service et ACK sont fixés dans le [profil local](hl7-profile.md). Le proxy public ne l'expose pas.

Un listener MLLP ultérieur utilise le même traitement métier. Le transport est limité au réseau de démonstration. Ni MLLP brut ni le simple usage de HL7 ne garantissent le chiffrement.

Les messages bruts synthétiques peuvent être conservés dans les fixtures. Les journaux d'exécution contiennent seulement les identifiants techniques autorisés, le statut et la corrélation, jamais le payload complet.

