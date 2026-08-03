"""
Travel MCP Server — exposes travel-specific tools via Model Context Protocol.

The server uses FastMCP and runs over stdio transport so any MCP client
(including app_mcp.py) can spawn it as a subprocess and call its tools.

Start standalone for manual testing:
    python travel_mcp_server.py
"""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("TravelAdvisor")

# ---------------------------------------------------------------------------
# Mock data (simulates a real travel-data backend)
# ---------------------------------------------------------------------------

_DESTINATIONS: dict[str, list[dict]] = {
    "beach": [
        {"name": "Bali, Indonesia", "highlight": "rice terraces + surf beaches", "daily_budget_usd": 60},
        {"name": "Santorini, Greece", "highlight": "caldera sunsets + white-washed villages", "daily_budget_usd": 150},
        {"name": "Phuket, Thailand", "highlight": "island-hopping + street food", "daily_budget_usd": 45},
        {"name": "Maldives", "highlight": "overwater bungalows + world-class diving", "daily_budget_usd": 300},
    ],
    "adventure": [
        {"name": "Queenstown, New Zealand", "highlight": "bungee + skydiving + fjords", "daily_budget_usd": 120},
        {"name": "Patagonia, Argentina", "highlight": "trekking + glaciers + condors", "daily_budget_usd": 80},
        {"name": "Nepal (Himalayas)", "highlight": "Everest Base Camp trek", "daily_budget_usd": 50},
        {"name": "Iceland", "highlight": "northern lights + volcanoes + glaciers", "daily_budget_usd": 180},
    ],
    "culture": [
        {"name": "Kyoto, Japan", "highlight": "temples + geisha districts + zen gardens", "daily_budget_usd": 100},
        {"name": "Rome, Italy", "highlight": "Colosseum + Vatican + pasta", "daily_budget_usd": 120},
        {"name": "Marrakech, Morocco", "highlight": "souks + riads + Sahara day trips", "daily_budget_usd": 55},
        {"name": "Istanbul, Turkey", "highlight": "Blue Mosque + Bosphorus + bazaars", "daily_budget_usd": 70},
    ],
    "nature": [
        {"name": "Costa Rica", "highlight": "rainforest + sloths + active volcanoes", "daily_budget_usd": 75},
        {"name": "Galápagos Islands, Ecuador", "highlight": "endemic wildlife + snorkelling", "daily_budget_usd": 200},
        {"name": "Serengeti, Tanzania", "highlight": "Big Five safari + Great Migration", "daily_budget_usd": 250},
        {"name": "Canadian Rockies", "highlight": "Banff + Lake Louise + bear watching", "daily_budget_usd": 130},
    ],
}

_WEATHER: dict[str, dict] = {
    "Bali, Indonesia": {"best_months": "Apr–Oct", "peak_temp_c": 30, "notes": "Dry season Apr–Oct; avoid the monsoon Nov–Mar"},
    "Santorini, Greece": {"best_months": "May–Oct", "peak_temp_c": 28, "notes": "Shoulder season (May, Sep–Oct) gives fewer crowds"},
    "Queenstown, New Zealand": {"best_months": "Dec–Feb", "peak_temp_c": 22, "notes": "Southern Hemisphere summer; ski season Jun–Aug"},
    "Kyoto, Japan": {"best_months": "Mar–May, Oct–Nov", "peak_temp_c": 25, "notes": "Cherry blossom (late Mar–Apr) and autumn foliage (Nov) are spectacular"},
    "Iceland": {"best_months": "Jun–Aug", "peak_temp_c": 12, "notes": "Aurora viewing Oct–Feb; midnight sun Jun–Jul"},
    "Marrakech, Morocco": {"best_months": "Mar–May, Sep–Nov", "peak_temp_c": 28, "notes": "Avoid Jul–Aug heat that tops 40 °C"},
    "Costa Rica": {"best_months": "Dec–Apr", "peak_temp_c": 27, "notes": "Green season (May–Nov) is cheaper and lush but wetter"},
    "Nepal (Himalayas)": {"best_months": "Oct–Nov, Mar–May", "peak_temp_c": 15, "notes": "Clearest mountain views pre- and post-monsoon"},
    "Rome, Italy": {"best_months": "Apr–Jun, Sep–Oct", "peak_temp_c": 26, "notes": "Summer is hot and crowded; spring/autumn ideal"},
    "Istanbul, Turkey": {"best_months": "Apr–May, Sep–Oct", "peak_temp_c": 23, "notes": "Mild, fewer tourists outside summer"},
    "Patagonia, Argentina": {"best_months": "Nov–Mar", "peak_temp_c": 18, "notes": "Southern summer; weather is unpredictable—layer up"},
    "Serengeti, Tanzania": {"best_months": "Jun–Oct", "peak_temp_c": 26, "notes": "Dry season gives best game-viewing; wildebeest calving Jan–Mar"},
}

_CURRENCIES: dict[str, dict] = {
    "Indonesia": {"code": "IDR", "approx_usd_rate": 15800, "tip": "Use ATMs in cities; bargain freely at markets"},
    "Greece": {"code": "EUR", "approx_usd_rate": 0.92, "tip": "Euro zone; cards accepted almost everywhere"},
    "Thailand": {"code": "THB", "approx_usd_rate": 35, "tip": "Exchange at banks; avoid airport booths"},
    "New Zealand": {"code": "NZD", "approx_usd_rate": 1.62, "tip": "Predominantly cashless; Visa/Mastercard universal"},
    "Japan": {"code": "JPY", "approx_usd_rate": 149, "tip": "Still cash-heavy; withdraw yen at 7-Eleven ATMs"},
    "Morocco": {"code": "MAD", "approx_usd_rate": 10.1, "tip": "Dirhams cannot be exported; spend before leaving"},
    "Iceland": {"code": "ISK", "approx_usd_rate": 136, "tip": "Almost entirely cashless—one card is enough"},
    "Italy": {"code": "EUR", "approx_usd_rate": 0.92, "tip": "Euro zone; 10 % tip appreciated in restaurants"},
    "Turkey": {"code": "TRY", "approx_usd_rate": 32, "tip": "Exchange USD/EUR on arrival; high inflation—check live rate"},
    "Nepal": {"code": "NPR", "approx_usd_rate": 133, "tip": "Exchange at Thamel banks; USD accepted in trekking areas"},
    "Costa Rica": {"code": "CRC", "approx_usd_rate": 512, "tip": "USD widely accepted in tourist zones"},
    "Ecuador": {"code": "USD", "approx_usd_rate": 1, "tip": "Ecuador uses USD—no exchange needed"},
    "Tanzania": {"code": "TZS", "approx_usd_rate": 2530, "tip": "USD cash preferred for national-park fees"},
    "Canada": {"code": "CAD", "approx_usd_rate": 1.36, "tip": "Tap-to-pay is universal"},
    "Argentina": {"code": "ARS", "approx_usd_rate": 350, "tip": "Use Wise or local exchange; blue-chip rate is more favourable"},
    "Maldives": {"code": "MVR", "approx_usd_rate": 15.4, "tip": "USD accepted everywhere; resorts are all-inclusive by default"},
}

_ADVISORIES: dict[str, dict] = {
    "Bali, Indonesia": {"level": "Level 1 – Normal Precautions", "notes": "Petty theft near tourist sites; respect temple dress codes"},
    "Santorini, Greece": {"level": "Level 1 – Normal Precautions", "notes": "Very safe; watch for tourist scams near the port"},
    "Queenstown, New Zealand": {"level": "Level 1 – Normal Precautions", "notes": "One of the safest destinations in the world"},
    "Kyoto, Japan": {"level": "Level 1 – Normal Precautions", "notes": "Very safe; occasional earthquakes—know the evacuation routes"},
    "Nepal (Himalayas)": {"level": "Level 1 – Normal Precautions", "notes": "Altitude sickness above 3 500 m; acclimatise gradually"},
    "Iceland": {"level": "Level 1 – Normal Precautions", "notes": "Weather changes rapidly; always inform others of your hiking plans"},
    "Marrakech, Morocco": {"level": "Level 2 – Increased Caution", "notes": "Petty theft; persistent touts in the medina; dress modestly"},
    "Costa Rica": {"level": "Level 1 – Normal Precautions", "notes": "Petty theft in San José; tourist areas are generally safe"},
    "Serengeti, Tanzania": {"level": "Level 1 – Normal Precautions", "notes": "Use licensed operators only; malaria prophylaxis recommended"},
    "Patagonia, Argentina": {"level": "Level 1 – Normal Precautions", "notes": "Extreme and sudden weather changes—carry storm gear at all times"},
    "Istanbul, Turkey": {"level": "Level 2 – Increased Caution", "notes": "Terrorism risk exists; avoid political gatherings and large crowds"},
    "Rome, Italy": {"level": "Level 1 – Normal Precautions", "notes": "Pickpockets on public transport; keep bags in front"},
    "Maldives": {"level": "Level 1 – Normal Precautions", "notes": "Very safe on resort islands; follow reef safety guidelines"},
}


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@mcp.tool()
def search_destinations(travel_style: str, max_daily_budget_usd: int = 999) -> list[dict]:
    """
    Search for travel destinations that match a travel style and daily budget.

    Args:
        travel_style: Preferred travel type. Accepted values: beach, adventure, culture, nature.
                      Common synonyms are mapped automatically (e.g. hiking → adventure).
        max_daily_budget_usd: Upper limit for daily spend per person in USD (default: no limit).

    Returns:
        List of matching destinations, each with name, highlight, and estimated daily budget.
    """
    style = travel_style.lower().strip()
    synonyms = {
        "hiking": "adventure", "outdoor": "adventure", "sports": "adventure", "extreme": "adventure",
        "history": "culture", "art": "culture", "heritage": "culture", "food": "culture",
        "ocean": "beach", "sea": "beach", "island": "beach", "sun": "beach", "relax": "beach",
        "wildlife": "nature", "eco": "nature", "jungle": "nature", "safari": "nature", "forest": "nature",
    }
    style = synonyms.get(style, style)

    candidates = _DESTINATIONS.get(style, [])
    filtered = [d for d in candidates if d["daily_budget_usd"] <= max_daily_budget_usd]
    return filtered if filtered else candidates


@mcp.tool()
def get_weather_info(destination: str) -> dict:
    """
    Return typical climate data and the best months to visit a destination.

    Args:
        destination: Full destination name, e.g. "Kyoto, Japan" or "Iceland".

    Returns:
        best_months, typical peak temperature (°C), and seasonal travel notes.
    """
    dest_lower = destination.lower()
    for key, data in _WEATHER.items():
        if dest_lower in key.lower() or key.lower() in dest_lower:
            return {"destination": key, **data}
    return {
        "destination": destination,
        "best_months": "Year-round",
        "peak_temp_c": "20–28",
        "notes": "No specific climate data found; check a local forecast before travelling.",
    }


@mcp.tool()
def get_currency_info(country: str) -> dict:
    """
    Return currency details and practical money tips for a destination country.

    Args:
        country: Country name, e.g. "Japan" or "Indonesia".

    Returns:
        Currency code, approximate units per 1 USD, and a practical money tip.
    """
    country_lower = country.lower()
    for key, data in _CURRENCIES.items():
        if country_lower in key.lower() or key.lower() in country_lower:
            return {"country": key, **data}
    return {
        "country": country,
        "code": "Local currency",
        "approx_usd_rate": "See xe.com for live rates",
        "tip": "Notify your bank before departure; use ATMs for the best exchange rate.",
    }


@mcp.tool()
def get_travel_advisory(destination: str) -> dict:
    """
    Return the safety advisory level and key notes for a travel destination.

    Args:
        destination: Destination name, e.g. "Istanbul, Turkey".

    Returns:
        Advisory level and concise safety notes.
    """
    dest_lower = destination.lower()
    for key, data in _ADVISORIES.items():
        if dest_lower in key.lower() or key.lower() in dest_lower:
            return {"destination": key, **data}
    return {
        "destination": destination,
        "level": "Level 1 – Normal Precautions",
        "notes": "No specific advisory found; check your government's official travel page before departing.",
    }


@mcp.tool()
def estimate_trip_cost(destination: str, duration_days: int, travel_class: str = "mid-range") -> dict:
    """
    Produce an itemised cost estimate (USD) for a trip to the given destination.

    Args:
        destination: Destination name, e.g. "Bali, Indonesia".
        duration_days: Number of nights / full days for the trip.
        travel_class: Spending tier — "budget", "mid-range", or "luxury".

    Returns:
        Breakdown of estimated costs (flights, accommodation, food, activities, misc) and totals.
    """
    # Find the base daily budget from destination data
    base_daily = 100  # fallback mid-range default
    for style_list in _DESTINATIONS.values():
        for dest in style_list:
            if destination.lower() in dest["name"].lower():
                base_daily = dest["daily_budget_usd"]
                break

    tier_mult = {"budget": 0.55, "mid-range": 1.0, "luxury": 2.6}.get(travel_class.lower(), 1.0)
    daily = base_daily * tier_mult

    accommodation   = round(daily * 0.40 * duration_days)
    food            = round(daily * 0.25 * duration_days)
    activities      = round(daily * 0.20 * duration_days)
    misc            = round(daily * 0.15 * duration_days)
    # Rough long-haul round-trip flight estimate by price tier
    flights = round(500 if base_daily < 70 else (900 if base_daily < 150 else 1300))

    total = accommodation + food + activities + misc + flights

    return {
        "destination": destination,
        "duration_days": duration_days,
        "travel_class": travel_class,
        "breakdown_usd": {
            "flights_roundtrip": flights,
            "accommodation":     accommodation,
            "food_and_dining":   food,
            "activities":        activities,
            "miscellaneous":     misc,
        },
        "total_usd":    total,
        "per_day_avg":  round(total / duration_days),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
