# 7.3 Interface graphique

L'interface est complète et branchée sur le vrai moteur (`core/` et `keystore/`) depuis le 19/11 (#21). Tout le parcours du CDC se fait dans une fenêtre CryptEasy, sans navigateur. Le guide utilisateur (#28, annexe C) montre chaque écran en capture.

## Écrans et parcours

| Écran | Ce qu'on y fait |
|---|---|
| Accueil | Premier pas guidé (« Créer ma paire de clés »), puis raccourcis vers les quatre actions |
| Mes clés | Créer une paire de clés avec un niveau de sécurité (Très fort à Faible, ou réglages à la main), importer une clé (même un `.pem` OpenSSL), changer la phrase secrète, exporter |
| Contacts | Ajouter une clé publique (fichier ou copier-coller), voir son empreinte à vérifier de vive voix, renommer, supprimer |
| Chiffrer | Un fichier ou un dossier, avec taille, temps estimé et barre de progression ; le paquet reçoit un nom neutre |
| Déchiffrer | La bonne clé est trouvée grâce à l'empreinte ; un dossier est gardé en `.zip` ou extrait dans un nouveau dossier |
| Info | Chiffrement hybride, niveaux de sécurité, format du paquet, bons réflexes |

L'interface existe en **français et en anglais** (293 textes par langue). Elle prend la langue du système au premier lancement, puis retient le choix de l'utilisateur. Chaque erreur du moteur devient un message clair, par exemple « Phrase secrète incorrecte pour cette clé » (F7).

## Choix techniques

- **Flask dans une fenêtre native (pywebview).** Les pages HTML s'affichent dans une vraie fenêtre (WebView2 sous Windows, WebKitGTK sous Linux) : l'utilisateur voit un logiciel, pas un onglet de navigateur.
- **Un serveur local verrouillé.** Flask n'écoute que sur 127.0.0.1, avec un port et un jeton aléatoires à chaque lancement, la protection CSRF et une vérification de l'en-tête `Host`. Un site ouvert dans le navigateur ne peut pas piloter CryptEasy.
- **Aucun fichier ne passe par HTTP.** Les fichiers sont choisis avec les boîtes de dialogue du système, et Python les lit directement. La page ne manipule que des identifiants aléatoires, jamais un chemin.
- **Un faux moteur pour travailler en parallèle.** Les écrans passent par une interface `Backend`. Un `FakeBackend`, qui ne chiffre rien, a permis de construire et tester l'interface dès le 15/10, un mois avant le moteur. Le branchement sur le vrai moteur (#21) n'a touché qu'un seul fichier, `real_backend.py`.
- **Les traductions dans des fichiers JSON** (`fr.json`, `en.json`), sans texte dans le code. Un test vérifie que les deux langues ont les mêmes textes.

## Difficultés

- **La spec est passée** d'une page dans le navigateur à une fenêtre pywebview. Il a fallu refaire le choix des fichiers avec les boîtes natives, mais les écrans n'ont presque pas changé grâce à l'interface `Backend`.
- **Les erreurs du moteur** sont des exceptions Python. Il a fallu les traduire une par une en messages compréhensibles, en deux langues, et ajouter deux messages qui manquaient.
- **Tester sans fenêtre**, notamment dans la CI : les boîtes de dialogue sont simulées, et tous les tests de l'interface tournent deux fois, sur le faux moteur et sur le vrai.

Ce qui manque : un avertissement quand une clé enregistrée est abîmée (elle est ignorée sans rien dire), et l'espace entre deux cartes de la page Info (#67). Les deux sont reportés en section 9.

## Temps estimé et temps réel

| Tâche | Estimé (h) | Réel (h) |
|---|---|---|
| #14 PR de l'interface vers `main` | 0,5 | 2 |
| #21 Brancher le vrai moteur | 6 | 8 |
| #22 Page Info à jour | 1 | 1 |
| #28 Guide utilisateur | 3 | 1 |
| #29 Cette section du rapport | 2 | 2 |
| #30 Démo et vidéo de secours | 3 | 4 |
| **Total des tâches prévues** | **15,5** | **18** |
| #53 Thème « verre dépoli » (non prévu) | — | 4 |
| Première interface, du 15/10 au 05/11 (avant le board) | — | 6 |

Les tâches prévues ont pris 18 h pour 15,5 h estimées (+16 %). #21 a dépassé de 2 h : il a fallu traduire chaque erreur du moteur et faire tourner tous les tests sur les deux moteurs. À l'inverse, #28 a pris 1 h au lieu de 3, car les captures du guide ont été faites automatiquement.
