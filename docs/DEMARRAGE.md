# Démarrage et publication sur GitHub

## Ce qui peut être utilisé immédiatement

- Les documents d'architecture et de découpage.
- Les dossiers de responsabilité.
- Les contrats et les mocks du frontend.
- Les modèles d'issues et de pull requests.
- Les contrôles locaux des documents et des exemples.

T01 fournit maintenant le [Compose PostgreSQL/Orthanc](../infra/README.md) et T02 un [aperçu frontend statique](../frontend/README.md). Aucun serveur FastAPI ni parcours clinique complet n'est encore exécutable. Les sections GitHub ci-dessous sont des consignes historiques du pack initial, pas des actions effectuées par T01/T02.

## Vérification locale

Depuis la racine du dossier extrait :

```bash
python3 scripts/check_repo.py
python3 -m unittest discover -s tests/contract -v
```

Python 3.12 ou supérieur suffit. Aucun accès réseau ni paquet Python tiers n'est requis par ces commandes.

Le workflow GitHub Actions exécute les mêmes contrôles. Il ne déploie rien. Il n'a pas été exécuté sur GitHub pendant la préparation du pack.

## Nouveau dépôt vide

Créer d'abord un dépôt GitHub vide. Remplacer `URL_DU_DEPOT` par son URL réelle avant toute commande `remote`.

```bash
git init
git branch -M main
git status
git add .
git diff --cached --stat
git diff --cached
git commit -m "docs: architecture et squelette initial"
git remote add origin URL_DU_DEPOT
git push -u origin main
```

Inspecter les fichiers préparés avant le commit. Les commandes sont des instructions à exécuter volontairement ; elles n'ont pas été exécutées pour publier ce pack.

## Dépôt existant

Ne pas remplacer ses fichiers en bloc. Créer une branche depuis la copie habituelle du dépôt, comparer les README et fusionner manuellement les changements qui se recouvrent.

```bash
git status
git switch -c chore/architecture-initiale
```

Copier ensuite les nouveaux dossiers pertinents, sans écraser un fichier existant non comparé. Les fichiers cachés `.github`, `.gitignore`, `.gitattributes` et `.env.example` font partie du pack.

Après vérification, préparer un commit et une pull request selon le fonctionnement du dépôt. Aucun `push --force`, reset destructif ou effacement d'historique n'est nécessaire.

## Organisation des issues

Les sections T01 à T12 du [backlog](BACKLOG.md) deviennent des issues séparées. Associer à chacune un lot, des dépendances, les fichiers concernés et les critères d'acceptation.

Un tableau GitHub peut utiliser quatre états : À préparer, Prêt, En cours, À vérifier. Il s'agit d'une suggestion ; aucun tableau ni ticket distant n'est créé dans ce pack.

## Configuration future

`.env.example` décrit les variables utilisées par la première tranche T03 ainsi que celles prévues pour les intégrations futures. Les secrets Docker de T01 sont créés par `scripts/init_local_env.py` dans `infra/.secrets/`, hors Git. Le [guide backend](../backend/README.md) décrit la migration et la recherche du patient synthétique.

Les variables ne sont consommées par aucun programme actuellement. Les paramètres vides ne sont pas une configuration fonctionnelle.

## Documents de conception

Les PDF existants peuvent être ajoutés dans [docs/conception](conception/README.md). Ils n'ont pas été réécrits, recopiés ni renommés par ce squelette. Cette séparation évite de mélanger les sources de conception et le nouveau plan d'implémentation.

