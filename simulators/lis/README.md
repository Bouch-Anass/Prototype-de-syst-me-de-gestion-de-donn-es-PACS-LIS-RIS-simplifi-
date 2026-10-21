# Simulateur LIS

Lot B. Les quatre messages du profil HL7 sont générés depuis le manifeste par `scripts/generate_hl7_fixtures.py`. `send_hl7.py` envoie uniquement ces fixtures au service local sur `127.0.0.1`.

Depuis la racine du dépôt, après `python scripts/init_local_env.py` et le démarrage du backend :

```powershell
$env:HL7_SERVICE_SECRET = (Get-Content -Raw infra/.secrets/hl7_service_secret.txt).Trim()
python simulators/lis/send_hl7.py order.oml.hl7
python simulators/lis/send_hl7.py result.nominal.oru.hl7
python simulators/lis/send_hl7.py result.correction.oru.hl7
```

Renvoyer une fixture à l'identique teste le rejeu. `result.missing-crp.oru.hl7` est une variante isolée du nominal : utiliser une base de test distincte pour ce scénario. Les scénarios conflictuels et patient inconnu sont couverts par les tests HTTP ; le simulateur CLI ne fabrique pas de données hors manifeste.

