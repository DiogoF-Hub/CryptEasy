# 7.2 Gestion des clés et contacts

`keystore/` garde les paires de clés de l'utilisateur et son carnet de contacts (#11, #12, #13). Il est terminé et branché sur l'interface depuis le 19/11 (#21).

## Stockage

Tout est dans un dossier propre à chaque utilisateur (`%APPDATA%\CryptEasy` sous Windows, `~/.local/share/CryptEasy` sous Linux) :

| Fichier | Contenu |
|---|---|
| `keys/<id>/private.key` | les deux clés privées (chiffrement et signature Ed25519), verrouillées par la phrase secrète |
| `keys/<id>/public.pem` | les deux clés publiques : le fichier que l'on partage |
| `keys/<id>/info.json` | nom, type de clé, niveau de sécurité, date, empreinte |
| `contacts.json` | nom, clé publique et empreinte de chaque contact |
| `settings.json` | réglages de l'application (la langue) |

- **La phrase secrète** passe par le KDF choisi par l'utilisateur (Argon2id, ou PBKDF2 avec ou sans sel). La clé obtenue chiffre les clés privées en AES-256-GCM. Une mauvaise phrase fait échouer la vérification GCM : « Phrase secrète incorrecte pour cette clé ». Au niveau « Aucune protection », les clés privées sont enregistrées en clair, après un avertissement.
- **Plusieurs paires de clés** sont possibles (par exemple Alice et Bob sur le même PC pour la démonstration). Chaque dossier a un nom aléatoire : le nom choisi par l'utilisateur n'apparaît jamais dans un chemin.
- **Écritures sûres** : chaque fichier est écrit à part puis renommé, et une nouvelle paire de clés n'apparaît qu'une fois complète. Un arrêt brutal ne laisse pas de clé à moitié écrite.
- **L'empreinte** est le SHA-256 de la clé publique de chiffrement (décision du 10/11), affiché en 16 groupes de 4 caractères.

## Fichiers non fiables

Tout fichier lu est traité comme s'il venait d'un attaquant. À chaque lecture, chaque clé de `contacts.json` est relue et son empreinte recalculée : une clé qui ne correspond plus à son empreinte est détectée. En revanche, quelqu'un qui peut écrire dans ce fichier peut remplacer à la fois une clé et son empreinte : c'est pour cela que l'empreinte doit être vérifiée de vive voix avec le contact. Les réglages du KDF d'un `private.key` sont vérifiés avant de lancer le KDF (au plus 1 Gio de mémoire), pour qu'un fichier piégé ne bloque pas l'application. L'import d'une clé `.pem` faite ailleurs (OpenSSL) a révélé que certains fichiers piégés figeaient ou faisaient planter la bibliothèque `cryptography` : un contrôle avant lecture les refuse maintenant (ajouté le 12/11, déplacé dans `core/` par #55).

## Par rapport au CDC (numéros de la spécification technique)

| Fonction | État |
|---|---|
| F1 Générer une paire de clés (X25519, RSA 2048, 3072 ou 4096, niveaux de sécurité) | fait |
| F2 Exporter la clé publique ou privée, importer un `.pem`, changer la phrase secrète | fait |
| F3 Carnet de contacts avec empreintes | fait |
| F9 Signature des fichiers | non fait : objectif bonus, pas prévu dans les sprints (décision du 8/11). La clé Ed25519 est déjà générée avec chaque paire, donc la signature pourra être ajoutée sans changer les clés existantes |

Une limite connue : un dossier de clé abîmé est bien détecté par `keystore/`, mais l'interface ne l'affiche pas encore. La clé est alors simplement absente de la liste.
