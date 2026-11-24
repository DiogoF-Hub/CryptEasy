# Rapport : une section par fichier

Chacun écrit sa partie du rapport en Markdown, dans le fichier qui lui est attribué, et l'envoie par une PR comme pour le code. Yani copie ensuite chaque partie dans le Word (`../CryptEasy_Rapport.docx`, #34), pour que la mise en forme soit la même partout.

Pourquoi : quand on modifiait tous le même Word, la mise en forme cassait, et git ne sait pas fusionner deux `.docx`. Ici, chaque fichier appartient à une seule personne, donc pas de conflit, et on peut relire les textes des autres sur GitHub (décision du 24/11 dans `docs/pm/decisions.md`).

## Qui écrit quoi

| Fichier | Section | Rédacteur | Pages | Issue |
|---|---|---|---|---|
| `01-introduction.md` | 1. Introduction | Yani | 1 | #34 |
| `02-organisation.md` | 2. Organisation réelle et prévue | Yani | 3 | #33 |
| `03-durees.md` | 3. Durées estimées et réelles | Yani | 1,5 | #33 |
| `04-difficultes.md` | 4. Difficultés rencontrées | Yani | 1,5 | #33 |
| `05-changements.md` | 5. Changements d'objectifs | Yani | 1 | #33 |
| `06-choix-cdc.md` | 6. Choix pour préciser le CDC | Yani | 2 | #46 |
| `07-1-core.md` | 7.1 Moteur cryptographique | Diogo | 0,5 | #32 |
| `07-2-keystore.md` | 7.2 Gestion des clés et contacts | Sam | 0,5 | #31 |
| `07-3-interface.md` | 7.3 Interface graphique | Yanis | 1 | #29 |
| `07-4-exe-ci.md` | 7.4 Exécutable et intégration continue | Sam | 1 | #31 |
| `08-1-tests-automatiques.md` | 8.1 Tests automatiques | Sam | 1 | #31 |
| `08-2-tests-manuels.md` | 8.2 Tests manuels | Yani | 1 | #23 #24 |
| `09-ameliorations.md` | 9. Pistes d'amélioration | Yani | 1 | #46 |
| `10-conclusion.md` | 10. Conclusion | Yani | 0,5 | #34 |

Total : 16,5 pages hors annexes (le rapport doit faire entre 10 et 20 pages).

**Date limite : jeudi 26/11 au soir**, pour que Yani assemble le Word le vendredi 27 et que tout le monde relise avant le dépôt du samedi 28.

## Comment faire

1. Sur ta branche (`git switch <ta-branche>`, puis `git fetch origin && git merge --no-edit origin/main`), ouvre ton fichier.
2. Lis le bloc de consignes en haut (les lignes qui commencent par `>`), écris ta partie en dessous, puis supprime le bloc.
3. Commit, push et PR avec `Part of #<ton issue>` dans la description. Un autre membre relit.

Ne modifie que ton fichier. Si tu as une remarque sur la partie de quelqu'un d'autre, laisse un commentaire sur sa PR.

## Markdown : le minimum

```markdown
## Un sous-titre

Un paragraphe. Une ligne vide entre deux paragraphes.

**en gras**, *en italique*, `du code`

- une liste
- à puces

| Tâche | Estimé (h) | Réel (h) |
|---|---|---|
| #8 Chiffrement hybride | 8 | 6 |

![Légende de la figure](../img/mon-image.png)
```

Les images vont dans `docs/report/img/`.
