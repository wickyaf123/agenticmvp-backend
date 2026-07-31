"""TCPA time-window guard.

US TCPA: outbound calls only between 8am and 9pm in the **recipient's** local
time. We resolve timezone from E.164 phone number (country + area code)
falling back to country-level when uncertain.

Other jurisdictions: caller must set explicit allowed_window per region.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import phonenumbers
import pytz
from phonenumbers import geocoder, timezone as ph_tz


DEFAULT_TCPA_START_HOUR = 8
DEFAULT_TCPA_END_HOUR = 21  # 9pm


def resolve_timezone(phone_e164: str) -> Optional[str]:
    """Return the most specific IANA timezone for a phone number, or None."""
    try:
        parsed = phonenumbers.parse(phone_e164, None)
    except phonenumbers.NumberParseException:
        return None
    tzs = ph_tz.time_zones_for_number(parsed) or []
    return tzs[0] if tzs else None


def in_allowed_window(
    phone_e164: str,
    *,
    now_utc: Optional[datetime] = None,
    start_hour: int = DEFAULT_TCPA_START_HOUR,
    end_hour: int = DEFAULT_TCPA_END_HOUR,
) -> tuple[bool, str]:
    """Return (allowed, reason). reason is human-readable."""
    tz_name = resolve_timezone(phone_e164)
    if tz_name is None:
        return False, "timezone_unresolved"
    tz = pytz.timezone(tz_name)
    now = (now_utc or datetime.utcnow().replace(tzinfo=pytz.UTC)).astimezone(tz)
    if start_hour <= now.hour < end_hour:
        return True, f"within_window_{tz_name}"
    return False, f"outside_window_{tz_name}_local_hour_{now.hour}"


def country_for(phone_e164: str) -> Optional[str]:
    try:
        parsed = phonenumbers.parse(phone_e164, None)
        return phonenumbers.region_code_for_number(parsed)
    except phonenumbers.NumberParseException:
        return None


def jurisdiction_blocked(phone_e164: str, *, blocklist: set[str]) -> bool:
    """blocklist: {'EU','US-CA',...}. Phase 0 keeps this minimal."""
    country = country_for(phone_e164)
    if country and country in blocklist:
        return True
    # EU shorthand
    EU = {"AT","BE","BG","HR","CY","CZ","DK","EE","FI","FR","DE","GR","HU","IE","IT","LV","LT","LU","MT","NL","PL","PT","RO","SK","SI","ES","SE"}
    if "EU" in blocklist and country in EU:
        return True
    return False
