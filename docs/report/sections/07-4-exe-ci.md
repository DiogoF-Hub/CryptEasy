# 7.4 Exécutable et intégration continue

Le CDC demande un exécutable autonome, utilisable sans installer Python ni aucune dépendance ; nous avons choisi un seul fichier (spécification, section 2.1). La version **1.0.0rc1** a été publiée le 22/11 sur GitHub : un `.exe` Windows (17,8 Mo), une archive `.tar.gz` de 21 Mo contenant le binaire Linux, et un fichier `SHA256SUMS` pour vérifier les téléchargements. Les tests manuels ont été faits sur ces fichiers (section 8.2).

## Construction de l'exécutable

- **PyInstaller, en un seul fichier et sans console.** La recette est dans `packaging/crypteasy.spec`. Elle ajoute nos pages, le CSS et les traductions, et laisse de côté les bibliothèques graphiques que pywebview n'utilise pas (Qt, Tk).
- **Windows** : la fenêtre utilise Edge WebView2, déjà installé sur Windows 10 et 11.
- **Linux** : la fenêtre utilise GTK et WebKitGTK. Seule la partie Python de GTK (PyGObject) est dans le binaire ; GTK et WebKitGTK viennent du système, comme le prévoit la spécification (section 2.2). Il faut donc WebKitGTK sur le système (testé avec WebKit2GTK 4.1) et, comme le binaire est construit sur Ubuntu 22.04, une glibc 2.35 ou plus récente.
- **Chaque exécutable est construit sur son propre système.** PyInstaller ne sait pas produire un `.exe` depuis Linux : la CI construit le `.exe` sur une machine Windows et le binaire Linux sur Ubuntu 22.04.
- **Un test de fumée** (`make smoke`) lance l'exécutable sans fenêtre, vérifie qu'il répond sur 127.0.0.1, qu'une requête sans le jeton de lancement est refusée, et que les pages et le CSS sont bien dans le fichier.

## La chaîne d'intégration continue (GitHub Actions)

| Étape | Quand | Ce qu'elle fait |
|---|---|---|
| Lint | chaque PR et chaque push sur `main` ou une branche `-dev` | Ruff : style et règles de sécurité |
| Tests | chaque PR et chaque push sur `main` ou une branche `-dev` | les 636 tests rapides, sous Linux et sous Windows (section 8.1) |
| Vérification de build | chaque PR et chaque push sur une branche `-dev` | construit les deux exécutables, lance le test de fumée et garde les fichiers 7 jours pour les tests manuels |
| Release | quand le numéro de version change sur `main` | construit les deux exécutables, crée l'étiquette `v<version>` et publie la release avec `SHA256SUMS` |

Une release se fait donc en changeant le numéro de version dans une PR (`uv version --bump major --bump rc` pour 1.0.0rc1, dans la PR #63) : quand Diogo la fusionne, la CI fait le reste. Seule l'étape de release peut écrire dans le dépôt, et les actions GitHub utilisées sont fixées à une version précise, pour qu'une action modifiée par un tiers ne puisse pas s'exécuter chez nous.

## Difficultés

- **Le vrai moteur a été branché tard.** Jusqu'au 19/11 (#21), l'exécutable ne démarrait qu'avec le faux moteur. La vérification de build a tourné en mode démonstration en attendant, pour avancer sur le packaging sans attendre ce branchement.
- **La fenêtre Linux.** La première version embarquait toute la partie graphique du système : 119 Mo, et WebKitGTK ne pouvait pas fonctionner ainsi, car il lance des programmes auxiliaires dont le chemin est fixé à sa compilation. En gardant seulement la partie Python, le binaire passe à 21 Mo et utilise le WebKitGTK du système. Il a fallu aussi une version plus ancienne de PyGObject (3.50), la plus récente demandant une GLib plus récente que celle d'Ubuntu 22.04. Le binaire construit par la CI a d'abord été testé sous Arch Linux, puis par Yani sous Debian 13, Ubuntu 22.04 et 26.04.
- **Des détails qui bloquent.** Un `.exe` sans console n'a normalement pas de sortie standard d'après la documentation de PyInstaller, alors que le test de fumée y lit l'adresse de l'application : un essai sur la CI Windows a montré que cela fonctionne. Le modèle de `.gitignore` ignorait aussi les fichiers `.spec`, donc la recette de build n'aurait pas été envoyée sur GitHub sans une exception.

## Temps passé

| Tâche | Estimé (h) | Réel (h) |
|---|---|---|
| #18 Exécutable Windows | 6 | 3 |
| #19 CI : build et release 1.0.0rc1 | 3 | 1 |
| #20 Binaire Linux (optionnel) | 2 | 1 |
| **Total** | **11** | **5** |

Le temps réel est inférieur à la moitié de l'estimation. Les outils (uv, Makefile, lint, CI) étaient en place depuis le 15/10, et PyInstaller savait déjà empaqueter pywebview sous Windows. Le travail a surtout consisté à écrire la recette, le test de fumée et les étapes de CI, puis à résoudre le cas de Linux.
