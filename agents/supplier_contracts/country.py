"""Normalize briefing country names onto the existing directory enum."""

from __future__ import annotations

from agents.supplier_contracts.constants import DIRECTORY_COUNTRY_USA

_TO_DIRECTORY = {
    "united states": DIRECTORY_COUNTRY_USA,
    "us": DIRECTORY_COUNTRY_USA,
    "usa": DIRECTORY_COUNTRY_USA,
    "uk": "UK",
    "united kingdom": "UK",
}

_TO_BRIEFING = {
    DIRECTORY_COUNTRY_USA: "United States",
    "UK": "United Kingdom",
}


def to_directory_country(value: str) -> str:
    key = value.strip().lower()
    if key not in _TO_DIRECTORY:
        raise ValueError(f"unsupported_country:{value}")
    return _TO_DIRECTORY[key]


def to_briefing_country(directory_country: str) -> str:
    if directory_country not in _TO_BRIEFING:
        raise ValueError(f"unsupported_directory_country:{directory_country}")
    return _TO_BRIEFING[directory_country]
