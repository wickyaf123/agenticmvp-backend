"""Disclosure phrase builder for recording + AI identity.

Phase 0: returns conservative defaults. Phase 3 wires per-jurisdiction rules.
"""
from __future__ import annotations

# Two-party consent recording states (US). Conservative list — verify with counsel.
TWO_PARTY_CONSENT_STATES = {
    "CA","CT","FL","HI","IL","MD","MA","MT","NV","NH","PA","WA",
}


def recording_disclosure(*, jurisdiction: str | None) -> str:
    """First-5-seconds line. Always disclose; harden for two-party states."""
    if jurisdiction and "-" in jurisdiction:
        country, region = jurisdiction.split("-", 1)
        if country == "US" and region in TWO_PARTY_CONSENT_STATES:
            return (
                "This call may be recorded for quality and training purposes. "
                "If you do not consent, please let me know now and I will end the call."
            )
    return "This call may be recorded for quality and training purposes."


def ai_disclosure(*, jurisdiction: str | None, force: bool = False) -> str | None:
    """Return disclosure phrase or None if not required for this jurisdiction.

    Default: disclose. Several US states (CA, CO, etc.) and the EU AI Act make
    this de-facto required. Only suppress if `force=False` and we have explicit
    config saying it isn't needed.
    """
    return "Just so you know, you're speaking with an AI assistant on behalf of AgenticMVP."
