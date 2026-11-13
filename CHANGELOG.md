# Journal des modifications

Format : [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/). Les numéros de version suivent [SemVer](https://semver.org/lang/fr/).

## [Non publié]

### Corrigé
- Quand le serveur ne répond plus, un message en français explique quoi faire, au lieu de « Failed to fetch ».
- Exports réels de l’API Figma : la taille automatique des textes (rangée dans leur style) est respectée, et les lignes sont dessinées à leur place.

### Ajouté
- Lancement sur Mac : scripts `install_mac.sh` et `start_app_mac.sh`, double-clic sur « Lancer ProtoLab.command », guide pas à pas (README_MAC.md).
- Sur Mac, la clé API est rangée dans le trousseau de session.
- Design system global et bibliothèque projet en plusieurs fichiers : autant de fichiers de tokens ou de composants qu’il faut, déposés un par un, en .zip ou en dossier entier ; chaque fichier se retire seul, un fichier réimporté sous le même nom remplace l’ancien.
- Les alias de tokens (« {color.brand.primary} ») sont résolus d’un fichier à l’autre, et de la bibliothèque projet vers le design system global ; les alias sans cible sont signalés.

## [0.1.0] - 2026-11-12

### Ajouté
- Projets : document de contexte et specs de SpecGen, maquette Figma (JSON de l’API REST), bibliothèque du projet ; tout est enregistré sur le poste.
- Structure lue sans IA dans le diagramme Mermaid du contexte : modules, écrans, navigation au travers des décisions et des actions système.
- Rattachement automatique des écrans aux frames et aux specs par leur nom, corrigeable à la main ; écran de départ, exclusion d’écrans.
- Conversion des frames Figma en écrans : auto-layout en flexbox, textes, ombres, contours, dégradés, icônes (avec `geometry=paths`), interactions de prototype.
- Points à vérifier avant de générer : écrans sans maquette, frames hors du flow, zones sans auto-layout, liens Figma absents du flow, composants introuvables.
- Design system global (composants, variables Figma ou tokens) partagé par tous les projets.
- Modèle IA (compatible OpenAI, comme SpecGen) : objets métier et données de départ tirés du contexte ; règles des champs, effet des boutons, listes liées aux données et textes de détail, écran par écran.
- Lecteur de prototype : saisie, messages d’erreur, données partagées entre les écrans, destinations conditionnelles, réinitialisation.
- Versions figées, mode test plein écran et export HTML autonome.
