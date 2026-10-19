# Module audit

Lot A.

Responsabilité : Traces minimales des consultations, modifications et refus.

Tables : audit_event.

Invariants : Pas de payload clinique, de secret ou de mot de passe ; opérations cliniques refusées si l'audit requis échoue.

T03 écrit les événements de login, consultation, refus de contexte et déconnexion dans `audit_event`. Les lectures cliniques ne sont retournées qu'après commit de leur trace. Le test de panne d'audit vérifie une réponse 503 sans contenu clinique.

