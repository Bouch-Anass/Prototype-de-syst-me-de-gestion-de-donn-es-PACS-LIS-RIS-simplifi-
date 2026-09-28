# Sécurité et limites d'utilisation

Ce dépôt est un prototype sur données synthétiques. Il n'est pas destiné au soin, au diagnostic ou au stockage de dossiers réels.

## Garde-fous de développement

- PostgreSQL, Orthanc et le transport HL7 restent sur un réseau privé de démonstration.
- Toute publication de port local doit être explicitement nécessaire et liée à l'interface locale.
- Les identifiants de service Orthanc et base de données ne sont jamais envoyés au navigateur.
- Les secrets sont générés localement ou fournis par un gestionnaire adapté ; aucune valeur réelle ne figure dans Git.
- Les droits sont évalués côté serveur, y compris lorsque l'UUID ou l'URL d'une ressource est connu.
- Les traces d'audit conservent l'action, l'acteur, la ressource et le résultat, pas le contenu clinique.
- Les messages HL7 et erreurs sont traités comme des entrées non fiables.
- Un jeu DICOM public n'est pas automatiquement autorisé à être redistribué ou exempt de données identifiantes.

## Données autorisées

Les exemples inclus sont entièrement fictifs. Les fixtures DICOM et HL7 futures doivent l'être aussi ou faire l'objet d'une vérification documentée de provenance, de droit d'usage et d'absence de données identifiantes. L'option par défaut est la génération synthétique.

Les volumes, exports, logs et dumps ne sont pas suivis par Git. Une règle `.gitignore` ne retire pas un secret déjà commité et ne remplace pas une revue.

## Authentification et exposition

Le schéma de session sera défini en T02/T03. Selon le choix, les risques liés au stockage du token, aux cookies, au CSRF et à la révocation devront être traités. Aucun mécanisme n'est considéré comme livré dans ce pack.

Une ouverture réseau au-delà de la démonstration locale exige une revue dédiée. Le simple usage de DICOM, HL7, HTTPS ou Orthanc ne constitue pas une certification de sécurité.

## Incidents

Une vulnérabilité ou une fuite ne doit pas être publiée avec ses secrets ou données sensibles dans une issue publique. Utiliser un canal privé adapté au dépôt. Si un secret est exposé, le révoquer et traiter son historique ; supprimer uniquement le fichier courant ne suffit pas.

## Conformité

Le document existant « Normes et conformité » reste la base de discussion, notamment pour la loi marocaine 09-08. Ce squelette ne fournit pas d'avis juridique ni de preuve de conformité. Tout usage de données personnelles réelles demande une analyse distincte et des autorisations appropriées avant traitement.

