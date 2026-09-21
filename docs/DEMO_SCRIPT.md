# Démonstration Smart EV - scénario de soutenance

## Préparation

1. Lancer PostgreSQL 18 et vérifier `GET /health/db`.
2. Depuis `backend`, lancer `..\.venv\Scripts\python.exe -m scripts.sync_energy_charts --days 10 --dry-run`.
3. Si au moins 672 créneaux sont continus et la dernière observation a moins de
   trois heures, lancer la commande sans `--dry-run`. Pour une démo prolongée,
   utiliser `--watch` dans un terminal séparé. Un watcher local a été démarré
   pendant le développement; vérifier qu'il tourne encore avant la soutenance.
4. Lancer FastAPI et React selon le `README.md`; ouvrir `/ai/model-info` pour
   vérifier le nom du modèle et le rapport de backtest.

## Déroulement (5 à 7 minutes)

1. **Compte (45 s)**: inscrire un utilisateur de démonstration. Montrer que le
   premier écran exige une voiture du catalogue; aucune saisie libre de modèle.
2. **Borne (45 s)**: choisir une station autrichienne. Montrer localisation,
   puissance et mention `simulated` de disponibilité. Ne pas dire « temps réel ».
3. **Besoin (45 s)**: saisir SoC actuel, SoC cible et départ dans plusieurs
   heures. Expliquer l'énergie requise: capacité batterie × différence de SoC.
4. **IA (60 s)**: afficher la timeline de 96 créneaux. Montrer prix, charge et
   renouvelables; expliquer `forecast_mode` et dernière observation. Si feed
   périmé, montrer explicitement le retour à la baseline.
5. **Comparaison (60 s)**: normal / V1G / V2G. Expliquer score 55/30/15,
   coût prévisionnel et export V2G **simulé**.
6. **Paiement (45 s)**: choisir un plan et confirmer le paiement **démo**.
   Montrer référence et refus de double paiement.
7. **Résultat scientifique (60 s)**: ouvrir le rapport de backtest. Citer les
   quatre gains MAE et signaler que solaire n'améliore que de 0,7 %.

## Questions anticipées

- **Pourquoi l'Autriche ?** Les stations et les quatre séries énergétiques
  sont cohérentes avec un seul pays.
- **Pourquoi pas un vrai paiement/V2G ?** Il faut un opérateur de paiement et
  du matériel/accord réseau bidirectionnel; le prototype ne les possède pas.
- **L'IA est-elle validée en 2026 ?** Non. Les métriques sont sur 2018; les
  données récentes servent à l'entrée live, et une validation récente reste
  nécessaire avant toute affirmation de précision actuelle.
