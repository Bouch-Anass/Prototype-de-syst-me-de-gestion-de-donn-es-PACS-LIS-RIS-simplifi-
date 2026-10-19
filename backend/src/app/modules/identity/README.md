# Module identity

Lot A.

Responsabilité : Résolution du patient par domaine et identifiant ; gestion des rencontres.

Tables : patient, encounter.

Invariants : Aucun rapprochement par nom ; une rencontre appartient au bon patient.

T03 fournit la résolution exacte domaine/identifiant, la recherche et la liste des rencontres accordées à l'utilisateur. Les tables patient et encounter sont créées par `0001_t03`. Les autres opérations d'identité restent à définir avant exposition.

