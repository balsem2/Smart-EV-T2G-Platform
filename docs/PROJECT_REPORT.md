# Smart EV T2G Platform - rapport de projet

## 1. Objectif et périmètre

Smart EV est un prototype académique de Transportation-to-Grid (T2G). Un utilisateur
crée un compte, choisit un véhicule et une borne autrichienne, renseigne son état
de charge (SoC) et son heure de départ, puis compare trois stratégies: recharge
immédiate, V1G (décalage intelligent) et V2G (export simulé vers le réseau).
L'organisation du projet fournie répartit ces sujets entre architecture, borne,
optimisation IA, application utilisateur, backend/business model/démonstration.

## 2. Architecture réalisée

```text
React (compte, véhicule, borne, comparaison, paiement démo, IA)
  -> FastAPI (authentification JWT, catalogue, optimisation, paiements démo)
  -> PostgreSQL 18 (utilisateurs, véhicules, bornes, données énergie, plans)
  -> modèle IA HistGradientBoosting V2 (prix, charge, solaire, éolien)
  -> import Energy-Charts (observations autrichiennes récentes)
```

Le tableau de bord peut afficher un scénario de 96 créneaux de 15 minutes. Les
bornes préchargées sont autrichiennes, mais leur disponibilité est simulée sauf
connexion future à un opérateur. Aucun signal n'est envoyé à une borne réelle.

## 3. Données et IA

L'entraînement et le backtest utilisent 131 158 observations autrichiennes
complètes (2015-2018), issues du fichier OPSD fourni. La série présente huit
lacunes temporelles; les fenêtres incomplètes sont exclues. La séparation est
chronologique (70 % entraînement, 15 % validation, 15 % test). Les variables
cibles sont le prix day-ahead, la charge réseau, la production solaire et
l'éolien terrestre. Le modèle utilise calendrier cyclique, retards et moyennes
glissantes. Le solaire V2 combine des retards journaliers et un mélange 50/50
entre modèle et valeur au même créneau la veille.

Le backtest récursif évalue 29 origines hebdomadaires du test, soit 2 784
prévisions par variable sur 24 h. Comparaison MAE avec une baseline « même
créneau la veille » :

| Variable | MAE IA | MAE baseline | Amélioration |
| --- | ---: | ---: | ---: |
| Prix électricité | 10,44 | 15,81 | 34,0 % |
| Charge réseau | 364,98 | 1 373,86 | 73,4 % |
| Solaire | 38,71 | 38,97 | 0,7 % |
| Éolien | 345,40 | 486,70 | 29,0 % |

La faible amélioration solaire ne constitue pas une preuve de performance
robuste. Les valeurs ci-dessus sont historiques; le modèle n'a pas encore été
réentraîné ni évalué sur les observations récentes.

Un importeur optionnel lit les quatre variables autrichiennes toutes les 15
minutes depuis l'API publique Energy-Charts. Il valide pays, unité, horodatage
UTC, valeurs et continuité avant l'upsert PostgreSQL. Il ne change pas la
période d'entraînement 2015-2018 pour éviter un mélange non validé.

## 4. Algorithme de recharge

Pour chaque créneau candidat, la plateforme calcule un score normalisé:

`0,55 × prix + 0,30 × charge réseau - 0,15 × production renouvelable`.

La recharge normale prend les premiers créneaux. V1G trie par score croissant.
V2G ajoute un créneau d'export simulé et réalloue l'énergie nécessaire pour
atteindre le SoC demandé. Le coût est une estimation fondée sur le prix de gros
en EUR/MWh, pas un tarif de vente final de l'opérateur.

## 5. Services et business model

Le prototype couvre la gestion de compte, le catalogue de véhicules, les
stations, l'historique des demandes, les plans, les points et un paiement
anticipé **simulé**. La carte complète et le CVC ne sont pas enregistrés. Les
recommandations V2G et les récompenses ne sont pas des transactions réseau.

Le positionnement envisagé est une combinaison « charging service provider +
load orchestrator »: service de recharge au conducteur et optimisation de
flexibilité pour un partenaire énergie. C'est une hypothèse de business model,
inspirée des catégories et de la « value stacking » décrites dans le livre
blanc T2G, et non un revenu déjà démontré.

## 6. Vérification

- Tests unitaires: mélange solaire, refus de données périmées, jointure UTC de
  l'API énergie.
- Tests API bout en bout sur base isolée: inscription, ajout véhicule, choix
  borne, demande de recharge, calcul des trois plans, paiement démo et refus
  d'un double paiement. Un second scénario vérifie qu'une série UTC récente
  active effectivement le modèle IA dans un plan.
- Compilation Python et build React effectués.
- Import réel récent vérifié localement: 1 036 créneaux autrichiens contigus au
  moment du test. Ce nombre et la fraîcheur doivent être revérifiés à chaque
  démonstration.

## 7. Limites et travail avant production

1. Réentraîner et évaluer prospectivement le modèle sur les données actuelles;
   détecter dérive et lacunes. Le modèle de 2015-2018 n'est pas validé pour 2026.
2. Maintenir l'import énergie en continu (`--watch` ou ordonnanceur). Sans cela,
   la plateforme revient à la baseline historique après expiration des données.
3. Obtenir auprès d'un opérateur un accès officiel à la disponibilité réelle
   des bornes; les 9 stations et leur statut simulé ne réservent pas de prise.
4. Choisir un prestataire de paiement, ouvrir le compte marchand, intégrer ses
   webhooks et gérer remboursements avant tout encaissement réel.
5. Obtenir une borne et un véhicule bidirectionnels compatibles, ainsi qu'un
   partenaire réseau, avant tout export V2G physique ou récompense réelle.
6. Déployer avec HTTPS, gestion des secrets, monitoring et sauvegardes.

## Références

- `T2G_Platform_Organisation_Projet.pdf`, pages 1-3: répartition des cinq
  domaines et déroulement de la démonstration (document fourni).
- `transportation-to-grid.pdf`, pages 7-12: charging service provider,
  load orchestrator et value stacking (document fourni).
- `Charging Ahead with EV Analytics.pdf`, page 3: intérêt des données et de
  l'analytique pour l'intégration des EV (document fourni).
- Energy-Charts, [API publique](https://api.energy-charts.info/): prix et
  production/charge autrichiens récents, données attribuées à energy-charts.info.
