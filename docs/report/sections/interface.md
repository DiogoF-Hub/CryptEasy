# 7.3 Interface graphique

*Auteur : Yanis (Track B). Captures d'écran : [guide utilisateur](../../user-guide.md) (annexe C).*

## Ce qui fonctionne

L'interface est complète et branchée sur le vrai moteur (`core/` et `keystore/`) depuis le 19/11 (#21). Tout le parcours du CDC se fait dans une fenêtre CryptEasy, sans navigateur : créer sa clé, ajouter un contact, chiffrer, déchiffrer.

Elle compte six écrans, accessibles par la barre du haut :

- **Accueil** : un premier pas guidé (« Créer ma paire de clés »), puis des raccourcis vers les quatre actions.
- **Mes clés** : créer une paire de clés avec un niveau de sécurité (Très fort, Fort, Moyen, Faible, ou réglages à la main), importer une clé (y compris un `.pem` OpenSSL), changer la phrase secrète, exporter la clé publique ou privée. Un indicateur note toujours le réglage le plus faible.
- **Contacts** : ajouter une clé publique par fichier ou par copier-coller, afficher son empreinte avec le rappel de la vérifier de vive voix, renommer, supprimer.
- **Chiffrer** : un fichier ou un dossier (taille, nombre de fichiers et temps estimé affichés), pour un contact ou pour soi, avec une barre de progression. Le paquet reçoit un nom neutre.
- **Déchiffrer** : la bonne clé est trouvée toute seule grâce à l'empreinte de l'en-tête. Un dossier peut être gardé en `.zip` ou extrait dans un nouveau dossier.
- **Info** : le chiffrement hybride, les niveaux de sécurité, le format du paquet et les bons réflexes.

L'interface existe en **français et en anglais** (293 textes par langue). Au premier lancement, elle prend la langue du système ; le choix fait ensuite est retenu. Chaque erreur du moteur s'affiche avec un message clair dans la langue choisie, par exemple « Phrase secrète incorrecte pour cette clé » ou « Ce fichier est endommagé ou a été modifié » (F7). Le guide utilisateur (`docs/user-guide.md`, #28) montre chaque écran en capture.

## Choix techniques

- **Flask affiché dans une fenêtre native (pywebview).** Flask était déjà connu de l'équipe, et le HTML / CSS permet une interface soignée plus vite qu'une bibliothèque graphique classique. pywebview affiche ces pages dans une vraie fenêtre (WebView2 sous Windows, WebKitGTK sous Linux) : l'utilisateur voit un logiciel, pas un onglet, et fermer la fenêtre quitte l'application.
- **Un serveur local verrouillé.** Flask n'écoute que sur 127.0.0.1, sur un port aléatoire, avec un jeton différent à chaque lancement. S'y ajoutent la protection CSRF (Flask-WTF), la vérification de l'en-tête `Host` (contre le DNS rebinding) et une politique de sécurité du contenu (CSP). Un site ouvert dans le navigateur ne peut donc pas piloter CryptEasy.
- **Les fichiers ne passent jamais par HTTP.** Les fichiers sont choisis avec les boîtes de dialogue natives du système, et Python lit et écrit directement sur le disque. La page ne manipule que des identifiants aléatoires, jamais un chemin. Les longues opérations tournent en arrière-plan, et la page affiche leur progression.
- **Un faux moteur pour travailler en parallèle.** Les routes passent par une interface `Backend`. Un `FakeBackend`, qui imite le format sans rien chiffrer, a permis de construire et de tester toute l'interface dès le 15/10, avant que le moteur existe (risque R5 évité). Le brancher sur le vrai moteur (#21) n'a demandé qu'un seul fichier, `real_backend.py`, sans toucher aux routes.
- **Traductions dans des fichiers JSON.** Il y a un fichier par langue (`fr.json`, `en.json`) et aucun texte dans le code. Si un texte manque, l'anglais prend le relais, et un test vérifie que les deux fichiers ont les mêmes clés. Ajouter une langue revient à ajouter un fichier (décision du 18/10).

## Difficultés rencontrées

| Difficulté | Traitement |
| --- | --- |
| La spec est passée d'une page dans le navigateur (envoi et téléchargement des fichiers) à une fenêtre pywebview. | Le choix des fichiers a été refait avec les boîtes natives. Comme les écrans reposaient déjà sur l'interface `Backend`, seule cette partie a changé. |
| L'interface était prête avant le moteur : #21 dépendait de #8, #11 et #12 (risque R6). | Le `FakeBackend` a permis d'avancer sans attendre. Une fois le moteur fusionné le 14/11, le branchement s'est fait en un commit. |
| Les erreurs du moteur sont des exceptions Python, illisibles pour un utilisateur. | Chaque exception (`WrongPassphraseError`, `DecryptionError`…) est traduite en un message clair, en français et en anglais. Les tests vérifient chaque cas, et il a fallu créer deux messages manquants (nom refusé, données abîmées). |
| Tester une interface sans ouvrir de fenêtre, notamment dans la CI. | Les boîtes de dialogue sont simulées dans les tests. Tous les tests de l'interface tournent deux fois : sur le faux moteur et sur le vrai. Le parcours complet a aussi été vérifié dans un navigateur piloté (Playwright). |
| Un serveur web local peut être visé par n'importe quel site ouvert sur le PC. | Les protections décrites plus haut (jeton, CSRF, `Host`, CSP) ont été ajoutées dès le départ, chacune avec ses tests. |

## Ce qui manque par rapport au CDC

- **Signature des fichiers (F9, bonus)** : elle a été retirée du périmètre le 08/11. La page Info n'en parle plus (#22).
- **Clés abîmées** : un dossier de clé abîmé sur le disque est ignoré sans prévenir l'utilisateur. Les autres clés restent utilisables. Un avertissement à l'écran serait une amélioration simple (section 9).
- **Page Info** : deux cartes se touchent, sans espace entre elles (#67). C'est purement visuel, et ce n'est pas corrigé à cause du gel du code (section 9).
- **macOS** : l'interface tourne depuis les sources, mais aucun exécutable n'est produit (décision d'équipe, voir 7.4).

## Temps estimé et temps réel

Les tâches de l'interface prévues dans le board totalisent 15,5 h. S'y ajoutent deux tâches qui n'y figuraient pas : la première version de l'interface, écrite le 15/10 avant le board et publiée le 05/11, et le thème « verre dépoli » (#53).

| Tâche | Estimé | Réel |
| --- | --- | --- |
| Première interface sur le faux moteur (15/10 → 05/11, hors board) | — | [? h] |
| #14 PR de l'interface vers `main` | 0,5 h | 2 h |
| #53 Thème verre dépoli (non prévu) | — | [4 h] |
| #21 Brancher le vrai moteur | 6 h | [8 h] |
| #22 Page Info à jour | 1 h | [1 h] |
| #28 Guide utilisateur | 3 h | [1 h] |
| #29 Cette section du rapport | 2 h | [2 h] |
| #30 Démo et vidéo de secours | 3 h | [4 h] |
| **Total** | **15,5 h** | **[? h]** |
