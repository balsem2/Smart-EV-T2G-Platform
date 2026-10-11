"""Account-aware help assistant for the Smart EV application.

The assistant is intentionally deterministic: it answers from verified product
rules and account data instead of inventing charging, tariff or availability
information. It therefore remains usable in the academic demo without an
external LLM key.
"""

from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter
from sqlalchemy import func, select

from app import crud, schemas
from app.dependencies import CurrentUser, DatabaseSession
from app.models import Reservation, Station


router = APIRouter(prefix="/assistant", tags=["Assistant"])

DEFAULT_SUGGESTIONS = [
    "How do I plan a charge?",
    "What is Smart V1G?",
    "How does V2G work?",
    "How do my rewards work?",
]


def _normalise(message: str) -> str:
    text = unicodedata.normalize("NFKD", message.lower())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contains(text: str, *phrases: str) -> bool:
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)


def _is_french(text: str) -> bool:
    return _contains(
        text,
        "bonjour",
        "comment",
        "pourquoi",
        "quoi",
        "quel",
        "quelle",
        "combien",
        "kifeh",
        "chnowa",
        "nheb",
        "recharge",
        "voiture",
        "karhba",
        "station",
        "paiement",
        "reservation",
        "recompense",
        "points",
    )


@router.post("/message", response_model=schemas.AssistantMessageRead)
def answer_message(
    payload: schemas.AssistantMessageCreate,
    database_session: DatabaseSession,
    current_user: CurrentUser,
) -> schemas.AssistantMessageRead:
    text = _normalise(payload.message)
    french = _is_french(text)
    vehicles = crud.list_vehicles(database_session, current_user.id)
    active_reservations = database_session.scalar(
        select(func.count(Reservation.id)).where(
            Reservation.user_id == current_user.id,
            Reservation.status == "confirmed",
        )
    ) or 0
    active_stations = database_session.scalar(
        select(func.count(Station.id)).where(
            Station.active.is_(True),
            Station.operational_status == "online",
        )
    ) or 0

    if not text:
        intent = "empty"
        answer = "Écris une question sur Smart EV." if french else "Ask me a question about Smart EV."
    elif _contains(text, "bonjour", "salut", "hello", "hi", "bonsoir", "asslema"):
        intent = "greeting"
        first_name = (current_user.name or "").split(" ")[0]
        answer = (
            f"Bonjour {first_name}. Je peux vous aider avec la recharge, V1G, V2G, les stations, "
            "les réservations, les paiements, les véhicules et les récompenses."
            if french
            else f"Hello {first_name}. I can help with charging, V1G, V2G, stations, reservations, "
            "payments, vehicles and rewards."
        )
    elif _contains(text, "reward", "rewards", "point", "points", "wallet", "recompense", "recompenses", "portefeuille", "flous"):
        intent = "rewards"
        answer = (
            f"Vous avez actuellement {current_user.reward_points} points et €{current_user.wallet_balance:.2f} "
            "dans votre wallet. Les économies V1G donnent des points. Une exportation V2G ajoute des points "
            "et de l'argent seulement après confirmation du compteur par l'opérateur. Lors du paiement, "
            "100 points peuvent réduire le prix de €1."
            if french
            else f"You currently have {current_user.reward_points} points and €{current_user.wallet_balance:.2f} "
            "in your wallet. V1G savings earn points. V2G exports add points and wallet credit only after "
            "operator meter confirmation. At checkout, 100 points can reduce the price by €1."
        )
    elif _contains(text, "v2g", "grid export", "export energy", "reseau", "donner energie"):
        intent = "v2g"
        compatible = [vehicle for vehicle in vehicles if vehicle.supports_v2g]
        compatible_models = ", ".join(vehicle.model or "EV" for vehicle in compatible)
        vehicle_note = (
            f"Votre garage contient {len(compatible)} véhicule(s) compatible(s) V2G"
            f"{f' : {compatible_models}' if compatible_models else ''}."
            if french
            else f"Your garage has {len(compatible)} V2G-compatible vehicle(s)"
            f"{f': {compatible_models}' if compatible_models else ''}."
        )
        answer = (
            f"Le V2G est un service séparé : une voiture compatible envoie une partie de son énergie à une "
            f"station bidirectionnelle bleue, sans descendre sous votre réserve minimale. {vehicle_note} "
            "Après acceptation, l'opérateur confirme l'énergie mesurée ; les points et le reward sont crédités ensuite."
            if french
            else f"V2G is a separate service: a compatible car sends spare energy to a blue bidirectional station "
            f"without going below your minimum reserve. {vehicle_note} After you accept, the operator confirms "
            "the metered energy; only then are points and wallet credit added."
        )
    elif _contains(text, "v1g", "smart charging", "charge intelligente", "recharge intelligente", "normal charging"):
        intent = "v1g"
        answer = (
            "La recharge Normal commence dès que possible. Smart V1G conserve la même énergie demandée mais "
            "déplace la recharge vers une période moins chère ou plus propre avant votre heure de départ. "
            "Vous choisissez le plan et voyez l'horaire exact avant de payer."
            if french
            else "Normal charging starts as soon as possible. Smart V1G keeps the same requested energy but "
            "moves charging to a cheaper or cleaner period before your ready-by time. You choose the plan and "
            "see its exact schedule before payment."
        )
    elif _contains(text, "station", "stations", "borne", "bornes", "map", "carte", "connector", "connecteur"):
        intent = "stations"
        answer = (
            f"La carte affiche actuellement {active_stations} station(s) autrichienne(s) en ligne. Les stations "
            "non compatibles avec le connecteur de votre véhicule ne sont pas sélectionnables. Les emplacements "
            "et puissances viennent d'E-Control, mais les nombres de places libres sont simulés tant que l'API live "
            "n'est pas configurée."
            if french
            else f"The map currently has {active_stations} online Austrian station(s). Stations that do not match "
            "your vehicle connector cannot be selected. Locations and power come from E-Control, but free-charger "
            "counts are simulated until the live API is configured."
        )
    elif _contains(text, "vehicle", "vehicles", "car", "cars", "voiture", "voitures", "vehicule", "vehicules", "karhba", "kraheb", "compatible"):
        intent = "vehicles"
        models = ", ".join(vehicle.model or "EV" for vehicle in vehicles)
        answer = (
            f"Votre garage contient {len(vehicles)} véhicule(s){f' : {models}' if models else ''}. Ajoutez ou "
            "supprimez un véhicule dans My vehicles. Le modèle vient du catalogue contrôlé afin de vérifier "
            "automatiquement la batterie, les connecteurs et la compatibilité V2G."
            if french
            else f"Your garage contains {len(vehicles)} vehicle(s){f': {models}' if models else ''}. Add or remove "
            "a vehicle in My vehicles. Models come from the controlled catalogue so battery, connectors and V2G "
            "compatibility can be checked automatically."
        )
    elif _contains(text, "reservation", "reservations", "booking", "bookings", "reserve", "reserver", "payment", "paiement", "payer", "invoice", "facture"):
        intent = "payment"
        answer = (
            f"Vous avez {active_reservations} réservation(s) confirmée(s). Une réservation est créée seulement "
            "après le choix d'un plan et la confirmation du paiement. Les paiements du prototype utilisent Stripe "
            "Test lorsqu'il est configuré, sinon le paiement académique local. Les factures apparaissent dans Rewards."
            if french
            else f"You have {active_reservations} confirmed reservation(s). A reservation is created only after "
            "you choose a plan and confirm payment. The prototype uses Stripe Test when configured, otherwise the "
            "local academic checkout. Invoices appear under Rewards."
        )
    elif _contains(text, "price", "prices", "cost", "tariff", "prix", "cout", "tarif", "ai", "prediction", "forecast", "ia"):
        intent = "ai_prices"
        answer = (
            "Smart assistant compare les prochaines 24 heures. Il utilise les prix day-ahead autrichiens publiés "
            "quand ils sont disponibles et prédit la demande, le solaire et l'éolien. Les prix affichés sont des "
            "prix de marché en €/kWh, pas le tarif final de la station avec taxes et frais opérateur."
            if french
            else "Smart assistant compares the next 24 hours. It uses published Austrian day-ahead prices when "
            "available and forecasts grid load, solar and wind. Displayed prices are market prices in €/kWh, not "
            "the station's final retail tariff with taxes and operator fees."
        )
    elif _contains(text, "plan", "charge", "charging", "recharge", "recharger", "charger", "chargi"):
        intent = "planning"
        answer = (
            "Pour planifier : ouvrez Plan charging, choisissez votre véhicule, sélectionnez une station compatible "
            "sur la carte, indiquez le niveau actuel, le niveau cible et votre fenêtre de disponibilité. Comparez "
            "Normal et Smart V1G, choisissez un horaire, puis confirmez le paiement et la réservation."
            if french
            else "To plan a charge: open Plan charging, choose your vehicle, select a compatible station on the "
            "map, enter current and target battery levels and your availability window. Compare Normal and Smart "
            "V1G, choose a schedule, then confirm payment and reservation."
        )
    elif _contains(text, "data", "dataset", "source", "donnee", "donnees"):
        intent = "data"
        answer = (
            "Les données énergétiques viennent d'Open Power System Data, Energy-Charts et Open-Meteo. Les stations "
            "viennent du registre autrichien E-Control. La disponibilité des chargeurs et l'export V2G physique "
            "restent simulés dans ce prototype académique."
            if french
            else "Energy data comes from Open Power System Data, Energy-Charts and Open-Meteo. Stations come from "
            "Austria's E-Control register. Charger availability and physical V2G export remain simulated in this "
            "academic prototype."
        )
    else:
        intent = "fallback"
        answer = (
            "Je n'ai pas trouvé une réponse fiable à cette question. Je peux expliquer la planification, V1G, V2G, "
            "les prix, les stations, les véhicules, les paiements, les réservations et les rewards."
            if french
            else "I could not find a reliable answer to that question. I can explain planning, V1G, V2G, prices, "
            "stations, vehicles, payments, reservations and rewards."
        )

    suggestions = {
        "v2g": ["Which of my cars supports V2G?", "How are V2G rewards confirmed?"],
        "v1g": ["How do I plan a charge?", "How do my rewards work?"],
        "rewards": ["How does V2G work?", "Where can I see my invoices?"],
        "stations": ["How is connector compatibility checked?", "How do I plan a charge?"],
        "vehicles": ["Which of my cars supports V2G?", "How are stations filtered?"],
        "payment": ["How do my rewards work?", "How do I plan a charge?"],
        "ai_prices": ["What is Smart V1G?", "Where does the data come from?"],
        "planning": ["What is Smart V1G?", "How are stations filtered?"],
        "data": ["How does the AI choose a charging time?", "Are station availabilities live?"],
    }.get(intent, DEFAULT_SUGGESTIONS)

    return schemas.AssistantMessageRead(intent=intent, answer=answer, suggestions=suggestions)
