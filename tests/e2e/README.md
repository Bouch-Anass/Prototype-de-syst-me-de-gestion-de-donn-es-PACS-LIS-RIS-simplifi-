# Parcours de bout en bout à implémenter

## Parcours nominal

1. Initialiser le scénario synthétique.
2. Envoyer demande et résultat depuis le simulateur LIS.
3. Importer l'étude DICOM synthétique dans Orthanc.
4. Finaliser le compte rendu avec un rôle autorisé.
5. Ouvrir une session médecin et rechercher le patient.
6. Sélectionner la rencontre et vérifier biologie, radiologie et imagerie.
7. Vérifier les traces d'accès sans contenu clinique.

## Parcours dégradés

- CRP absente : mention visible, sans zéro artificiel et sans suppression du glucose.
- Orthanc arrêté : données métier lisibles et imagerie indiquée indisponible.
- Session expirée : aucune nouvelle donnée clinique affichée après un refus.
- Identifiant de dossier hors contexte : accès bloqué.
- Rejeu HL7 : affichage stable, sans duplication de résultats.

Les captures d'écran complètent les assertions API et base. Elles ne prouvent pas seules les contrôles d'accès ou l'idempotence.

Aucun de ces parcours n'est exécuté par le workflow documentaire initial.

