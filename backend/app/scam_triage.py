import hashlib
import json
import re
from datetime import datetime, timezone

URL_RE = re.compile(r"https?://[^\s<>'\"]+", re.I)
SHORTENER_HOSTS = {
    "bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "rb.gy", "rebrand.ly", "shorturl.at"
}
IMPERSONATION_TERMS = {
    "cra", "canada revenue agency", "rcmp", "police", "government", "service canada",
    "bank", "visa", "mastercard", "paypal", "amazon", "microsoft", "apple", "telus",
    "rogers", "bell", "koodo", "fido", "shaw", "crtc"
}
URGENCY_TERMS = {
    "urgent", "immediately", "right now", "within 24 hours", "final warning", "suspended",
    "arrest", "warrant", "legal action", "cut off", "shut off", "account locked", "act now"
}
PAYMENT_TERMS = {
    "gift card", "bitcoin", "crypto", "wire transfer", "etransfer", "e-transfer", "western union",
    "moneygram", "prepaid card", "payment", "send money", "deposit", "fee"
}
CREDENTIAL_TERMS = {
    "password", "passcode", "security code", "verification code", "one-time code", "otp",
    "pin", "banking login", "remote access", "anydesk", "teamviewer", "screen share"
}


def _normalize_number(value: str) -> str:
    raw = (value or "").strip()
    keep_plus = raw.startswith("+")
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return raw[:64]
    return ("+" if keep_plus else "") + digits[:20]


def _contains_any(text: str, terms: set[str]) -> list[str]:
    lower = text.lower()
    return sorted(term for term in terms if term in lower)


def _url_risk(text: str) -> tuple[int, list[str]]:
    reasons = []
    points = 0
    for url in URL_RE.findall(text or ""):
        try:
            host = re.sub(r"^www\.", "", url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0].lower())
        except Exception:
            continue
        if host in SHORTENER_HOSTS:
            points = max(points, 2)
            reasons.append(f"shortened link ({host})")
        elif any(ch.isdigit() for ch in host) and host.count(".") >= 2:
            points = max(points, 1)
            reasons.append(f"unusual link host ({host})")
    return points, reasons[:3]


def score_scam_contact(payload: dict) -> dict:
    number = _normalize_number(str(payload.get("number") or ""))
    channel = str(payload.get("channel") or "call").lower()
    claimed_identity = str(payload.get("claimed_identity") or "").strip()
    message = str(payload.get("message") or "").strip()
    combined = " ".join([claimed_identity, message]).strip()
    received_at = str(payload.get("received_at") or "").strip()
    repeat_count = max(1, min(int(payload.get("repeat_count") or 1), 999))

    score = 1
    factors: list[dict] = []

    def add(points: int, reason: str, evidence: str | None = None):
        nonlocal score
        score += points
        item = {"points": points, "reason": reason}
        if evidence:
            item["evidence"] = evidence
        factors.append(item)

    if payload.get("unsolicited", True):
        add(1, "Unsolicited contact")

    payment_hits = _contains_any(combined, PAYMENT_TERMS)
    if payload.get("requested_money") or payment_hits:
        add(3, "Requested money or a payment method", ", ".join(payment_hits[:4]) or "user indicated payment request")

    credential_hits = _contains_any(combined, CREDENTIAL_TERMS)
    if payload.get("requested_credentials") or credential_hits:
        add(3, "Requested credentials, verification codes, or remote access", ", ".join(credential_hits[:4]) or "user indicated credential request")

    impersonation_hits = _contains_any(combined, IMPERSONATION_TERMS)
    if payload.get("claimed_organization") or impersonation_hits:
        add(2, "Claimed to represent a government body, financial institution, telecom, or major brand", ", ".join(impersonation_hits[:4]) or claimed_identity[:120])

    urgency_hits = _contains_any(combined, URGENCY_TERMS)
    if payload.get("threat_or_urgency") or urgency_hits:
        add(2, "Used urgency, threats, suspension, arrest, or similar pressure", ", ".join(urgency_hits[:4]) or "user indicated threat/urgency")

    link_points, link_reasons = _url_risk(combined)
    if link_points:
        add(link_points, "Contained a potentially risky link", "; ".join(link_reasons))

    if repeat_count >= 3:
        add(1, "Repeated contact", f"{repeat_count} contacts")

    if payload.get("caller_id_mismatch"):
        add(2, "Caller identity did not match the displayed number or verified organization contact")

    if payload.get("known_scam_pattern"):
        add(2, "Matched a known scam pattern reported by the user")

    score = max(1, min(score, 10))
    if score >= 6:
        disposition = "reportable"
        summary = "Enough indicators to report this as a suspected scam/spoofing incident. This score does not identify the owner of the displayed number as the scammer."
    elif score == 5:
        disposition = "uncertain"
        summary = "Borderline. Preserve the evidence and avoid engaging, but there is not enough here for WatchDog to treat it as clearly reportable."
    else:
        disposition = "not_reportable"
        summary = "Low reportability based on the supplied evidence. Keep it archived if you want, but do not treat the displayed number as proven malicious."

    evidence = {
        "displayed_number": number or None,
        "channel": channel,
        "claimed_identity": claimed_identity or None,
        "received_at": received_at or None,
        "repeat_count": repeat_count,
        "message_excerpt": message[:2000] or None,
    }
    evidence_sha256 = hashlib.sha256(json.dumps(evidence, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    report_packet = {
        "classification": "suspected scam/spoofing incident" if score >= 6 else "unconfirmed suspicious contact",
        "reportability_score": score,
        "displayed_number": number or None,
        "received_at": received_at or None,
        "channel": channel,
        "claimed_identity": claimed_identity or None,
        "summary": summary,
        "evidence_sha256": evidence_sha256,
        "important_note": "Caller ID can be spoofed. Report the incident and evidence, not the displayed number's subscriber as the offender unless independently verified.",
        "canada_destinations": [
            {"name": "National Do Not Call List complaint", "url": "https://lnnte-dncl.gc.ca/en/Consumer/File-a-complaint/#!/"},
            {"name": "Canadian Anti-Fraud Centre", "url": "https://reportcyberandfraud.canada.ca/"},
            {"name": "Spam Reporting Centre (texts/commercial electronic messages)", "url": "https://fightspam.gc.ca/eic/site/030.nsf/eng/h_00050.html"},
        ],
        "automatic_submission": {
            "submitted": False,
            "reason": "WatchDog does not submit government complaints without a supported official machine-to-machine intake. The worker prepares the complete incident packet so a reporting connector can be added without fabricating or misattributing reports."
        },
    }

    deterrence = {
        "recommended": "Use as an inbound call-screening or voicemail notice, not as an outbound reply to the displayed number, because the number may belong to an innocent spoofing victim.",
        "message": "This line screens unknown callers. Suspected fraud attempts are logged with timestamps and may be reported to telecom and anti-fraud authorities. Do not request passwords, verification codes, remote access, or payment."
    }

    return {
        "score": score,
        "scale": {"1_to_4": "not reportable", "5": "uncertain", "6_to_10": "reportable"},
        "disposition": disposition,
        "summary": summary,
        "factors": factors,
        "evidence": evidence,
        "evidence_sha256": evidence_sha256,
        "report_packet": report_packet,
        "deterrence": deterrence,
        "scored_at": datetime.now(timezone.utc).isoformat(),
    }
