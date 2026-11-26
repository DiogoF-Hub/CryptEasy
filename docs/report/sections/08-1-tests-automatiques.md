# 8.1 Tests automatiques

Le projet compte **637 tests pytest** (au 26/11), un dossier par partie du code. Les 636 tests rapides tournent à chaque PR et à chaque push sur `main` ou une branche `-dev`, sous Linux et sous Windows (section 7.4), et le résultat s'affiche sur chaque PR avant que Diogo la fusionne.

| Partie | Tests | Ce qui est vérifié |
|---|---|---|
| `core/` : moteur cryptographique | 127 | aller-retour chiffrer / déchiffrer avec chaque type de clé et des tailles limites (0 octet, 64 Kio ± 1 octet) ; mauvaise clé ou paquet modifié, tronqué ou réordonné → la bonne erreur et **aucun fichier laissé derrière** ; noms de fichiers piégés (`../../x`) ; dossiers (zip-slip, archive anormalement grosse) ; KDF et ses limites ; fichiers de clés piégés |
| `keystore/` : clés et contacts | 179 | chaque niveau de sécurité, y compris « Aucune protection » ; mauvaise phrase secrète ; fichiers abîmés ou modifiés à la main ; coupure pendant une écriture ; réglages de KDF absurdes refusés avant de lancer le KDF ; import de clés OpenSSL |
| `ui/` : interface | 331 | jeton de lancement, protection CSRF et contrôle de l'en-tête `Host` (attaque par DNS rebinding) ; parcours chiffrer / déchiffrer et clés / contacts ; les erreurs du moteur deviennent le bon message ; chaque texte existe dans les deux langues ; lancement réel de l'application sur 127.0.0.1 |

## Comment ils sont écrits

- **Jamais sur les vraies données.** Chaque test travaille dans un dossier temporaire (`CRYPTEASY_HOME` y redirige les données) avec des clés jetables créées pendant le test : aucune clé n'est enregistrée dans le dépôt.
- **Rapides par défaut.** La suite complète prend moins d'une minute. Une partie des tests de `keystore/` remplace le KDF par un faux, rapide, pour tester le stockage ; d'autres tournent avec le vrai moteur et le vrai KDF, à chaque niveau. Le seul test lent (le niveau « Très fort », 1 Gio de mémoire) est marqué `slow` et se lance avant une release avec `make test-slow`.
- **L'interface est testée deux fois** : sur le faux moteur, puis sur le vrai `core/` et `keystore/`. Les écrans ont ainsi pu être testés un mois avant le moteur, puis le branchement (#21) a été vérifié par les mêmes tests.
- **Les fichiers piégés trouvés en relecture deviennent des tests.** Les relectures des PR #50 et #59 ont révélé des fichiers de clés qui figeaient ou faisaient planter la bibliothèque `cryptography` (#55) et des paquets qui donnaient « Erreur inattendue » au lieu d'un message clair (#60). Chacun est maintenant un test, pour que le problème ne revienne pas.

## Cas limites

Des tests vérifient aussi que les fichiers abîmés donnent un message clair au lieu de faire planter l'application : par exemple un `contacts.json` trop gros, ou un JSON très imbriqué (16 000 `[`) dans un fichier de `keystore/`.

## Limites

- **La fenêtre n'est pas testée automatiquement** : les machines de la CI n'ont pas d'écran. Les tests de l'interface passent par le client de test de Flask, et le test de fumée lance l'exécutable sans fenêtre. La fenêtre elle-même est vérifiée par les tests manuels (section 8.2).
- **La couverture du code n'a pas été mesurée.** Les tests ont été choisis à partir de la spécification (les fonctions F1 à F7 et les messages d'erreur), pas à partir d'un pourcentage de lignes.
