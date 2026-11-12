# Chronologie du projet CryptEasy

Ce que l'équipe a **réellement** fait, et quand, pour le comparer à ce que prévoyait le cahier des charges (CDC). C'est la matière première des sections 2 à 5 du rapport (#33). La partie 4 sert d'annexe B (historique Git).

- **Sources :** historique Git de toutes les branches, pull requests et issues GitHub, [planning v1](../pm/planning-v1.md), [planning v2](../pm/planning-v2.md), [journal des décisions](../pm/decisions.md), [registre des risques](../pm/risks.md).
- **Heures :** heure de Paris.
- **Dernière mise à jour :** 12/11/2026. À compléter jusqu'au 28/11 (voir la partie 3).

---

## 1. Grandes étapes

La colonne « Prévu par le CDC » reprend le [planning v1](../pm/planning-v1.md), où la semaine S1 est celle du 14/09.

| Date | Ce qui s'est passé | Prévu par le CDC | Source |
|---|---|---|---|
| 15/09 | Cahier des charges déposé sur Arche | S1 : rédaction du sujet | planning-v1 |
| 21/09 → 04/10 | *Aucune trace dans Git (le dépôt n'existe pas encore)* | S2-S3 : conception (architecture, bibliothèques, maquette) | — |
| 05/10 | *Rien ne démarre* | S4 : début du moteur crypto et de l'interface | planning-v1 |
| 15/10 | Création du dépôt GitHub (Diogo). Outillage uv, Makefile, lint, CI et workflow une branche par membre (Sam, PR #1). Première version de l'interface sur un faux backend (Yanis, écrite en local, publiée le 05/11) | — | Git, PR #1 |
| 15/10 → 18/10 | Spécification technique (Diogo). Arrivée dans le dépôt seulement le 08/11 | S2-S3 : conception | planning-v2, PR #41 |
| 18/10 | Branche `main` protégée (seul le propriétaire merge). Dernier commit avant 17 jours sans activité | — | decisions.md, Git |
| 19/10 → 04/11 | **Aucun commit pendant 17 jours** | S6-S8 : gestion des clés, packaging, intégration | Git |
| 25/10 | *Moteur crypto non commencé* | Fin prévue du moteur crypto et de l'interface | planning-v1 |
| 05/11 | Interface complète publiée sur `s11nay-dev` (fenêtre pywebview, FR / EN, tests) | — | Git |
| 08/11 | **Re-planification** : constat d'environ 5 semaines de retard, passage à 3 sprints d'une semaine, rôles redistribués selon les compétences, périmètre réduit. Création des 3 milestones, de 39 issues et du board GitHub. CDC, spec et documents de suivi ajoutés au dépôt (PR #41) | Fin prévue de l'intégration et du packaging (S8) | planning-v2, decisions.md, PR #41 |
| 09/11 | Lancement du sprint 1 (réunion sur Discord, #4). Interface mergée dans `main` (PR #42) | S9 : début de la documentation et du rapport | #4, PR #42 |
| 10/11 | **Ajustements en cours de sprint**, décidés ensemble en cours : #9 passe de Diogo à Yani pour équilibrer la charge du sprint 1 ; chacun rédige la partie du rapport qui correspond à son travail, dans un Word partagé en ligne. Squelette du rapport (#15, PR #43) et génération des clés (#6, PR #44) mergés. Sections 6, 7 et 9 du rapport redécoupées (#46 créée, #31 et #32 modifiées, PR #47) | — | decisions.md, PR #43 → #47 |
| *14/11* | *Revue et rétrospective du sprint 1 (#17)* | — | à venir |
| *15/11* | *Fin du sprint 1 : un vrai chiffrement → déchiffrement fonctionne* | Fin prévue de la documentation et du rapport (S9) | à venir |
| *22/11* | *Fin du sprint 2 : exe Windows construit et testé, **gel du code** (#27)* | Fin prévue de la préparation de la soutenance (S10) | à venir |
| *28/11* | *Fin du sprint 3 : archive déposée sur Arche (#38)* | — | à venir |
| *30/11* | *Répétition chronométrée (#40)* | — | à venir |
| *01/12* | *Soutenance* | — | à venir |

---

## 2. Constats utiles pour le rapport

Ce sont des faits relevés dans les sources. Les sections 2 à 4 du rapport devront les **expliquer et les justifier**.

1. **Le retard se voit dans Git.** Entre le 19/10 et le 04/11, il n'y a aucun commit, alors que le CDC prévoyait sur cette période le moteur crypto, la gestion des clés et le packaging. C'est une preuve concrète des risques R1 (mauvaise répartition du temps) et R2 (écart de compétences), tous deux réalisés.
2. **Une partie du travail d'octobre a été publiée tard.** L'interface a été écrite le 15/10 mais publiée sur GitHub le 05/11. La spec technique a été écrite du 15 au 18/10 mais ajoutée au dépôt le 08/11. L'historique GitHub **sous-estime donc** le travail fait en octobre : il faut le dire dans le rapport, sinon le lecteur conclura qu'il ne s'est rien passé.
3. **Le travail s'est fait par à-coups.** L'activité se concentre sur quelques journées (15/10, 05/11, 08-10/11) au lieu d'être régulière. Le passage aux sprints hebdomadaires du 08/11 répond justement à ce problème.
4. **La planification formelle date du 08/11.** Les milestones, les 39 issues et le board ont été créés le même jour, en moins d'une heure (12:06 → 12:38). Avant, l'organisation passait uniquement par le groupe Discord.
5. **Compter les commits ne mesure pas le travail.** Exemple : le commit d'interface du 05/11 modifie 44 fichiers (+4 522 lignes), alors que d'autres ne changent qu'une ou deux lignes (par exemple `014ea9a`). Il vaut mieux s'appuyer sur le board (qui a fait quoi, temps estimé et réel).
6. **Le plan s'ajuste pendant le sprint, et c'est tracé.** Dès le 10/11, il y a eu deux réaffectations : la #9 (de Diogo à Yani, car Diogo avait 26 h prévues sur le sprint 1) et le découpage des sections du rapport. Chacune est notée dans `decisions.md` avec sa raison. C'est un bon exemple de la capacité à « s'adapter » évaluée par le prof.
7. **Premiers écarts entre estimé et réel** (board au 10/11, 6 tâches terminées) :

   | Tâche | Estimé | Réel | Écart |
   |---|---|---|---|
   | #2 Re-planification | 2 h | 3 h | +50 % |
   | #3 Dossier `docs/pm/` | 1 h | 1,5 h | +50 % |
   | #4 Réunion de lancement | 0,5 h | 1 h | ×2 |
   | #6 Génération des clés | 4 h | 3 h | −25 % |
   | #14 PR de l'interface | 0,5 h | 1 h | ×2 |
   | #15 Squelette du rapport | 2 h | 2 h | = |
   | **Total** | **10 h** | **11,5 h** | **+15 %** |

   Tendance à confirmer d'ici la fin du projet : les petites tâches d'organisation sont sous-estimées, alors que la seule grosse tâche technique a pris moins de temps que prévu.
8. **Attention aux noms dans Git.** Yanis apparaît sous 3 noms (`S11nay`, `Yanis DISCOURS`, `Yanis Discours`) et Sam sous `Enryou`. Il faut les regrouper avant tout comptage, par exemple dans *Insights → Contributors*.

---

## 3. À compléter

- [ ] **Board GitHub** : relever le temps estimé et le temps réel de chaque tâche terminée, à la fin de chaque sprint (fait pour les 6 tâches terminées au 10/11, voir le constat 7)
- [x] **Confirmé par Diogo** (12/11) : la spec a bien été rédigée du 15 au 18/10, hors du dépôt
- [x] **Confirmé par Yanis** (12/11) : l'interface a bien été écrite le 15/10, en local
- [ ] Ajouter chaque réunion de sprint (14/11, 22/11, 28/11) et ses décisions
- [ ] Mettre à jour la partie 4 juste avant l'assemblage du rapport (#34)

---

## 4. Détail Git (annexe B)

### 4.1 Pull requests

| PR | Ouverte | Mergée | Auteur | Branche | Titre |
|---|---|---|---|---|---|
| #1 | 15/10 15:34 | 15/10 15:35 | Sam (`Enryou`) | `enryou-dev` → `main` | Document per-member branch workflow and run CI on dev branches |
| #41 | 08/11 19:46 | 08/11 19:48 | Diogo (`DiogoF-Hub`) | `diogo-dev` → `main` | docs: CDC, technical spec and project management records |
| #42 | 09/11 09:40 | 09/11 15:22 | Yanis (`S11nay`) | `s11nay-dev` → `main` | Interface graphique (Flask + pywebview) sur FakeBackend |
| #43 | 10/11 15:10 | 10/11 17:01 | Yani (`c0mpr0mized`) | `c0mp-dev` → `main` | docs: report skeleton |
| #44 | 10/11 16:40 | 10/11 17:01 | Diogo (`DiogoF-Hub`) | `diogo-dev` → `main` | core: key generation, PEM import / export and fingerprints |
| #45 | 10/11 17:17 | 10/11 17:18 | Diogo (`DiogoF-Hub`) | `diogo-dev` → `main` | docs: log the shared online Word document for the report |
| #47 | 10/11 17:37 | *ouverte* | Yani (`c0mpr0mized`) | `c0mp-dev` → `main` | docs: re-split report sections |

### 4.2 Commits

« Écrit le » est la date à laquelle le commit a été créé. « Publié le » est la date à laquelle il est arrivé dans le dépôt, indiquée seulement quand elle est différente.

| Écrit le | Publié le | Hash | Auteur | Message |
|---|---|---|---|---|
| 15/10 10:37 | | `77f1d4c` | Diogo | Initial commit |
| 15/10 14:18 | | `2cdb370` | Sam | Set up project tooling and documentation |
| 15/10 14:55 | | `43e89e9` | Yani | Revise team information in README |
| 15/10 14:58 | | `014ea9a` | Yanis | Update README.md |
| 15/10 15:04 | 05/11 15:01 | `533ac1e` | Yanis | ui: squelette Flask, middleware § 6 et écrans sur FakeBackend |
| 15/10 15:04 | 05/11 15:01 | `ce29367` | Yanis | ui: page Info (fonctionnement, empreintes, format .ceasy v1, limites) |
| 15/10 15:04 | 05/11 15:01 | `11ea763` | Yanis | Lancement (`__main__.py`) selon le contrat § 3, waitress, bouton Quitter |
| 15/10 15:04 | 05/11 15:01 | `b18da7d` | Yanis | ui: retouches après revue visuelle |
| 15/10 15:19 | 05/11 15:01 | `d9da58d` | Yanis | ui: alignement sur SPEC_TECHNIQUE (brouillon) |
| 15/10 15:33 | | `6509110` | Sam | Document per-member branch workflow and run CI on dev branches |
| 15/10 15:35 | | `04af912` | Sam | *Merge de la PR #1* |
| 18/10 22:44 | | `9462b5e` | Diogo | Add resources to .gitignore |
| 05/11 15:01 | | `d0a4210` | Yanis | Échafaudage minimal pour la partie interface |
| 05/11 15:03 | | `91216c3` | Yanis | ui: conformité aux règles du dépôt (Ruff, Python 3.13) |
| 05/11 15:44 | | `06223a8` | Yanis | ui: interface complète selon SPEC_TECHNIQUE (fenêtre pywebview) |
| 08/11 19:45 | | `dc67602` | Diogo | docs: CDC, technical spec and project management records |
| 08/11 19:53 | | `c138197` | Diogo | *Merge de la PR #41* |
| 09/11 09:33 | | `a7ea47a` | Yanis | *Merge de `main` dans `s11nay-dev`* |
| 09/11 15:22 | | `f201b8d` | Diogo | *Merge de la PR #42* |
| 10/11 15:09 | | `6f4ed52` | Yani | docs: add report skeleton (#15) |
| 10/11 15:27 | | `8fa55b7` | Yani | docs: update report skeleton (#15) |
| 10/11 16:39 | | `c01ff1e` | Diogo | core: key generation, PEM import / export and fingerprints (#6) |
| 10/11 16:39 | | `8b9cdc4` | Diogo | docs: log the #9 reassignment, ignore .vscode |
| 10/11 17:00 | | `108f11d` | Diogo | docs: log how the report is written (each member writes their part) |
| 10/11 17:01 | | `5ff0117` | Diogo | *Merge de la PR #43* |
| 10/11 17:01 | | `3a827d4` | Diogo | *Merge de la PR #44* |
| 10/11 17:15 | | `8398012` | Diogo | docs: log the shared online Word document for the report |
| 10/11 17:18 | | `71cda54` | Diogo | *Merge de la PR #45* |
| 10/11 17:37 | | `0b0aeaa` | Yani | docs: re-split report sections 6, 7 and 9 (#46) |
| 12/11 09:51 | | `f9666e2` | Yani | docs: update the report of contents |

### 4.3 Suivi des tâches (GitHub)

| Date | Événement |
|---|---|
| 08/11 11:52 | Création des milestones Sprint 1, Sprint 2 et Sprint 3 |
| 08/11 12:06 → 12:38 | Création des issues #2 à #40 (39 tâches), ajoutées au board |
| 08/11 19:48 | #2 (re-planification) et #3 (dossier `docs/pm/`) terminées via la PR #41 |
| 09/11 15:22 | #14 (ouvrir la PR de l'interface) terminée via la PR #42 |
| 09/11 17:29 | #4 (réunion de lancement du sprint 1) terminée |
| 10/11 15:12 | #15 (squelette du rapport) terminée |
| 10/11 16:30 | #9 (zip d'un dossier + extraction sûre) réassignée de Diogo à Yani |
| 10/11 17:01 | #6 (génération des clés) terminée via la PR #44 |
| 10/11 17:32 | #46 créée (sections 6 et 9 du rapport, Yani) ; #32 recentrée sur l'état final de `core/` ; #31 complétée avec `keystore/` |
