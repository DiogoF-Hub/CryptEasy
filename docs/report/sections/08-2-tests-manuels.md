# 8.2 Tests manuels

Les tests automatiques (section 8.1) vérifient le code, mais pas ce que voit l'utilisateur : l'exécutable lancé sur un PC sans Python, la fenêtre, les boîtes « Ouvrir » et « Enregistrer sous », les messages affichés. Ces points ont donc été testés à la main, sur l'exécutable de la release `v1.0.0rc1`, celui qu'un utilisateur télécharge.

## Une checklist tirée de la spécification

La checklist (`docs/manual-tests.md`, #23) a été écrite le 18 novembre, avant d'avoir l'exécutable, à partir de la spécification technique (sections 3, 4, 5.4 et 7). Chaque test dit quoi faire et ce qu'on doit obtenir : le résultat attendu vient de la spécification, pas de ce que fait l'application. Les parties s'enchaînent (lancement, clés, contacts, chiffrement, déchiffrement, erreurs, page Info) : chacune réutilise ce que la précédente a créé, comme le ferait un vrai utilisateur. Pour chaque échec, la règle était d'ouvrir une issue avec le label `bug`.

Nous avons aussi vérifié les résultats, pas seulement l'affichage : l'empreinte SHA-256 de l'exécutable est comparée à celle publiée avec la release, et chaque fichier déchiffré est comparé à l'original par son empreinte. Pour les erreurs, nous avons fabriqué des paquets modifiés (un octet changé, un paquet coupé en deux), et vérifié qu'aucun fichier à moitié déchiffré ne restait sur le disque.

## Windows : 49 tests sur 49

Windows est le système visé par le cahier des charges, donc la checklist complète y a été déroulée, le 22 novembre, sur Windows 11. Nous voulions la lancer dans Windows Sandbox, pour avoir un PC propre sans Python. Mais Edge ne s'ouvre pas dans la Sandbox, et la fenêtre de l'application utilise le même moteur (WebView2) : une fenêtre vide n'aurait rien prouvé sur CryptEasy. Le test s'est donc fait sur un vrai PC. Python y est installé, mais l'exécutable ne s'en sert pas : PyInstaller embarque son propre Python.

Résultat : **49 tests sur 49 réussis**, aucun bug bloquant.

## Linux : une checklist réduite, sur trois systèmes

Pour le binaire Linux, nous n'avons pas refait les 49 tests. Le chiffrement, les clés, les contacts et les messages d'erreur sont le même code Python sur tous les systèmes, et la CI fait déjà tourner les tests automatiques sous Ubuntu et Windows. Refaire ces tests n'aurait rien appris de plus. Nous avons gardé **16 tests** sur ce qui dépend du système : l'installation décrite dans le README, la fenêtre, les boîtes de dialogue, le dossier de données et ses droits (`drwx------`), « Ouvrir le dossier », la langue et la fermeture.

Jusque-là, la fenêtre Linux n'avait été vue que sur l'Arch Linux de Sam, car la CI construit le binaire sous Ubuntu 22.04 sans pouvoir ouvrir sa fenêtre. Nous avons donc choisi trois systèmes : **Debian 13** sur un PC, **Ubuntu 22.04**, la version sur laquelle le binaire est construit, et **Ubuntu 26.04**, la plus récente, toutes deux en machine virtuelle. Résultat : **16 sur 16 sur chacun, soit 48 sur 48**, les 22 et 23 novembre.

## Ce que les tests ont trouvé

- **L'avertissement SmartScreen.** Au premier lancement, Windows affiche « Windows a protégé votre ordinateur », car l'exécutable n'est pas signé. Ce n'est pas un bug, mais n'importe quel utilisateur tombera dessus au premier lancement et devra cliquer sur « Informations complémentaires », puis « Exécuter quand même ». Nous l'avons noté, et la signature de l'exécutable est une piste d'amélioration (section 9).
- **L'espacement de la page Info (#67).** Diogo a remarqué, en testant l'exécutable, que certaines cartes de la page Info se touchent. Le défaut est seulement visuel, et il a été trouvé après le gel du code : il est noté pour une prochaine version (section 9).
- **Une erreur dans la checklist elle-même.** Le message attendu pour un paquet coupé en deux (test F4) était faux : l'application avait raison, et la checklist a été corrigée le 19 novembre.
- **Des problèmes de machines virtuelles**, pas de CryptEasy : le pilote graphique de VirtualBox à changer pour Ubuntu 26.04, et la langue du système à reconfigurer sur Ubuntu 22.04. Ils expliquent en partie pourquoi les tests manuels ont pris 5 heures au lieu de 3 (section 3).

## Limites

Un seul testeur a déroulé la checklist, et Windows n'a été testé que sur un PC. Le fichier de 1 Go utilisé pour le test de performance ne contient que des zéros : il vérifie que les gros fichiers passent, mais pas le temps réel sur un fichier quelconque.
