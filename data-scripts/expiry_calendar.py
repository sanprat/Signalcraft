"""
expiry_calendar.py — Generate weekly expiry dates & ATM strike ranges for NSE F&O
Handles NIFTY (Thu), BANKNIFTY (Wed), FINNIFTY (Tue) weekly expiries.
Adjusts for NSE trading holidays.
"""

from datetime import date, timedelta
from typing import Generator

# NSE holidays 2024-2026 (adjust/extend as needed)
NSE_HOLIDAYS = {
    date(2024, 1, 22),   # Ram Mandir
    date(2024, 3, 25),   # Holi
    date(2024, 3, 29),   # Good Friday
    date(2024, 4, 14),   # Ambedkar Jayanti / Baisakhi (Sunday — no adjustment needed)
    date(2024, 4, 17),   # Ram Navami
    date(2024, 5, 23),   # Buddha Purnima
    date(2024, 6, 17),   # Eid al-Adha
    date(2024, 7, 17),   # Muharram
    date(2024, 8, 15),   # Independence Day
    date(2024, 10, 2),   # Gandhi Jayanti
    date(2024, 10, 14),  # Dussehra
    date(2024, 11, 1),   # Diwali Laxmi Puja
    date(2024, 11, 15),  # Gurunanak Jayanti
    date(2024, 12, 25),  # Christmas
    date(2025, 2, 26),   # Mahashivratri
    date(2025, 3, 14),   # Holi
    date(2025, 4, 14),   # Dr. Ambedkar Jayanti
    date(2025, 4, 18),   # Good Friday
    date(2025, 5, 12),   # Buddha Purnima
    date(2025, 6, 7),    # Eid al-Adha (tentative)
    date(2025, 8, 15),   # Independence Day
    date(2025, 8, 27),   # Ganesh Chaturthi
    date(2025, 10, 2),   # Gandhi Jayanti
    date(2025, 10, 2),   # Dussehra (same day)
    date(2025, 10, 20),  # Diwali (tentative)
    date(2025, 11, 5),   # Gurunanak Jayanti (tentative)
    date(2025, 12, 25),  # Christmas
    date(2026, 1, 26),   # Republic Day
    date(2026, 2, 23),   # No holiday today — placeholder
}

# Weekday indices: Monday=0 … Sunday=6
EXPIRY_WEEKDAY = {
    "NIFTY":     3,  # Thursday
    "BANKNIFTY": 2,  # Wednesday
    "FINNIFTY":  1,  # Tuesday
}

# Lot sizes (for ATM rounding)
STRIKE_STEP = {
    "NIFTY":     50,
    "BANKNIFTY": 100,
    "FINNIFTY":  50,
}


def _is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in NSE_HOLIDAYS


def _prev_trading_day(d: date) -> date:
    """If d is a holiday/weekend, roll back to the last trading day."""
    while not _is_trading_day(d):
        d -= timedelta(days=1)
    return d


def get_weekly_expiries(index: str, start: date, end: date) -> list[date]:
    """
    Return all weekly expiry dates for `index` between start and end (inclusive).
    Expiry is adjusted to prev trading day if it falls on a holiday.
    """
    target_weekday = EXPIRY_WEEKDAY[index]
    expiries = []

    # Find the first target weekday >= start
    d = start
    days_ahead = (target_weekday - d.weekday()) % 7
    d += timedelta(days=days_ahead)

    while d <= end:
        expiry = _prev_trading_day(d)
        if start <= expiry <= end:
            expiries.append(expiry)
        d += timedelta(weeks=1)

    return sorted(set(expiries))


def get_atm_strikes(spot_price: float, index: str, num_strikes: int = 10) -> list[int]:
    """
    Return ATM ± num_strikes strikes rounded to the index's strike step.
    e.g. spot=22345 → ATM=22350 for NIFTY (step=50) → [21850..22850]
    """
    step = STRIKE_STEP[index]
    atm = round(spot_price / step) * step
    return [atm + (i * step) for i in range(-num_strikes, num_strikes + 1)]


def iter_contracts(
    indices: list[str],
    start: date,
    end: date,
    atm_strikes_by_index: dict[str, list[int]],
    option_types: list[str] = ("CE", "PE"),
) -> Generator[dict, None, None]:
    """
    Yield every (index, expiry, strike, option_type) combination to download.
    Yields: {index, expiry (date), strike (int), option_type (str)}
    """
    for index in indices:
        expiries = get_weekly_expiries(index, start, end)
        strikes = atm_strikes_by_index.get(index, [])
        for expiry in expiries:
            for strike in strikes:
                for opt in option_types:
                    yield {
                        "index": index,
                        "expiry": expiry,
                        "strike": strike,
                        "option_type": opt,
                    }


if __name__ == "__main__":
    # Quick test
    from datetime import date
    start = date(2024, 1, 1)
    end   = date(2026, 2, 23)

    for idx in ["NIFTY", "BANKNIFTY", "FINNIFTY"]:
        expiries = get_weekly_expiries(idx, start, end)
        print(f"{idx}: {len(expiries)} weekly expiries  |  first={expiries[0]}  last={expiries[-1]}")

    strikes = get_atm_strikes(22500, "NIFTY", num_strikes=10)
    print(f"NIFTY sample strikes (ATM=22500): {strikes}")
