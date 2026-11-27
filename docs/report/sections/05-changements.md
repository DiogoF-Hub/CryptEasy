# 5. Changements apportés aux objectifs

Le cahier des charges prévoyait une application qui génère une paire de clés, chiffre un fichier pour un destinataire, le déchiffre, gère un carnet de contacts et, si le temps le permettait, signe les fichiers. Le tout dans un exécutable autonome. Par rapport à ce périmètre, nous avons ajouté des fonctions, et nous en avons retiré d'autres.

## 5.1 Ce que nous avons ajouté

- **Le chiffrement de dossiers** (octobre) : l'application zippe le dossier elle-même, pour que l'utilisateur n'ait pas à le faire à la main.
- **Des niveaux de sécurité** (octobre) : quatre niveaux qui remplissent tous les réglages en un clic (section 6.6).
- **Une interface en français et en anglais** (octobre) : un fichier de traduction par langue, pour qu'ajouter une langue revienne à ajouter un fichier.
- **Un binaire Linux** (novembre) : optionnel dans le planning du 8 novembre, il a pu être fait au sprint 2 et testé sur trois systèmes.
- **Le rejet des fichiers piégés** (novembre) : des protections contre les fichiers de clés et les paquets malveillants (#55, #60), ajoutées après les relectures de code.
- **Un thème graphique** (novembre) : un nouveau look pour l'interface, avec un mode clair et un mode sombre (#53).

## 5.2 Ce que nous avons retiré ou reporté

- **La signature de fichiers.** Le cahier des charges la prévoyait comme fonction complémentaire. Le 8 novembre, nous l'avons laissée hors des sprints, faute de temps. Une clé de signature est tout de même créée avec chaque paire de clés depuis octobre, pour pouvoir l'ajouter plus tard sans rien changer aux clés existantes (section 9).
- **La version macOS.** Passée en dernière priorité le 8 novembre, pour concentrer l'effort sur l'exécutable Windows. Elle n'a pas été faite.

## 5.3 La dérive du périmètre (risque R3)

Le cahier des charges avait identifié ce risque : ajouter des fonctions en cours de route et manquer les échéances. Il s'est produit en partie. La spécification technique d'octobre a ajouté plusieurs fonctions (les dossiers, les niveaux de sécurité, le français et l'anglais, les versions Linux et macOS), alors que le développement n'avait pas commencé.

Le 8 novembre, avec 3 semaines restantes, nous avons recentré le projet : le binaire Linux est devenu optionnel, la version macOS est passée en dernière priorité, et la signature est restée hors des sprints. Les fonctions déjà prévues dans la spécification et utiles à tous les utilisateurs, comme les dossiers et les niveaux de sécurité, ont été gardées.

Un ajout a échappé à ce contrôle : le thème graphique (#53), fait au sprint 1 sans avoir été planifié. Nous l'avons ajouté au board après coup, avec son temps réel (4 heures), pour qu'il apparaisse dans le suivi. Les correctifs de sécurité (#55, #60) sont aussi des ajouts, mais ils étaient nécessaires : ils corrigeaient des failles, pas des fonctions en plus.
