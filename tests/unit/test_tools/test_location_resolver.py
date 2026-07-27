import sys
import os

# Add the functions directory to sys.path so we can import our modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../functions')))

from tools.location_resolver import resolve_location

def test_resolve_location_lowercase():
    assert resolve_location("Bangalore") == "Bangalore, India"
    assert resolve_location("NEW DELHI") == "Delhi, India"

def test_resolve_location_whitespace():
    assert resolve_location("  Mumbai  ") == "Mumbai, India"

def test_resolve_location_aliases():
    assert resolve_location("bengaluru") == "Bangalore, India"
    assert resolve_location("gurgaon") == "Gurugram, India"
