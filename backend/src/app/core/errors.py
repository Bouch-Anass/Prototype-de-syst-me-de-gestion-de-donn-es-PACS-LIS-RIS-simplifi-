"""Erreurs API sans données cliniques ni détails d'infrastructure."""


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(code)


UNAUTHENTICATED = (401, "UNAUTHENTICATED", "Authentification requise.")
ACCESS_DENIED = (403, "ACCESS_DENIED", "Accès non autorisé à cette ressource.")
NOT_FOUND = (404, "NOT_FOUND", "Ressource introuvable.")
