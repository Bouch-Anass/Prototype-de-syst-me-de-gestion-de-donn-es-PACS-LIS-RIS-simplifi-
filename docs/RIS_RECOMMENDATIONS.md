# Contenu recommandé pour le RIS

Le RIS organise le parcours d'un examen radiologique. Il garde la demande, la réalisation et le compte rendu distincts de l'étude DICOM stockée dans le PACS. Le profil [IHE Scheduled Workflow](https://profiles.ihe.net/RAD/) relie précisément les étapes de demande, planification, acquisition et lecture ; son profil Reporting Workflow ajoute le suivi du compte rendu.

## Déjà présent dans ce prototype

| Étape | Informations affichées ou enregistrées |
| --- | --- |
| Demande | Patient et rencontre autorisés, numéro d'accession, procédure demandée, modalité, priorité routine/urgente, état de la demande |
| Réalisation | État de l'examen et date de réalisation |
| Compte rendu | Texte du brouillon/final, état de validation, date de validation |
| Liaison PACS | Accession et modalité utilisées pour rapprocher l'étude DICOM, puis état de disponibilité de l'imagerie dans la vue unifiée |

Seul un radiologue autorisé marque l'examen réalisé et valide son compte rendu. La version actuelle crée puis finalise un examen depuis le formulaire de démonstration ; elle ne gère pas encore une véritable liste de rendez-vous.

## À ajouter pour un RIS plus réaliste

1. **Demande clinique :** motif de l'examen, question diagnostique, demandeur, service et date de demande. Ces champs donnent au radiologue le contexte nécessaire.
2. **Planification :** date/heure prévues, salle ou appareil, statut `demandé → planifié → en cours → réalisé → rapporté`, et motif d'annulation. Une liste de travail filtrable par statut et priorité rendrait ces données utiles.
3. **Acquisition :** protocole, région anatomique, produit de contraste si pertinent, technicien et heures de début/fin. Les informations sensibles ou propres à une modalité doivent rester conditionnelles.
4. **Compte rendu structuré :** indication, technique, constatations et conclusion, avec auteur, date, validation et amendements conservant l'historique. La structure peut aider la lecture sans imposer un diagnostic automatisé.
5. **Contrôle de cohérence :** même patient, rencontre et accession entre RIS et PACS ; images disponibles et compte rendu validé restent deux états indépendants.

Ces ajouts nécessiteraient un schéma de données, des droits et des tests supplémentaires. Le prototype reste sur données synthétiques et son aperçu PNG n'est pas un outil de diagnostic.
