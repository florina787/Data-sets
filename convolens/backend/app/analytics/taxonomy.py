"""Topic taxonomy, subthemes and label vocabularies shared by rules, LLM extraction and the UI."""
from __future__ import annotations

TOPICS: dict[str, dict] = {
    "billing_refunds": {
        "label": "Billing & refunds",
        "definition": "Charges, refunds, fees, invoices and payment problems reported by the customer.",
        "keywords": ["refund", "charged", "charge", "billing", "bill", "invoice", "payment", "paid", "fee", "overcharg*",
                     "money back", "credit", "reembolso", "cobro", "remboursement", "facture", "rückerstattung", "rechnung"],
        "subthemes": {"refund_delay": ["refund", "money back", "reembolso", "remboursement", "rückerstattung"],
                      "unexpected_charge": ["charged twice", "double charge", "overcharg*", "unexpected", "extra fee", "fee"],
                      "payment_failure": ["payment failed", "declined", "card", "payment"]},
        "department": "Billing operations",
    },
    "orders_delivery": {
        "label": "Orders & delivery",
        "definition": "Order status, shipping delays, missing or damaged deliveries.",
        "keywords": ["order", "delivery", "deliver*", "shipping", "shipped", "package", "parcel", "tracking", "courier",
                     "arriv*", "pedido", "envío", "livraison", "colis", "lieferung", "paket"],
        "subthemes": {"late_delivery": ["late", "delay*", "still waiting", "hasn't arrived", "not arrived", "where is"],
                      "missing_item": ["missing", "never received", "lost", "not received"],
                      "damaged_item": ["damaged", "broken", "crushed"]},
        "department": "Fulfilment & logistics",
    },
    "account_access": {
        "label": "Account access",
        "definition": "Login failures, password resets, locked or hacked accounts, verification codes.",
        "keywords": ["login", "log in", "password", "locked", "account", "sign in", "verification", "2fa", "code",
                     "hacked", "contraseña", "cuenta", "mot de passe", "compte", "passwort", "konto"],
        "subthemes": {"password_reset": ["password", "reset", "contraseña", "mot de passe", "passwort"],
                      "locked_account": ["locked", "suspended", "disabled"],
                      "security_concern": ["hacked", "unauthori*", "fraud", "suspicious"]},
        "department": "Identity & account support",
    },
    "app_technical": {
        "label": "App & website issues",
        "definition": "Crashes, errors, bugs and failures in apps, websites or devices after updates.",
        "keywords": ["app", "crash*", "error", "bug", "update", "website", "site", "freez*", "not loading", "glitch",
                     "ios", "android", "battery", "aplicación", "application", "fehler"],
        "subthemes": {"crash_after_update": ["update", "crash*", "freez*"],
                      "error_message": ["error", "not loading", "fails"],
                      "device_performance": ["battery", "slow", "lag"]},
        "department": "Product engineering",
    },
    "network_connectivity": {
        "label": "Network & connectivity",
        "definition": "Internet, mobile signal, Wi-Fi and service outages.",
        "keywords": ["internet", "wifi", "wi-fi", "signal", "outage", "network", "connection", "service down", "no service",
                     "speed", "slow internet", "4g", "5g", "broadband", "red", "réseau", "netz"],
        "subthemes": {"outage": ["outage", "down", "no service"],
                      "slow_speed": ["slow", "speed"],
                      "signal_coverage": ["signal", "coverage", "bars"]},
        "department": "Network operations",
    },
    "travel_disruption": {
        "label": "Travel disruption",
        "definition": "Flight delays, cancellations, baggage and rebooking problems.",
        "keywords": ["flight", "delayed", "cancelled flight", "baggage", "bag", "luggage", "gate", "boarding", "rebook",
                     "seat", "vuelo", "maleta", "vol", "bagage", "flug", "gepäck"],
        "subthemes": {"delay_cancellation": ["delayed", "cancel*", "delay*"],
                      "baggage": ["baggage", "bag", "luggage", "maleta", "bagage", "gepäck"],
                      "rebooking": ["rebook", "connection", "missed"]},
        "department": "Travel operations",
    },
    "cancellation": {
        "label": "Cancellation & retention",
        "definition": "Requests to cancel, close or downgrade a service or subscription.",
        "keywords": ["cancel my", "cancel subscription", "cancellation", "close my account", "unsubscribe", "terminate",
                     "switching to", "leave", "cancelar", "résilier", "kündigen"],
        "subthemes": {"cancel_request": ["cancel*", "cancelar", "résilier", "kündigen"],
                      "switching_provider": ["switching", "leave", "competitor"]},
        "department": "Customer retention",
    },
    "service_experience": {
        "label": "Service experience",
        "definition": "Complaints about support responsiveness, wait times or staff behaviour.",
        "keywords": ["customer service", "wait", "hold", "no response", "nobody", "rude", "ignored", "on hold", "hours",
                     "terrible service", "worst", "atención", "service client", "kundenservice"],
        "subthemes": {"long_wait": ["wait", "hold", "hours"],
                      "no_response": ["no response", "ignored", "nobody", "no reply"],
                      "staff_conduct": ["rude", "unprofessional"]},
        "department": "Support operations",
    },
}
OTHER = "other"
UNKNOWN = "unknown"
TOPIC_KEYS = list(TOPICS) + [OTHER, UNKNOWN]

def topic_label(key: str) -> str:
    if key in TOPICS:
        return TOPICS[key]["label"]
    return {"other": "Other", "unknown": "Unknown"}.get(key, key)


RESOLUTION = {
    "resolved_confirmed": "Customer-confirmed resolved",
    "unresolved_explicit": "Explicitly unresolved",
    "solution_offered_unconfirmed": "Solution offered, outcome unconfirmed",
    "unknown": "Unknown",
}
SENTIMENT = {"negative": "Negative", "neutral": "Neutral", "positive": "Positive", "unknown": "Unknown"}
ESCALATION = {"yes": "Escalation requested", "no": "No escalation request", "unknown": "Unknown"}
INTENTS = ["request_refund", "report_problem", "ask_status", "cancel_service", "complain", "request_help", "unknown"]
JOURNEY_STAGES = ["problem", "clarification", "support_action", "follow_up", "escalation", "outcome"]
JOURNEY_LABELS = {
    "problem": "Customer problem", "clarification": "Clarification", "support_action": "Support action",
    "follow_up": "Follow-up", "escalation": "Escalation", "outcome": "Outcome evidence",
}
# Languages whose lexicons the rules analyser covers. Others receive "unknown" sentiment/escalation.
RULES_LANGUAGES = {"en", "es", "fr", "de"}
