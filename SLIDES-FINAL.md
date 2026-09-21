# MES SLIDES — version intermédiaire (6 slides, un peu plus de contenu)

## SLIDE 1 — Le problème & notre solution (Personne 1 · 4 min)

- Tous les VE se branchent en même temps le soir (17h-21h) → pic que le réseau ne peut pas absorber
- L'électricité du soir est chère (0,38 €/kWh) et polluante ; la nuit elle est 3 fois moins chère et propre
- Le VE a 3 rôles : il CONSOMME (en charge), il STOCKE (garé branché), il PRODUIT (décharge V2G)
- Et il roule : le réseau perd sa trace — c'est ça, la complexité de la charge mobile
- Notre solution : une plateforme « cerveau » entre les VE, les bornes et le réseau :
  VE → Borne intelligente → Application → Plateforme (API) → Moteur d'optimisation → Réseau
- 3 couches réelles : Interface web (FR/EN) · API REST 12 endpoints · Moteur (52 tests automatisés)

Démo : onglet 5, « Lancer la journée » → la flotte bouge (orange = roule, vert = charge, rouge = rend au pic).
Chiffre clé : pic de 7 700 kW pour 1 000 VE sans pilotage.

## SLIDE 2 — La borne intelligente (Personne 2 · 3 min)

- Puissance limitée par la borne ET le véhicule : CA 7-22 kW (maison/bureau), DC 50-150 kW (autoroute)
- Courbe de charge : la puissance diminue quand la batterie se remplit (protection > 55 % SoC)
- Elle mesure en continu : SoC (%), puissance (kW), temps restant, heure de départ
- Elle communique avec la plateforme : session = mesure + facturation toutes les 10 minutes
- Bornes standards vs bornes bidirectionnelles (V2G) ; places libres en temps réel

Démo : onglet 2 → jauge SoC + journal de télémétrie (chaque ligne = une mesure).
Chiffre clé : une mesure toutes les 10 minutes = l'équivalent du protocole OCPP en prototype.

## SLIDE 3 — L'optimisation V1G / V2G — le cœur (Personne 3 · 5 min)

- Le moteur reçoit : prix spot 24 h · état du réseau (CO₂) · préférences du conducteur
- Décide QUAND : recharge dans les heures les moins chères → économie de 59,6 %
- Décide LA PUISSANCE : modulation — pic divisé par 2 à coût égal (22 → 13,5 kW)
- V1G (unidirectionnel) : charge pilotée, le conducteur économise
- V2G (bidirectionnel) : décharge au pic (18-20 h), réserve de 30 % jamais violée → coût net NÉGATIF
- Résultat pour le réseau : pic de charge réduit de 65 %
- Honnêteté : usure batterie incluse (0,07 €/kWh) — rentable mais marginal

Démo : onglet 1 → optimiser (45→80 %) puis (80 %, coût négatif) ; onglet 4 → les deux courbes.
Chiffre clé : 7 700 kW → 2 709 kW (−65 %) pour 1 000 véhicules.

## SLIDE 4 — L'application conducteur (Personne 4 · 3 min)

- LOCALISATION : carte interactive avec les 8 bornes, détour km, accessibilité selon la batterie
- DISPONIBILITÉ : occupation en temps réel (vert = libre, rouge = pleine, « 3/6 libres »)
- TEMPS : durée de charge simulée minute par minute
- COÛT : prix horaires + marge + frais − revenus V2G (+ empreinte CO₂)
- PRÉFÉRENCES : sliders SoC/cible, V2G on/off, usure batterie
- BONUS : planificateur de trajet (« dois-je m'arrêter ? ») + application bilingue FR/EN
- Web responsive (utilisable sur mobile) ; app native en roadmap

Démo : onglet 1 → survol d'une borne (info-bulle) ; Zoe à 12 % → l'app propose l'arrêt (1,3 km).
Chiffre clé : Zoe à 12 % vers l'aéroport = arrêt nécessaire, détour de seulement 1,3 km.

## SLIDE 5 — Backend & business model (Personne 5 · 4 min)

- Backend livré : API REST 12 endpoints · registre des sessions actives · historique (télémétrie) · facturation
- Sécurité / base de données : en roadmap (prototype = serveur isolé, pas d'auth)
- 4 modèles économiques (Guidehouse) :
  · Infrastructure Developer — 2 c€/kWh · Charging Service Provider — 8 c€/kWh
  · Load Orchestrator — arbitrage V2G + 15 €/kW-an · Mobility Provider — abonnement MaaS
- Value stacking : les 4 combinés = +64 % de revenus (507 k€/an pour 500 véhicules)
- Qui paie : le conducteur (kWh), les flottes (B2B), le gestionnaire de réseau (flexibilité)
- Point mort d'une borne : 5 ans (CA 22 kW à 10 % d'utilisation)

Démo : onglet 3 → curseur « Taux d'utilisation » → le point mort change en direct.
Chiffre clé : +64 % de revenus en combinant les 4 modèles.

## SLIDE 6 — DÉMO T2G en direct (Personne 5 · 4-5 min)

Titre plein écran : « Un conducteur qui GAGNE de l'argent avec sa voiture garée »

Les 6 étapes :
1. Ouvrir l'application (localhost:5000)
2. Choisir la borne → onglet 1 → Optimiser (classement)
3. Analyser la batterie → sliders SoC 80 % / cible 80 %
4. Optimiser le recharge → plan : décharge au pic, recharge la nuit
5. Smart charging → « Démarrer la session en direct » → « Lecture auto »
6. Mode V2G → « Gains V2G » montent → à la fin : COÛT NET NÉGATIF

Conclusion (3 phrases) :
- Le VE est charge, stockage et centrale — notre plateforme orchestre les trois
- 4 modèles économiques empilés = +64 % — notre moteur implémente le Load Orchestrator
- Données simulées (assumé) ; roadmap : OCPP 2.0.1, ISO 15118-20, vrais prix ENTSO-E

Si question VW/Elli : VW a CRÉÉ Elli en 2018 (pas un rachat). Rachats réels : Shell/NewMotion, BP/Chargemaster.
