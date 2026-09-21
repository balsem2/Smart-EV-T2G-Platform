# SLIDES — version « recherche » (chiffres uniquement issus des PDFs, sans le prototype)

Tous les chiffres de ce deck sont traçables vers les 4 PDFs du projet.
Aucun chiffre du simulateur. Le prototype n apparaît qu à la fin (démo).

---

## SLIDE 1 — Partie 1 : Complexité de la charge mobile

Titre : « Pourquoi la charge des VE est un défi pour le réseau »

- La demande en électricité des VE pourrait dépasser **400 TWh par an en 2035**
  — la plus forte croissance de charge en une génération (Source : SAS/Intel, EV Analytics)
- Un VE est **3 choses à la fois** : une charge (il consomme), un stockage (garé branché),
  une source d alimentation (il restitue) (SAS/Intel)
- Et il se déplace : le gestionnaire de réseau n a JAMAIS une visibilité complète
  de sa position ni de sa charge (SAS/Intel)
- Les réseaux locaux n ont pas été conçus pour ces charges : risque de congestion
  sans pilotage (SAS/Intel)
- 2025 : année où les VE entrent dans le grand public — il faut préparer
  l infrastructure MAINTENANT (SAS/Intel)

Démo/illustration : schéma des 3 rôles (charge / stockage / centrale) dessiné sur le slide.
Phrase : « La complexité vient de là : le VE change de rôle et de position en permanence. »

---

## SLIDE 2 — Partie 2 : La plate-forme digitale (notre conception)

Titre : « Ce que doit faire la plateforme : le cerveau entre VE, bornes et réseau »

- La littérature est claire : l électrification des transports est un PROJET DE DIGITALISATION —
  les modèles économiques reposent sur l IoT et l analytique (SAS/Intel)
- Les véhicules ACES (Autonomes, Connectés, Électriques, Partagés) sont la fondation
  de la plateforme T2G (Guidehouse)

Notre conception — les 4 estimations que la plateforme doit calculer :
- LIEUX : classer les bornes (détour, accessibilité selon la batterie)
- TEMPS : créneaux horaires les moins chers (prix de l électricité variable)
- DURÉE : simulation de la courbe de puissance (elle diminue quand la batterie se remplit)
- COÛT : prix de l énergie + frais, optimisés selon le prix du marché

Architecture proposée : VE → Borne intelligente → Application → Plateforme cloud
(API) → Moteur d optimisation → Réseau — communication par API, temps réel.

Contraintes du chargeur intelligent : puissance limitée borne/véhicule,
réserve de batterie, modulation de puissance, bornes bidirectionnelles ou non.

Image : architecture.svg (présentée comme « l architecture que nous avons conçue »).
Phrase : « La digitalisation est le prérequis identifié par la littérature — voici notre conception. »

---

## SLIDE 3 — Partie 3 : Business model (Guidehouse)

Titre : « 4 modèles économiques — et leur empilement »

Les 4 modèles du livre blanc Guidehouse :
- INFRASTRUCTURE DEVELOPER — construit et exploite les bornes
- CHARGING SERVICE PROVIDER — vend le service de recharge
- LOAD ORCHESTRATOR — pilote la charge et la décharge (le cerveau)
- MOBILITY PROVIDER — vend la mobilité comme service (MaaS)

Marché adressable mondial de la plateforme PEV : **150 à 200 milliards USD par an en 2028**
(Guidehouse, Figure 4.1)

VALUE STACKING : les modèles ne sont pas exclusifs — ils se construisent l un sur l autre :
- Shell a racheté NewMotion (2017) et Greenlots (2019) — Developer + Provider
- BP a racheté Chargemaster (2018), le plus grand réseau du Royaume-Uni
- GM + Bechtel : infrastructures de recharge pour ses 20 nouveaux modèles VE (Developer + Provider + Mobility)
- Enel X : JuiceBox (maison, bidding day-ahead en Californie) + JuicePole + JuiceStation
  = Developer + Provider + Orchestrator

Qui paie : le conducteur (kWh, abonnement), les flottes (B2B), le gestionnaire de réseau (flexibilité).
Où acheter : bornes (ABB, Schneider...), énergie (fournisseurs), logiciels eMSP, roaming (Hubject, Gireve).

Phrase : « Plus on empile de modèles, plus la valeur est grande — c est la thèse centrale du Guidehouse. »

---

## SLIDE 4 — Partie 4 : Retours d expérience (pays et constructeurs)

Titre : « Ce n est pas une hypothèse : ça existe déjà »

Par pays (marchés pionniers) :
- Norvège : leader mondial des VE — fiscalité et péages avantageux
- Pays-Bas : orchestration charge-réseau (Jedlix ↔ TenneT), forte congestion = flexibilité valorisée
- France : pilotes V2G (Elli Flex, Mobilize), réseau bas-carbone
- Allemagne : ISO 15118-20 (Plug and Charge + bidirectionnel), Solarpaket 2024
- USA : FERC 2222 ouvre les marchés aux ressources distribuées ; bus scolaires V2G (Nuvve)
- Chine : pilotes V2G à Shanghai ; échange de batteries (NIO)

Par constructeur :
- Volkswagen : a créé ELLI en 2018 — sa marque énergie et recharge (l exemple demandé)
- Les acquisitions du Guidehouse : Shell→NewMotion (2017), BP→Chargemaster (2018)
- GM : partenariat Bechtel pour un réseau de bornes + 20 modèles VE d ici 2023

Phrase : « Chaque modèle de la partie 3 a déjà un acteur réel qui l exploite — notre plateforme les combine. »

---

## SLIDE 5 — Et nous l avons réalisée : démo de notre solution T2G

Titre : « De la conception au prototype fonctionnel »

- Nous avons implémenté l architecture conçue : interface, API, moteur d optimisation
- Le Load Orchestrator décide QUAND, À QUELLE PUISSANCE, et QUI RESTITUE de l énergie
- Données simulées (hypothèses calibrées) — la logique d orchestration est le livrable

DÉMO (3-4 min) : la flotte qui bouge → le plan de recharge optimisé → le V2G au pic
→ le conducteur économise, le réseau est soulagé.

Phrase de conclusion : « La littérature décrit le quoi et le pourquoi ; notre prototype montre le comment. »

---

## NOTE IMPORTANTE (pour vous, pas pour les slides)

- AUCUN chiffre du simulateur (7 700 kW, -59,6 %, 13,5 kW, +64 %, 507 kEUR, 5 ans) ne doit être
  attribué aux PDFs — ce sont des sorties de NOTRE simulation.
- Les seuls chiffres citables : 400 TWh (2035), 150-200 MdUSD (2028), 3 M/1,5 M (ville modèle), 2025.
- Les parts de marché par pays (Norvege 90 %...) ne sont PAS dans les PDFs — rester qualitatif
  ou citer « données publiques 2023 ».
- VW/Elli : « créé en 2018 », jamais « racheté ».
