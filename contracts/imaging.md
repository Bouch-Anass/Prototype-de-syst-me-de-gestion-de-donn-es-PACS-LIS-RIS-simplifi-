# Contrat radiologie et imagerie

## Trois objets distincts

- La demande radiologique exprime l'examen demandé et porte l'accession.
- L'examen représente sa réalisation et ses états.
- L'étude d'imagerie référence les objets DICOM dans Orthanc.

Un compte rendu peut être absent alors qu'une étude est présente, et inversement. L'interface ne doit pas confondre « images disponibles » et « compte rendu validé ».

## Import initial

Le simulateur de modalité importe un jeu DICOM synthétique dans Orthanc par C-STORE. La configuration des AE Titles, du port DICOM et des pairs autorisés sera livrée avec l'environnement local.

Le backend utilise l'API REST privée Orthanc pour le rapprochement et l'état. Il ne consulte pas directement son stockage sur disque ou son index interne.

## Rapprochement

Proposition v0.1 : source unique `DEMO`. Le générateur renseigne `PatientID (0010,0020)=DEMO-P001`, `IssuerOfPatientID (0010,0021)=DEMO`, `AccessionNumber (0008,0050)=DEMO-ACC001`, `StudyInstanceUID (0020,000D)=2.25.10101` et `Modality (0008,0060)=CT`. Les séries et instances possèdent leurs propres UID, distincts de l'UID d'étude. Ces valeurs proviennent du [manifeste commun](../data/fixtures/scenario.json). Les UID fixes sont réservés aux fixtures ; les nouvelles études de T07 devront générer leurs propres UID.

Ordre de contrôle : résoudre patient par domaine/identifiant ; résoudre accession ; retrouver l'examen et son épisode ; vérifier que cet épisode appartient au patient résolu ; comparer modalité ; vérifier unicité et rattachement de l'UID ; persister le lien. Un UID déjà lié au même examen est idempotent, un UID lié à un autre examen est un conflit. Le nom du patient ne participe jamais à ces étapes.

Dans cette première version, un IssuerOfPatientID absent est refusé, même si le PatientID existe. Le repli vers un domaine configuré n'est pas activé. Un ajout ultérieur devra être revu et testé. Une étude non rapprochée conserve un état technique en attente hors dossier clinique ; elle n'apparaît pas chez un patient par défaut.

| Clé | Usage | Règle |
|---|---|---|
| PatientID et domaine d'identification convenu | Identité | Doit correspondre au patient de la rencontre |
| AccessionNumber | Demande radiologique | Doit identifier la demande attendue |
| StudyInstanceUID | Identité de l'étude | Stable et unique ; pas un identifiant patient |
| ID interne Orthanc | Accès technique au PACS | Peut être conservé côté serveur, pas utilisé comme identité clinique |
| UUID d'examen | Relation métier | Lie l'étude au RIS |

Le domaine doit rester cohérent avec PID-3.4 dans le profil HL7. La politique stricte ci-dessus évite les replis implicites entre sources.

L'absence ou la contradiction d'une clé bloque le rattachement automatique. Une fonctionnalité de résolution manuelle contrôlée pourra être ajoutée ; ce n'est pas une association arbitraire par nom.

## Disponibilité

| État | Sens |
|---|---|
| `available` | Étude accessible selon la vérification définie |
| `incomplete` | L'attente du scénario n'est pas satisfaite ou la complétude reste non établie |
| `unavailable` | Accès impossible à l'instant de contrôle, même si une référence existe |

Pour les fixtures, le manifeste fixe le nombre attendu de séries et d'instances. Cette méthode de démonstration ne constitue pas une preuve générale de fin d'acquisition clinique.

Chaque état est accompagné d'un instant de contrôle ou de dernière synchronisation. Une donnée ancienne ne doit pas être affichée comme une vérification instantanée.

T08 emploie un budget Orthanc proposé de 500 ms, sans retry synchrone. Au-delà : `unavailable`, `checked_at` date de tentative, `last_synced_at` dernière réussite, avertissement français. Les compteurs historiques peuvent rester visibles mais ne prouvent pas l'accès actuel. Sans étude connue, `studies=[]` ; jamais d'UUID inventé. La panne PostgreSQL ne donne pas ce mode partiel : réponse 503.

Références de vocabulaire : [DICOM, identification du patient](https://dicom.nema.org/medical/Dicom/2015c/output/chtml/part03/sect_C.2.2.html) et [module étude](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.7.2.html). Les valeurs DEMO et la politique de rejet sont propres au projet.

## Accès au viewer

L'endpoint `viewer-link` doit retourner un accès applicatif contrôlé, sans credentials Orthanc ni accès à son administration. La stratégie de viewer est à choisir : proxy applicatif ou composant compatible avec un mécanisme de session validé.

Une URL non devinable ne suffit pas comme contrôle d'accès. La requête d'image doit vérifier l'autorisation ou un jeton temporaire strictement limité, selon la stratégie retenue.

DICOMweb et ses plugins éventuels ne sont nécessaires que si la solution choisie les exige. Les versions des plugins doivent être compatibles avec l'image Orthanc retenue.

## Tests obligatoires

Import correct, accession inconnue, patient contradictoire, Study Instance UID déjà connu, étude partielle, PACS arrêté, timeout, accès interdit et absence de secret côté navigateur.

