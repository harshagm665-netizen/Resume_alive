"""
functions/tools/location_resolver.py — Location normalization tool.
"""

from config import normalize_location

def resolve_location(location: str) -> str:
    """Tool to normalize a location string."""
    return normalize_location(location)
