# Adaptateur HL7

Lot B. Implémenter le [contrat HL7](../../../../../contracts/hl7.md).

Séparer transport, parser, validation du profil et mapping. La vérification d'idempotence et les écritures métier ont une frontière transactionnelle explicite.

Première preuve : un message synthétique correct, son ACK après commit et son rejeu sans duplication.

