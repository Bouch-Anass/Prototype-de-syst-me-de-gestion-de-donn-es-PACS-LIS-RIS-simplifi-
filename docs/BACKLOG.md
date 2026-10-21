# Backlog initial

Les identifiants T01 à T12 sont des repères locaux, pas des numéros d'issues GitHub. Chaque section peut devenir une issue à partir du modèle fourni.

État au 21 octobre 2026 : T01/T02 fournissent Compose, contrats et fixtures ; T03–T07 fournissent identité, laboratoire, HL7, RIS et rapprochement d'imagerie ; T08–T10 ajoutent synthèse, mode API de l'interface et aperçu PNG contrôlé ; T11 possède un parcours intégré automatisé sur SQLite et PostgreSQL 18 local avec faux Orthanc ; T12 possède une procédure et un script de vérification locale. Les courses HL7/RIS/imagerie et la persistance ont été vérifiées sur un cluster PostgreSQL 18 temporaire. L'image PostgreSQL 17 du Compose, Orthanc Docker et le parcours navigateur réel doivent encore être validés.

## T01 : environnement local reproductible

Lot E. Dépendance : choix D15.

Livrer les versions verrouillées, un Compose local PostgreSQL/Orthanc, les volumes et healthchecks, puis les services applicatifs lorsqu'ils existent. Publier seulement les ports nécessaires sur l'interface locale. Documenter l'initialisation des secrets hors Git.

Acceptation : démarrage depuis un clone vierge selon une procédure exacte, données persistantes après redémarrage, aucune exposition publique ni mot de passe commité. La suppression de volumes exige une commande explicitement signalée comme destructive ; aucune purge automatique.

## T02 : contrats et jeu synthétique commun

Lot A avec B, C et D. Aucune dépendance technique.

Valider les exemples JSON et les identifiants, le profil HL7 précis, les clés de rapprochement DICOM, le choix d'authentification et les interfaces de services. Résoudre D08, D11, D12 et D13 à temps pour les lots concernés.

Acceptation : les lots interprètent les mêmes champs et états ; le manifeste est la référence unique ; aucun choix bloquant n'est masqué par une valeur arbitraire.

## T03 : socle backend, identité, droits et audit

Lot A. Dépendances : T02 ; base T01 pour les essais persistants.

Créer FastAPI, configuration validée, session de base, migrations communes, patient/rencontre synthétiques, authentification, droits et audit minimal.

Acceptation : recherche d'identifiant exact, refus d'accès hors contexte, aucune donnée sensible dans les logs, readiness cohérente, refus des opérations cliniques si l'audit requis est indisponible.

## T04 : domaine laboratoire et versions

Lot B. Dépendance : T02 ; intégration avec T03.

Implémenter commandes, rapports, observations, règles de valeurs manquantes et corrections. Les tests unitaires peuvent débuter avant la disponibilité de l'API.

Acceptation : une observation disponible porte une valeur ; la CRP manquante reste nulle ; une correction crée une nouvelle version ; aucune écriture dans les tables d'identité hors service prévu.

État : service interne et projection implémentés ; cinq tests métier et un test de migration passent sur SQLite. Les essais concurrents et PostgreSQL restent à valider.

## T05 : adaptateur et simulateur HL7

Lot B. Dépendances : T04 et profil T02.

Construire les messages synthétiques du profil accepté, leur réception, parsing, validation, corrélation, transactions et ACK.

Acceptation : demande et résultat intégrés, rejeu exact sans doublon, conflit même ID/autre contenu, rejeux concurrents maîtrisés, rejet patient inconnu, ACK positif seulement après commit.

État : transport HTTP, parseur strict, émetteur de fixtures et tests HTTP implémentés sur SQLite. Des rejeux simultanés ont produit un seul traitement métier sur PostgreSQL 18 local. Le parcours avec PostgreSQL 17 Docker reste à valider.

## T06 : workflow RIS et compte rendu

Lot C. Dépendance : T02 ; intégration avec T03.

Implémenter demandes, examens et compte rendu courant. Définir et tester les transitions permises, notamment la validation par un radiologue.

Acceptation : rattachement à la rencontre, accession unique dans le périmètre retenu, date de réalisation et validation cohérentes, transition interdite refusée.

État : service et routes HTTP implémentés avec accès explicite par rencontre, CSRF, accession unique dans la base, transitions contrôlées, compte rendu final immuable et audit transactionnel. Tests métier et HTTP réussis sur SQLite ; accession, réalisation et validation concurrentes vérifiées sur PostgreSQL 18 local. PostgreSQL 17 Docker reste à vérifier.

## T07 : Orthanc et rapprochement des études

Lot C. Dépendances : T01, T02 et T06.

Générer/importer une étude synthétique, lire les métadonnées Orthanc et relier l'étude à l'examen. Fixer les délais d'appel et l'actualisation de disponibilité.

Acceptation : étude correcte retrouvée, mauvais patient et accession inconnue refusés, doublon d'étude maîtrisé, arrêt Orthanc signalé sans perte de données métier.

État : première tranche T07 implémentée. Le seed local prépare la demande et l'examen DEMO-001 ; la commande `complete-radiology-demo` utilise ensuite le workflow T06. Le rapprochement vérifie les clés, maîtrise le rejeu et les conflits, audite les changements et actualise les comptes datés. Une panne Orthanc conserve l'association et la dernière synchronisation. Les tests SQLite avec faux Orthanc et un C-STORE en boucle locale passent ; un rattachement concurrent a été vérifié sur PostgreSQL 18 local. L'import dans l'image Orthanc Docker reste à vérifier ; l'aperçu contrôlé relève de T10.

## T08 : endpoint de synthèse

Lot A. Dépendances : T03 ; services de T04, T06 et T07 ou doubles de test conformes.

Composer le dossier avec droits, audit, warnings et erreurs. Documenter les données datées de l'imagerie.

Acceptation : réponses compatibles avec les trois mocks ; HTTP 200 dégradé si seul Orthanc tombe ; HTTP 503 si la base métier ne répond plus ; mesure du p95 sans pixels.

État : endpoint et composition inter-domaines implémentés ; nominal, CRP absente, PACS indisponible, droits et échec d'audit testés sur SQLite. Le p95 de 30 lectures était 0,058 s sur PostgreSQL 18 local avec faux Orthanc ; la mesure sur le stack Docker réel reste à faire.

## T09 : interface sur mocks puis API

Lot D. Dépendance : T02 ; T08 pour l'intégration réelle.

Créer recherche patient, sélection de rencontre et dossier, états de chargement/refus/erreur, onglets ou sections biologiques et radiologiques.

Acceptation : les trois fixtures sont affichables, la CRP manquante ne vaut jamais zéro, aucune requête directe à la base ou à l'administration Orthanc, aucun secret de service côté client.

État : les mocks restent disponibles et un mode API locale ajoute connexion, recherche exacte, choix de rencontre, synthèse, erreurs et déconnexion. Syntaxe JavaScript et assets servis par FastAPI vérifiés ; parcours navigateur réel à vérifier.

## T10 : accès d'imagerie contrôlé

Lots C et D avec A. Dépendances : T07, T09 et décision D14.

Choisir le viewer de démonstration, implémenter la route d'accès et les vérifications de droits. Ajouter DICOMweb seulement si requis.

Acceptation : accès autorisé fonctionnel, accès interdit bloqué même avec URL connue, aucune credential Orthanc exposée, erreur lisible en cas d'indisponibilité. Aucun usage diagnostique revendiqué.

État : D14 fixe un aperçu PNG non diagnostique via backend. Contrôles de session, rôle et rencontre, refus et panne PACS testés avec faux Orthanc. Import et affichage sur Orthanc réel à vérifier.

## T11 : intégration nominale et cas dégradés

Lot E avec A, B, C, D. Dépendances : T05 à T10 selon scénario.

Automatiser les parcours du [plan d'intégration](../tests/integration/README.md) et du [plan de bout en bout](../tests/e2e/README.md).

Acceptation : un scénario reproductible prouve la chaîne complète ; les rejouabilités et pannes sont vérifiées par assertions en base et API, pas seulement par captures d'écran.

État : le test API intégré HL7 → laboratoire → RIS → imagerie → synthèse, ainsi que les variantes CRP absente et PACS en panne, passent sur SQLite avec faux Orthanc. Le nominal et les courses passent aussi sur PostgreSQL 18 local avec faux Orthanc. Le parcours réel Docker, le navigateur et cinq répétitions complètes restent à exécuter.

## T12 : documentation et démonstration reproductible

Lot E avec revue des domaines. Dépendance : T11 pour la clôture.

Mettre à jour les commandes exactes, décisions, contrats, versions et limites. Ajouter les six PDF existants sans les modifier si leur publication est souhaitée.

Acceptation : exécution depuis un clone vierge, preuves de tests, liste transparente des éléments non implémentés, absence de données réelles et secrets.

État : [procédure locale](DEMO.md) et script `scripts/smoke_live.py` ajoutés. Leur exécution sur un clone vierge avec Docker, les mesures et le bilan final restent à faire.

## Définition commune de terminé

Une fonctionnalité est documentée, testée, compatible avec le contrat, revue sur les frontières concernées et démontrable. Une issue fermée ne signifie pas « le dossier existe », mais « le comportement attendu a une preuve ».

L'ordre T01/T02, puis lots en parallèle, puis intégration, exprime les dépendances. Il n'impose ni durée ni taille d'effectif.
