# Contrat HL7 v2 ciblé

## Périmètre

Le premier parcours importe une demande de laboratoire puis ses résultats depuis un simulateur. Les messages ciblés sont `OML^O21` et `ORU^R01`.

Le profil proposé **DEMO-LAB-0.1** utilise HL7 **2.5.1**, encodage ER7 UTF-8, séparateur de champs `|`, séparateurs de composants `^~\&` et fin de segment CR. Une fin CR est exigée après le dernier segment. Dates HL7 `YYYYMMDDHHMMSS+ZZZZ`, avec décalage obligatoire ; les dates JSON correspondantes sont normalisées en UTC. Ce sous-ensemble local demande la revue du Membre 3 avant T05. Il ne revendique ni profil IHE complet ni conformité clinique.

## Structure locale acceptée

Les cardinalités ci-dessous restreignent les structures HL7 ; elles ne les remplacent pas par une liste arbitraire. Un message contient un patient, un épisode et une seule demande de bilan `BILAN_DEMO`. Les segments non admis et répétitions supplémentaires sont rejetés explicitement. Les groupes facultatifs non utilisés (assurance, notes, visites supplémentaires) sont absents.

| Message | Structure ciblée et ordre des segments | Réponse applicative |
|---|---|---|
| `OML^O21^OML_O21` | MSH (1), PATIENT : PID (1), PATIENT_VISIT : PV1 (1), ORDER : ORC (1), OBSERVATION_REQUEST : OBR (1) | `ORL^O22^ORL_O22` avec MSH, MSA et ERR en erreur ; groupes d'ordre non nécessaires omis |
| `ORU^R01^ORU_R01` | MSH (1), PATIENT_RESULT : PATIENT/PID (1), VISIT/PV1 (1), ORDER_OBSERVATION : ORC (1), OBR (1), OBSERVATION/OBX (1 à 2) | `ACK^R01^ACK` avec MSH, MSA et ERR en erreur |

L'OML accepte uniquement une nouvelle demande (`ORC-1=NW`). Son acceptation porte sur l'importation de la demande simulée. Le simulateur joue le rôle d'une source d'événements pour le dossier ; cette direction n'est pas une description générale d'un LIS réel. Les prélèvements et conteneurs sont hors de ce sous-ensemble initial.

## Champs obligatoires et domaine

| Champ | Règle locale v0.1 |
|---|---|
| MSH-3 / MSH-4 | `DEMO-LIS` / `DEMO` ; la source autorisée est associée au compte de service |
| MSH-5 / MSH-6 | `DOSSIER` / `DEMO` |
| MSH-7, MSH-9, MSH-10 | Date avec décalage ; type complet ci-dessus ; identifiant non vide, maximal 120 caractères |
| MSH-11 / MSH-12 | `T` (traitement de test) / `2.5.1` |
| MSH-15 / MSH-16 / MSH-18 | Vides pour le mode original d'acquittement / `UNICODE UTF-8` pour le jeu de caractères |
| PID-3 | Un CX : `DEMO-P001^^^DEMO^MR` ; valeur et autorité correspondent au manifeste |
| PV1-2 / PV1-19 | `O` (consultation externe) / un CX `DEMO-E001^^^DEMO^VN` ; épisode existant de ce patient |
| ORC-1 | `NW` dans l'OML ; `RE` dans l'ORU |
| ORC-2 et OBR-2 | EI `DEMO-LAB001^DEMO` ; valeurs identiques |
| ORC-3 et OBR-3 | EI `DEMO-LIS001^DEMO-LIS` ; valeurs identiques |
| OBR-4 | `BILAN_DEMO^Bilan de demonstration^DEMO` : catalogue local, CRP et glucose attendus |
| OBR-22 / OBR-25 dans ORU | Date de rapport avec décalage / `F` pour initial, `C` pour correction |
| OBX-1 / OBX-2 / OBX-3 | Numéro séquentiel / `NM` / `CRP^CRP^DEMO` ou `GLU^Glucose^DEMO` ; un seul résultat par code |
| OBX-5 / OBX-6 | Nombre décimal fini avec point / `mg/L` pour CRP ou `mmol/L` pour glucose |
| OBX-11 | `F` dans le rapport initial, `C` dans une correction ; concordance avec OBR-25 |

Les autres champs facultatifs restent vides dans les fixtures initiales. Types textuels, répétitions de valeur, unités différentes, valeurs nullifiées HL7 (`""`), segments personnalisés et suppressions sont hors profil : rejet contrôlé, sans conversion implicite. Le sous-ensemble JSON général peut représenter du texte ; ce premier profil HL7 ne l'émet pas.

## Absence, correction et autorité de la demande

Une demande `BILAN_DEMO` enregistre les deux analyses attendues à partir du catalogue du manifeste. Une CRP manquante se représente **par l'absence de l'OBX CRP** ; l'OBX glucose reste présent. Le mapping construit alors CRP `missing`, valeurs nulles, sans fabriquer une mesure. Un OBX présent avec valeur numérique vide ou invalide provoque un rejet de message ; ce n'est pas le scénario d'absence convenu. Une demande inconnue, un code supplémentaire ou deux OBX pour le même code provoquent également un rejet.

Chaque ORU est une photographie complète du rapport courant pour la demande ; une correction (`C`) porte un nouvel MSH-10, les deux analyses attendues ou leurs absences, et une date OBR-22 strictement postérieure au rapport courant. Le rapport initial exige `F` sans version antérieure ; une correction exige une version antérieure. Version suivante allouée sous verrou de la demande, historique conservé. Message hors ordre temporel : rejet, jamais remplacement silencieux. Une retransmission identique est reconnue avant la règle de version/date.

## Acquittement et reprise

Mode original : une réponse applicative après traitement ; pas de double acquittement d'acceptation et d'application. MSA-2 recopie le MSH-10 reçu ; MSH-10 de la réponse est distinct. `AA` signifie traitement accepté et durable, `AE` erreur de traitement, `AR` rejet de profil/source/version. Pour OML, la réponse est ORL_O22 et non un ACK générique. ERR transporte un code et une position de champ contrôlés, sans contenu clinique ni exception complète.

Proposition locale : identité/demande inconnue, conflit d'identifiant, valeur invalide et échec de transaction donnent `AE` ; type/version/structure refusés donnent `AR`. Les erreurs de syntaxe dont MSH-10 est illisible ne permettent pas de construire une réponse corrélée. Les messages rejetés laissent une trace minimale ; les erreurs permanentes sont corrigées puis envoyées avec un nouvel identifiant. En cas de délai dépassé ou panne temporaire, le simulateur peut retransmettre **les mêmes octets et le même MSH-10**, au maximum deux fois après 1 s puis 2 s. Après trois essais, intervention explicite.

Un échec technique ne consomme pas définitivement l'identifiant. L'unicité de source/message et l'écriture métier sont coordonnées par transaction et verrou ; une tentative concurrente attend au maximum le budget, puis signale une erreur temporaire. Un message traité conserve son statut canonique ; le rejeu retourne la réponse applicative persistée sans nouvelle version. Clé de source = couple MSH-3/MSH-4 autorisé ; empreinte SHA-256 des octets ER7 exacts, CR final inclus, après retrait de l'enveloppe MLLP si utilisée. Aucun changement de casse, espaces ou fins de ligne n'est appliqué avant comparaison.

## Transport HTTP interne proposé

`POST /internal/hl7/messages`, corps brut `application/hl7-v2; charset=utf-8`, au maximum 64 Kio. Authentification selon [le contrat d'accès](acces.md). Budget serveur 2 s pour l'objectif nominal ; délai client 5 s. HTTP 200 signifie qu'une réponse HL7 est disponible, même si MSA-1 vaut AE/AR : le client doit lire l'acquittement. HTTP 400 si en-tête incorrélable, 401 si compte invalide, 413 si trop volumineux, 415 si type non accepté, 503 si traitement temporairement impossible. Les erreurs sans réponse HL7 utilisent l'enveloppe JSON du contrat API ; aucun faux ACK positif.

MLLP sera un adaptateur ultérieur, avec VT + ER7 + FS + CR et la même sémantique métier. Le proxy public ne route jamais cette interface interne. Aucun listener n'est livré par T02.

Références : [HL7 2.5.1, contrôle et acquittements](https://www.hl7.eu/HL7v2x/v251/std251/ch02.html), [OML O21](https://www.hl7.eu/HL7v2x/v251/hl7v251eventO21.htm), [ORL O22](https://www.hl7.eu/HL7v2x/v251/hl7v251eventO22.htm), [résultats ORU](https://www.hl7.eu/HL7v2x/v251/std251/ch07.html). Les restrictions, délais et règles DEMO ci-dessus sont des choix du projet, à distinguer des exigences générales de la norme.

## Mapping sémantique

| Information HL7 | Destination | Vérification |
|---|---|---|
| Émetteur et identifiant de contrôle du message, notamment MSH-10 | `inbound_message` | Unicité par source, présence et cohérence |
| Identifiant patient et autorité d'affectation dans PID | `patient` | Correspondance exacte domaine/identifiant |
| Référence de rencontre selon le profil retenu | `encounter` | Rencontre existante du bon patient |
| Références de demande et d'examen dans les groupes ORC/OBR du profil | `lab_order`, `lab_report` | Aucun rattachement par simple ordre d'arrivée |
| Code, type, valeur, unité et état d'observation dans OBX | `lab_observation` | Type, code local et cohérence de valeur |
| État de résultat et correction selon le profil | Version du rapport | Pas d'écrasement silencieux |

Les champs et cardinalités du profil précédent priment sur ce résumé. Le Membre 3 devra vérifier les fixtures ER7 avec une bibliothèque compatible 2.5.1 avant l'intégration T05.

## Chaîne de traitement

1. Vérifier l'origine et la taille autorisée avant parsing.
2. Parser et valider le profil ciblé.
3. Résoudre l'identité et la rencontre.
4. Contrôler source, identifiant de message et hash du contenu.
5. Transformer en commande métier.
6. Enregistrer demande ou résultats dans une transaction.
7. Produire un ACK conforme au profil après le commit.
8. Conserver une trace minimale de résultat de traitement.

Si la transaction échoue, aucun acquittement de réussite métier n'est envoyé. Distinguer l'erreur technique temporaire du rejet fonctionnel selon les règles de reprise ci-dessus.

## Rejeu et corrections

| Cas | Résultat |
|---|---|
| Nouveau message valide | Traitement et commit, puis ACK positif |
| Message déjà traité, contenu identique | Même résultat logique, aucun nouveau rapport |
| Même source et même ID, contenu différent | Conflit contrôlé, données inchangées |
| Message précédemment rejeté | Même motif ou procédure de reprise explicitement autorisée ; jamais succès automatique |
| Deux réceptions concurrentes | La contrainte en base arbitre ; pas de doublon métier |
| Correction avec nouvel ID | Nouvelle version du rapport, ancien rapport conservé |

L'empreinte et les fins de ligne suivent la règle exacte du profil local ci-dessus.

## Résultat manquant

Le manifeste synthétique annonce les analyses attendues. Si la CRP attendue n'est pas fournie, l'application produit son état `missing`, avec valeurs nulles et avertissement. Elle ne fabrique pas un résultat clinique et ne rejette pas nécessairement les observations valides du même rapport.

Une analyse non demandée, inconnue ou mal typée relève d'une règle distincte de validation, à documenter avant acceptation.

## Transport et confidentialité

L'endpoint HTTP interne est un adaptateur de test proposé par T02. Son acceptation par les membres concernés reste nécessaire avant T05. Le proxy public ne l'expose pas.

Un listener MLLP ultérieur utilise le même traitement métier. Le transport est limité au réseau de démonstration. Ni MLLP brut ni le simple usage de HL7 ne garantissent le chiffrement.

Les messages bruts synthétiques peuvent être conservés dans les fixtures. Les journaux d'exécution contiennent seulement les identifiants techniques autorisés, le statut et la corrélation, jamais le payload complet.

