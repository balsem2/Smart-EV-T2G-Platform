# PRÉSENTATION VoltHub — TEXTE FINAL (5 personnes, ~22 min)

Mode d emploi : chaque section = le TEXTE à mettre sur les slides (bullets courts, prêts à coller)
+ CE QUE TU DIS (script oral) + CE QUE TU MONTRES (démo/onglet). Images à insérer indiquées.

## RÉPARTITION — consignes ↔ personnes

| Consigne (4 parties) | Couvert par | Slides |
|---|---|---|
| Partie 1 : Complexité de la charge mobile | P1 (le VE roule, 3 rôles) + P3 (V1G/V2G, équilibrage) + démo flotte | Slides 1 et 3 |
| Partie 2 : Plate-forme digitale + estimation lieux/temps/durée/coût | P2 (bornes, données) + P3 (algorithme) + P4 (application) | Slides 2, 3, 4 |
| Partie 3 : Business model | P5 | Slide 5 |
| Partie 4 : Retours d expérience + démo | P4 (pays/constructeurs) + P5 (démo finale) | Slides 4b et 6 |

---

## PERSONNE 1 — Architecture générale

### SLIDE 1 — « L architecture d une plateforme T2G »

TEXTE SUR LE SLIDE (au centre : le schéma EV → Borne → Application → Cloud → IA → Réseau ;
insérer architecture.svg) :

- Chaîne T2G : VE + batterie → Borne intelligente → Application → Plateforme cloud (API) → Moteur d optimisation → Réseau
- Architecture 3 couches : Interface ⇄ API REST (12 endpoints) ⇄ Moteur (Load Orchestrator)
- Communication : HTTP/JSON entre chaque brique — temps réel (rafraîchi toutes les 5 s)
- Flux de données : session → mesure (toutes les 10 min) → facturation
- Flux d énergie : charge la nuit (vallée de prix) · décharge au pic (18-21 h)
- Zéro dépendance : Python stdlib · 52 tests automatisés · 0 erreur

CE QUE TU DIS : « Notre plateforme connecte trois mondes : les véhicules, les bornes et le réseau.
Trois couches : une interface web bilingue, une API REST de 12 endpoints, et le moteur d optimisation —
le Load Orchestrator. Chaque flèche du schéma correspond à du code qui tourne en ce moment, validé par 52 tests. »

CE QUE TU MONTRES : architecture.svg (30 s) → puis onglet 5 « Flotte mobile » → « Lancer la journée » (20 s) :
le VE roule (orange), charge la nuit (vert), restitue au pic (rouge).

Lien consignes : intro Partie 1 (le VE roule) + architecture de la Partie 2.

---

## PERSONNE 2 — Smart Charger + communication EV

### SLIDE 2 — « La borne intelligente : mesurer, limiter, communiquer »

TEXTE SUR LE SLIDE :

- Puissance = MINI(borne, véhicule) : CA 7-22 kW (maison/bureau) · DC 50-150 kW (autoroute)
- Contrôle de puissance : modulation (pic divisé par 2 à coût égal) + courbe de charge (taper > 55 % SoC)
- Mesure de l énergie : compteur toutes les 10 minutes (kWh + euros)
- Communication borne ⇄ véhicule ⇄ plateforme : session = boucle mesure/facturation (équivalent OCPP)
- 4 données mesurées : SoC (%) · Puissance (kW) · Temps restant (h) · Heure de départ (contrainte)
- Bornes bidirectionnelles (V2G) vs standard ; places libres en temps réel

CE QUE TU DIS : « Une borne intelligente ne fait pas qu’alimenter : elle mesure, elle limite la puissance,
et elle dialogue avec la plateforme. Voici les 4 données qu elle remonte en continu. »

CE QUE TU MONTRES : onglet 2 → jauge SoC en direct + tableau « Journal de télémétrie » (chaque ligne = une mesure).
Dire : « Une vraie borne enverrait ces lignes via OCPP. »

Image : capture du journal de télémétrie (onglet 2).
Lien consignes : Partie 2 — les contraintes fonctionnelles du chargeur intelligent.

---

## PERSONNE 3 — Optimisation IA + V1G/V2G (LE CŒUR)

### SLIDE 3 — « Le cerveau : QUAND · À QUELLE PUISSANCE · QUI RESTITUE »

TEXTE SUR LE SLIDE (haut : les entrées / bas : le tableau des décisions) :

Entrées du moteur :
- Prix de l électricité (spot 24 h : 0,10 EUR nuit → 0,38 EUR pic)
- État du réseau (courbe CO2 : 40 g nuit → 420 g pic = gaz)
- Renouvelables : le solaire de midi se voit dans la courbe CO2
- Préférences utilisateur : SoC · cible · fenêtre · V2G on/off · usure

Décisions :
| V1G (reseau -> VE) | charge dans les heures les moins chères | -59,6 % de coût |
| PUISSANCE | modulation : pic divisé par 2 à coût égal | 22 → 13,5 kW |
| V2G (bidirectionnel) | décharge au pic, réserve 30 % JAMAIS violée | coût net NÉGATIF |
| Équilibrage réseau | vallee la nuit + decharge au pic | pic de charge -65 % |

Note honnêteté : usure batterie modélisée (0,07 EUR/kWh cyclé) — arbitrage rentable mais marginal.

CE QUE TU DIS : « Voici le coeur : le moteur reçoit les prix, l état du réseau et les préférences du conducteur,
et décide QUAND charger, À QUELLE PUISSANCE, et quels véhicules restituent de l énergie —
sans jamais violer la réserve de 30 % ni la contrainte de départ. »

CE QUE TU MONTRES : onglet 1 → Optimiser (45 -> 80 %) : plan graphique + « -59,6 % » + « Pic réduit à 13,5 kW » ;
puis SoC 80 % → coût net NÉGATIF ; onglet 4 → les deux courbes (pic -65 %).

Image : capture du graphique du plan (barres vertes la nuit, rouges au pic, courbe de prix).
Lien consignes : le cœur de la Partie 2 + la démonstration de la Partie 1.

=== SUITE (PERSONNES 4-5) DANS LA SECTION SUIVANTE ===

---

## PERSONNE 4 — Application utilisateur + retours d expérience

### SLIDE 4 — « L application conducteur »

TEXTE SUR LE SLIDE (autour d une capture de la CARTE, onglet 1) :

- LOCALISATION : carte interactive, detour km, accessibilite (SoC insuffisant = borne ecartee)
- DISPONIBILITE : occupation en temps reel (vert = libre, rouge = pleine, « 3/6 libres »)
- ESTIMATION DU TEMPS : duree simulee minute par minute (courbe de puissance)
- ESTIMATION DU COUT : prix horaires + marge + frais − revenus V2G (+ empreinte CO2)
- PREFERENCES UTILISATEUR : sliders SoC/cible · V2G on/off · usure batterie
- BONUS : planificateur de trajet (« dois-je m arreter pour recharger ? ») · bilingue FR/EN

Positionnement honnete : application web responsive (utilisable sur mobile) ; app native en roadmap.

CE QUE TU DIS : « Tout ce que le conducteur veut : ou charger, est-ce libre, combien de temps,
combien ca coute — et le platforme respecte ses preferences. »

CE QUE TU MONTRES : carte → survol d une borne (info-bulle : nom, prix, places libres) ;
puis planificateur : Zoe a 12 % vers l Aeroport → l app propose l arret (1,3 km de detour).

Image : capture de la carte avec info-bulle.
Lien consignes : Partie 2 — l estimation des lieux, du temps, de la duree et du cout cote conducteur.

### SLIDE 4b — « Ce qui existe déjà dans le monde » (retours d expérience)

TEXTE SUR LE SLIDE :

Par pays :
- Norvege : 90 % de VE neufs (fiscalite totale) · reseau hydro deja flexible
- Pays-Bas : Jedlix <-> TenneT, leader de l orchestration (congestion reseau)
- France : Elli Flex / Mobilize ; reseau nucleaire bas-carbone
- Allemagne : pionnier ISO 15118-20 (Plug and Charge + bidirectionnel), Solarpaket 2024
- USA (Californie) : FERC 2222 ouvre les marches DER ; bus scolaires V2G (Nuvve)
- Chine : pilotes V2G a Shanghai ; NIO echange de batteries ; TELD (plus grand reseau)

Par constructeur / energeticien :
- Volkswagen : a CREE Elli en 2018 (marque energie du groupe) — PAS un rachat
- Shell : rachete NewMotion (2017) et Greenlots (2019) · BP : rachete Chargemaster (2018)
- GM + Bechtel : reseau de bornes aux USA · Enel X : JuiceBox + orchestration
- = exactement les combinaisons du Tableau 5.1 du livre blanc Guidehouse

CE QUE TU DIS : « Ce n est pas de la science-fiction : chaque modele qu on presente existe deja,
dans un pays ou chez un constructeur. Notre prototype les combine. »

CE QUE TU MONTRES : onglet 6 « Retours d experience » (tableau + graphique).

Image : capture de l onglet 6.
Lien consignes : Partie 4 — retours d experience par pays et par constructeur.

---

## PERSONNE 5 — Backend + business model + DEMO FINALE

### SLIDE 5 — « Ce qui tourne derriere — et comment ca rapporte »

TEXTE SUR LE SLIDE (2 colonnes) :

BACKEND LIVRE :
- API REST : 12 endpoints (le « cloud » de la plateforme)
- Registre des sessions actives = gestion des vehicules/utilisateurs connectes
- Historique de recharge : journal de telemetrie complet
- Paiement : compteurs « Paye (EUR) / Gains V2G (EUR) » — modele par kWh
- Securite : serveur stdlib isole ; auth + TLS + base de donnees = roadmap (SQLite)

BUSINESS MODEL (Guidehouse) :
- 4 modeles : Infrastructure Developer (2 cEUR/kWh) · Charging Service Provider (8 cEUR/kWh + frais)
  · Load Orchestrator (arbitrage + capacite 15 EUR/kW-an) · Mobility Provider (MaaS)
- VALUE STACKING : combiner les 4 = +64 % (507 kEUR/an pour 500 VE)
- Paiement par l utilisateur EV (kWh + abonnement) · services aux fournisseurs d energie
- Remuneration V2G pour le conducteur · point mort d une borne : 5 ans (CA 22 kW a 10 %)

CE QUE TU DIS : « Derriere l ecran : une API, un registre de sessions, un historique et une facturation.
Et devant : 4 modeles economiques qui s empilent — +64 % de revenus par rapport a la recharge seule. »

CE QUE TU MONTRES : onglet 3 → curseur « Taux d utilisation » → le point mort change en direct.

Image : capture du graphique « Revenus annuels par modele ».
Lien consignes : Partie 3 — business model (qui fait quoi, qui paie, ou acheter).

### SLIDE 6 — « DEMO T2G en direct » + conclusion

TEXTE SUR LE SLIDE (plein ecran, une phrase) :
« Un conducteur qui GAGNE de l argent avec sa voiture garee »

Script de demo (les 6 etapes — ton plan) :
1. Ouverture application → localhost:5000
2. Choix borne → onglet 1 → Optimiser (classement des bornes)
3. Analyse batterie → sliders SoC 80 % / cible 80 %
4. Optimisation recharge → plan : decharge au pic, recharge la nuit
5. Smart charging → « Demarrer la session en direct » → « Lecture auto »
6. Mode V2G → Gains V2G montent → a la fin : COUT NET NEGATIF (le conducteur gagne)

Conclusion (3 phrases) :
- Le VE = charge, stockage, centrale — notre plateforme orchestre les trois (SAS/Intel)
- 4 modeles Guidehouse empiles = +64 % — notre moteur implemente le Load Orchestrator
- Limite assume : donnees simulees ; roadmap : OCPP 2.0.1 · ISO 15118-20 · prix reels ENTSO-E

CE QUE TU MONTRES : tout, en direct (voir script). Reprise possible : captures de secours.

Lien consignes : Partie 4 — la demo de votre solution T2G.

---

## MINUTAGE

| Section | P1 | P2 | P3 | P4 | P5 (backend/business) | P5 (demo) |
|---|---|---|---|---|---|---|
| Minutes | 4 | 3 | 5 | 3 | 4 | 4-5 |

Total ~23-26 min. Repeter en priorite la transition P3 → P5 demo (passage de clavier).

## PLAN DE SECOURS

- Demarrer le serveur AVANT la presentation : python3 app.py → localhost:5000
- Captures de chaque onglet dans un dossier « secours » (au cas ou le live echoue)
- PC charge, notifications fermees

## Q&A — reponses preparees

1. Les donnees sont reelles ? → Simulees mais calibrees ; logique metier reelle, 52 tests ; roadmap : prix ENTSO-E reels.
2. Le V2G use la batterie ? → Oui, modélise (0,07 EUR/kWh) — rentable mais marginal. On le montre dans le prototype.
3. Plusieurs VE sur une connexion faible ? → Modulation de puissance + registre ; allocation multi-VE par site = prochaine etape.
4. Il y a une vraie BDD/paiement ? → Modeles dans le prototype ; implementation complete (SQLite, auth, TLS) en roadmap.
5. VW a rachete Elli ? → Non : VW a CREE Elli en 2018. Rachats reels : Shell/NewMotion, BP/Chargemaster.

## SOURCES (les 4 PDFs du projet)

- Guidehouse (T2G white paper) : les 4 modeles + value stacking (Table 5.1) + exemples
- SAS/Intel (Charging Ahead with EV Analytics) : VE = charge/stockage/centrale ; 400 TWh en 2035
- Navigant (Redefining Mobility Services in Cities) : MaaS ; ville modele 3 M habitants / 1,5 M voitures
