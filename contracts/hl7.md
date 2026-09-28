# Contrat HL7 v2 ciblé

## Périmètre

Le premier parcours importe une demande de laboratoire puis ses résultats depuis un simulateur. Les messages ciblés sont `OML^O21` et `ORU^R01`.

La version HL7 exacte, le profil de segments, les champs obligatoires, le jeu de caractères, le fuseau, les acquittements et le transport sont à fixer en T02. Aucun message brut prétendument conforme n'est fourni avant cette décision.

## Mapping sémantique à finaliser

| Information HL7 | Destination | Vérification |
|---|---|---|
| Émetteur et identifiant de contrôle du message, notamment MSH-10 | `inbound_message` | Unicité par source, présence et cohérence |
| Identifiant patient et autorité d'affectation dans PID | `patient` | Correspondance exacte domaine/identifiant |
| Référence de rencontre selon le profil retenu | `encounter` | Rencontre existante du bon patient |
| Références de demande et d'examen dans les groupes ORC/OBR du profil | `lab_order`, `lab_report` | Aucun rattachement par simple ordre d'arrivée |
| Code, type, valeur, unité et état d'observation dans OBX | `lab_observation` | Type, code local et cohérence de valeur |
| État de résultat et correction selon le profil | Version du rapport | Pas d'écrasement silencieux |

Ce tableau n'est pas une grammaire de message. La position exacte et la cardinalité de chaque segment dépendent du profil choisi, notamment pour OML. Les tests de parsing devront utiliser ce profil, pas une liste de segments supposée universelle.

## Chaîne de traitement

1. Vérifier l'origine et la taille autorisée avant parsing.
2. Parser et valider le profil ciblé.
3. Résoudre l'identité et la rencontre.
4. Contrôler source, identifiant de message et hash du contenu.
5. Transformer en commande métier.
6. Enregistrer demande ou résultats dans une transaction.
7. Produire un ACK conforme au profil après le commit.
8. Conserver une trace minimale de résultat de traitement.

Si la transaction échoue, aucun ACK de réussite métier n'est envoyé. Une erreur technique temporaire et un rejet fonctionnel doivent être distingués. Les codes d'ACK exacts et la stratégie de retransmission seront fixés avec le mode d'acquittement retenu.

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

Une analyse non demandée, inconnue ou mal typée relève d'une règle distincte de validation, à documenter avant acceptation.

## Transport et confidentialité

L'endpoint HTTP interne est un adaptateur de test, non un remplacement universel de MLLP. S'il est retenu, l'enveloppe, le type de contenu, le compte de service et le format de retour ACK seront définis en T02. Le proxy public ne l'expose pas.

Un listener MLLP ultérieur utilise le même traitement métier. Le transport est limité au réseau de démonstration. Ni MLLP brut ni le simple usage de HL7 ne garantissent le chiffrement.

Les messages bruts synthétiques peuvent être conservés dans les fixtures. Les journaux d'exécution contiennent seulement les identifiants techniques autorisés, le statut et la corrélation, jamais le payload complet.

