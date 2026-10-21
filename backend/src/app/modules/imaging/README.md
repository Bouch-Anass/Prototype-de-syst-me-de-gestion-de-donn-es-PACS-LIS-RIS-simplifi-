# Module imaging

Le service interne T07 rapproche une étude Orthanc d'un examen RIS avec le PatientID et son domaine, l'accession, le StudyInstanceUID et la modalité. Il refuse les clés manquantes ou contradictoires, un second UID pour le même examen et le rattachement d'un UID déjà connu à un autre examen. Un rejeu exact actualise la même ligne `imaging_study`.

`match_study` et `get_availability` reçoivent un client Orthanc injecté. La disponibilité vaut `available` quand le nombre de séries et d'instances correspond au manifeste synthétique, `incomplete` sinon. Si Orthanc est inaccessible ou renvoie des métadonnées contradictoires, `get_availability` retourne `unavailable` et un code d'avertissement ; il conserve le rattachement, les derniers comptes et `last_synced_at`. Chaque lecture de disponibilité et chaque rapprochement réussi écrit un événement d'audit dans la transaction métier. Une panne d'audit fait échouer l'opération.

T06 doit encore fournir le workflow de création et de validation RIS. Le seed CLI `seed-radiology-demo` crée uniquement la demande et l'examen synthétiques nécessaires à cette démonstration. T08 composera la synthèse clinique ; T10 traitera l'accès contrôlé aux images.

