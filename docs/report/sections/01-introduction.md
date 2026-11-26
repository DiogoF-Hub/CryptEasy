# 1. Introduction

Échanger un fichier sensible de façon sûre reste compliqué pour quelqu'un qui n'est pas du métier. Les outils sérieux, comme GPG en ligne de commande, demandent de comprendre la cryptographie à clé publique avant de pouvoir chiffrer un simple fichier. À l'inverse, certains outils simples donnent une impression de sécurité qui ne correspond pas à la réalité.

**CryptEasy** répond à ce problème. C'est une application de bureau qui s'ouvre dans sa propre fenêtre, comme un logiciel classique, et qui permet de :

- générer une paire de clés, protégée par une phrase secrète ;
- enregistrer les clés publiques de ses contacts ;
- chiffrer un fichier ou un dossier pour un contact, et déchiffrer un paquet reçu.

Le chiffrement est **hybride** : le fichier est chiffré avec une clé AES tirée au hasard, et cette clé est elle-même verrouillée avec la clé publique du destinataire (X25519 ou RSA). Les réglages sûrs sont choisis par défaut, mais un utilisateur avancé peut tout ajuster, et l'application lui indique le niveau de sécurité de ses choix. Elle n'utilise que la bibliothèque reconnue `cryptography` : aucun algorithme n'est écrit à la main. Elle est livrée sous la forme d'un **exécutable autonome**, en français et en anglais : rien à installer, pas besoin de Python.

## Le contexte

CryptEasy est notre projet de SAÉ 5.02, en troisième année de BUT Réseaux et Télécommunications, parcours Cybersécurité, à l'IUT Nancy-Brabois. Nous sommes une équipe de quatre : Diogo Carvalho, Sam Kafai, Yanis Discours et Yani Sai. Le cahier des charges initial, rendu le 15 septembre 2026, prévoyait environ dix semaines de travail.

Ce rapport raconte surtout comment nous nous sommes organisés, et comment nous nous sommes adaptés quand le plan initial n'a pas tenu : le développement a démarré avec cinq semaines de retard, ce qui nous a obligés à tout re-planifier le 8 novembre. Pour l'appuyer, nous nous servons de ce que nous avons gardé tout au long du projet : l'historique Git, les issues et le board GitHub, les comptes rendus de réunion et le journal des décisions.

## Plan du rapport

- **Section 2** : l'organisation réelle, comparée à celle prévue dans le cahier des charges.
- **Section 3** : les durées estimées et réelles des tâches principales, et ce que les écarts nous ont appris.
- **Section 4** : les difficultés rencontrées et la façon dont nous les avons traitées.
- **Section 5** : les changements apportés aux objectifs, en plus et en moins.
- **Section 6** : les choix faits pour préciser les points flous du cahier des charges.
- **Section 7** : l'état final du projet, composant par composant.
- **Section 8** : les tests, automatiques et manuels.
- **Section 9** : les pistes d'amélioration.
- **Section 10** : la conclusion.

En annexe, on trouve notamment le tableau complet des durées, le guide utilisateur et l'utilisation de l'intelligence artificielle par l'équipe.
