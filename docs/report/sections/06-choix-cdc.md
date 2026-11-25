# 6. Choix faits pour préciser les points flous du CDC

Le cahier des charges du 15 septembre décrivait ce que l'application devait faire, mais laissait plusieurs choix ouverts. Nous les avons tranchés pendant la phase de conception, du 15 au 18 octobre. Chaque décision est notée avec sa date et sa raison dans le journal des décisions (`docs/pm/decisions.md`). Pour chacune, nous présentons ce que disait le CDC, ce que nous avons choisi, et l'option que nous avons écartée.

## 6.1 Flask plutôt que Streamlit

**Ce que disait le CDC :** « Interface web (Streamlit ou Flask) », choix à trancher en phase de conception.

**Notre choix (15/10) :** Flask.

**L'option écartée :** Streamlit permet de faire une interface plus vite, avec moins de code. Mais notre livrable principal est un exécutable autonome, et Streamlit se transforme mal en `.exe` avec PyInstaller. Choisir Streamlit, c'était prendre un risque sur la partie la plus importante du projet pour gagner du temps sur l'interface.

## 6.2 Une vraie fenêtre plutôt que le navigateur

**Ce que disait le CDC :** une interface web, sans préciser où elle s'affiche.

**Notre choix (18/10) :** l'application s'ouvre dans sa propre fenêtre, grâce à pywebview, comme un logiciel classique.

**L'option écartée :** ouvrir l'interface dans le navigateur de l'utilisateur. C'était plus simple, mais l'application ressemblait alors à un site web : un onglet de plus, une adresse `127.0.0.1` dans la barre, et une appli qui continue de tourner quand on ferme l'onglet. Le prix de notre choix : la fenêtre dépend d'un composant du système (WebView2 sous Windows, WebKit2GTK sous Linux). Nous l'avons vérifié pendant les tests manuels sur Windows, Debian et Ubuntu (section 8.2).

## 6.3 X25519 comme courbe elliptique par défaut

**Ce que disait le CDC :** une paire de clés « RSA ou courbe elliptique, au choix », sans dire quelle courbe ni lequel proposer par défaut.

**Notre choix :** X25519 par défaut, et RSA en 2048, 3072 ou 4096 bits au choix.

**L'option écartée :** proposer seulement RSA. X25519 offre une sécurité équivalente à RSA-3072 (environ 128 bits) avec des clés beaucoup plus petites et plus rapides. Nous avons tout de même gardé RSA, que le CDC citait en premier et qui reste l'algorithme le plus répandu.

## 6.4 Un seul paquet .zip comme fichier chiffré

**Ce que disait le CDC :** rien sur la forme du fichier chiffré.

**Notre choix (15 au 18/10) :** un seul paquet `.zip` ordinaire, qui contient deux fichiers : `key.enc` (la clé du fichier, chiffrée pour le destinataire) et `file.enc` (le fichier chiffré). Le nom proposé est neutre : il ne révèle pas le nom du fichier d'origine.

**L'option écartée :** un format binaire maison, `.ceasy`, que décrivait encore la première version de la page Info (corrigée par la #22). Avec un seul fichier à envoyer, l'utilisateur ne peut pas oublier la clé, et les réglages de chiffrement voyagent avec le fichier. Un `.zip` est en plus un format standard, qu'on peut ouvrir pour vérifier ce qu'il contient.

## 6.5 Une phrase secrète sur la clé privée, pas un mot de passe par fichier

**Ce que disait le CDC :** une clé privée « protégée par mot de passe », sans dire comment.

**Notre choix (15 au 18/10) :** la phrase secrète protège la clé privée enregistrée sur le disque. Elle passe par une fonction de dérivation (KDF) avec un sel avant de servir de clé. Les fichiers, eux, n'ont pas de mot de passe.

**L'option écartée :** ajouter un mot de passe à chaque fichier. Il aurait fallu le transmettre au destinataire par un canal sûr, ce qui est exactement le problème que le chiffrement par clé publique résout.

## 6.6 Des niveaux de sécurité et le choix du KDF

**Ce que disait le CDC :** des réglages simples pour les débutants, modifiables par les utilisateurs avancés.

**Notre choix (15 au 18/10) :** quatre niveaux (très fort, fort, moyen, faible), qui remplissent tous les réglages en un clic. « Fort » est le niveau par défaut : X25519, AES-256-GCM et le KDF Argon2id. Si l'utilisateur change un réglage à la main, le niveau passe à « personnalisé » et il est noté selon son réglage le plus faible. Pour le KDF, nous proposons Argon2id pour les niveaux hauts et PBKDF2 pour les niveaux bas. Le temps de déverrouillage de chaque niveau a été mesuré le 10 novembre sur un ordinateur portable récent, puis réglé pour rester raisonnable sur un ordinateur moyen.

**L'option écartée :** n'afficher que les réglages techniques, comme le font la plupart des outils de chiffrement. Un débutant ne sait pas quoi choisir entre Argon2id et PBKDF2. Avec les niveaux, il obtient un réglage sûr sans y penser. Nous avons choisi Argon2id par défaut parce qu'il demande beaucoup de mémoire : les cartes graphiques, qui servent à tester des millions de phrases secrètes, l'accélèrent beaucoup moins que PBKDF2.

## En résumé

| Point flou du CDC | Notre choix | Option écartée |
|---|---|---|
| Streamlit ou Flask | Flask | Streamlit, difficile à transformer en `.exe` |
| Une interface web | Sa propre fenêtre (pywebview) | Un onglet du navigateur |
| RSA ou courbe elliptique | X25519 par défaut, RSA possible | RSA seulement |
| La forme du fichier chiffré | Un paquet `.zip` (`key.enc` + `file.enc`) | Un format maison `.ceasy` |
| La protection de la clé privée | Une phrase secrète + KDF + sel | Un mot de passe par fichier |
| Des réglages simples et avancés | 4 niveaux + mode personnalisé | Les réglages techniques seuls |
