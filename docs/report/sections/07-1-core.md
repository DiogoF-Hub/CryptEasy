# 7.1 Moteur cryptographique

Le moteur (`src/crypteasy/core/`) contient toute la cryptographie de l'application. Il n'utilise que la bibliothèque `cryptography`, la plus utilisée en Python : aucune primitive n'est écrite à la main, car un algorithme de chiffrement « fait maison » est presque toujours cassable.

## Les clés (`keys.py`, `kdf.py`)

Une paire de clés contient deux clés :

- **une clé de chiffrement**, au choix :
  - **X25519** (par défaut) : une clé sur courbe elliptique. Elle est petite (32 octets) et rapide, et à peu près aussi solide qu'une clé RSA-3072 ;
  - **RSA** 2048, 3072 ou 4096 bits : l'algorithme le plus connu, plus lent et avec des clés bien plus grandes. En dessous de 2048 bits, RSA est considéré comme cassable, donc refusé ;
- **une clé de signature Ed25519**, générée avec chaque paire pour la signature des fichiers (voir plus bas).

Sur le disque, la clé privée est verrouillée avec la **phrase secrète** de l'utilisateur. On ne chiffre pas directement avec la phrase : un **KDF** (Key Derivation Function, fonction de dérivation de clé) la transforme en clé AES, et il est volontairement lent, pour qu'un voleur qui essaie des millions de phrases mette des années. Deux KDF sont proposés :

- **Argon2id** (recommandé) : il demande beaucoup de mémoire en plus du temps de calcul, ce qui le rend très difficile à attaquer avec des cartes graphiques ;
- **PBKDF2-SHA256** : plus ancien, il répète SHA-256 des millions de fois. Il reste sûr, mais il ne demande pas de mémoire, donc il est plus facile à attaquer avec des cartes graphiques.

Un **salt** (sel), fait de 16 ou 32 octets aléatoires, est mélangé à la phrase : la même phrase donne un verrou différent pour chaque clé, donc un attaquant ne peut pas préparer ses essais à l'avance pour tout le monde. Ces réglages correspondent aux niveaux de sécurité de la spécification (section 4.2).

## Le chiffrement hybride (`hybrid.py`, `package.py`)

Le chiffrement est **hybride** : on combine un chiffrement symétrique, rapide, pour le fichier, et un chiffrement à clé publique pour verrouiller la clé de ce fichier.

1. Une **nouvelle clé AES** (Advanced Encryption Standard, standard de chiffrement avancé) aléatoire (256 ou 128 bits) est créée pour chaque fichier.
2. Le fichier est chiffré avec **AES-GCM** (Galois/Counter Mode, mode compteur de Galois), par blocs de 64 Kio. GCM chiffre et ajoute à chaque bloc un **tag** (étiquette de contrôle) : toute modification, coupure ou inversion de blocs est détectée. Les blocs évitent aussi de charger un gros fichier entier en mémoire.
3. La clé AES est verrouillée avec la **clé publique du destinataire** :
   - **RSA-OAEP** pour une clé RSA (Optimal Asymmetric Encryption Padding, remplissage optimal : c'est le remplissage sûr de RSA, l'ancien est attaquable) ;
   - pour une clé X25519, un **key exchange** (échange de clés) avec une clé jetable, puis **HKDF** (HMAC-based Key Derivation Function, fonction de dérivation de clé basée sur HMAC) qui transforme le secret commun en clé AES.
4. Le résultat est un paquet `.zip` qui contient exactement `key.enc` (la clé verrouillée) et `file.enc` (le fichier chiffré). Le nom d'origine du fichier est chiffré à l'intérieur, et il n'y a aucun mot de passe à envoyer au destinataire : seule sa clé publique a servi.

Un dossier est d'abord zippé (`folders.py`), puis chiffré comme un fichier.

## Les protections

- **Rien de partiel.** Au déchiffrement, le fichier ne reçoit son vrai nom qu'une fois tous les blocs vérifiés : un échec ne laisse rien sur le disque, et un fichier existant n'est jamais écrasé.
- **Les fichiers des autres sont vérifiés.** Les clés importées, les paquets et les zips de dossiers viennent d'autres personnes : ils sont contrôlés avant d'être utilisés, pour qu'un fichier piégé ne puisse ni bloquer ni faire planter l'application (`pem_guard.py`, #55, #60).
- **Les noms sont nettoyés.** Un nom comme `../../evil.exe` pourrait écrire en dehors du dossier choisi : il devient `evil.exe`. Les noms réservés de Windows (`CON`, `NUL`...) et les caractères invisibles (qui peuvent cacher la vraie extension d'un fichier) sont aussi corrigés.

## Tests

- **127 tests automatiques** couvrent le moteur (section 8.1). Ils tournent sous Linux et Windows à chaque PR.
- **Aller-retour** : chiffrer puis déchiffrer redonne exactement le même fichier, avec chaque type de clé, les deux tailles d'AES, et des tailles limites (fichier vide, 1 octet, 64 Kio plus ou moins 1 octet, 10 Mio).
- **Paquets modifiés** : un octet changé, un paquet coupé, des blocs inversés, ou une clé qui n'est pas la bonne donnent tous la bonne erreur, et **aucun fichier n'est laissé** sur le disque.
- **Fichiers piégés** : noms dangereux, clés importées et paquets construits exprès pour bloquer ou faire planter l'application (#55, #60).
- **Un essai en plus** : 5 000 paquets abîmés au hasard ont été essayés une fois. Tous donnent un message d'erreur clair, aucun ne fait planter l'application.

## Par rapport au CDC

**Fait, comme prévu :**
- chiffrement hybride : AES pour le fichier, RSA ou courbe elliptique (X25519) pour verrouiller la clé AES ;
- génération des paires de clés, avec le choix du type et de la taille de la clé ;
- clé privée protégée sur le disque par une phrase secrète.

**Précisé ou ajouté en cours de route** (décisions du 15 au 18/10, `docs/pm/decisions.md`) :
- le résultat est **un seul paquet `.zip`** (`key.enc` + `file.enc`), avec les réglages de chiffrement dedans : un seul fichier à envoyer ;
- **pas de mot de passe par fichier** : la phrase secrète ne protège que la clé privée sur le disque. Un mot de passe par fichier devrait être envoyé au destinataire par un canal sûr, ce qui est justement le problème que les clés publiques résolvent ;
- **les niveaux de sécurité**, pour choisir tous les réglages en un clic, avec des valeurs sûres par défaut ;
- **le chiffrement de dossiers**, zippés automatiquement par l'application ;
- **la vérification des fichiers piégés** (clés importées, paquets, dossiers), ajoutée après les relectures de code (#55, #60).

**Pas fait :**
- **la signature des fichiers** (F9) : restée un objectif bonus, non prévu dans les sprints faute de temps (décision du 8/11). La clé Ed25519 est déjà générée avec chaque paire, pour pouvoir l'ajouter plus tard sans changer les clés existantes ni les contacts.
