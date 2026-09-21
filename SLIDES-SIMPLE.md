# MES SLIDES — version simple (6 slides)

## SLIDE 1 — Le problème (Personne 1)
- Tous les VE se branchent à 19h → le réseau ne suit pas
- Le VE : charge + stockage + centrale
- Notre idée : charger la nuit (pas cher), rendre au pic (cher)

Je dis : « Voici le problème et notre chaîne : VE → borne → application → plateforme → réseau. »
Je montre : onglet 5, la flotte qui bouge.

## SLIDE 2 — La borne intelligente (Personne 2)
- Elle mesure : batterie (SoC), puissance, temps
- Elle limite la puissance (jamais trop fort)
- Elle parle à la plateforme en continu

Je dis : « Voici les 4 données mesurées » → onglet 2, journal de télémétrie.

## SLIDE 3 — Le cerveau (Personne 3)
- Il décide QUAND : les heures les moins chères (−60 % de coût)
- Il décide LA PUISSANCE : pas trop fort (22 → 13,5 kW)
- V2G : la voiture rend de l'énergie au pic → le conducteur gagne
- Résultat : le pic du réseau baisse de 65 %

Je dis : « C'est le cœur du projet. » → onglet 1 puis onglet 4.

## SLIDE 4 — L'application (Personne 4)
- Où charger (carte)
- Est-ce libre ? (temps réel)
- Combien de temps, combien ça coûte
- Mes préférences + planificateur de trajet

Je dis : « Tout ce que le conducteur veut. » → onglet 1, la carte.

## SLIDE 5 — Backend & business (Personne 5)
- Derrière : API, registre des sessions, historique, facturation
- 4 façons de gagner de l'argent → ensemble : +64 %
- Qui paie : le conducteur, les flottes, le réseau

Je dis : « Voici le modèle économique » → onglet 3.

## SLIDE 6 — LA DÉMO (Personne 5)
- « Un conducteur qui GAGNE de l'argent avec sa voiture garée »
- Démo : SoC 80 % → optimiser → démarrer la session → la voiture vend au pic
- Résultat : coût net NÉGATIF

Je conclus : « C'est ça, le T2G. »
