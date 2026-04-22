from __future__ import annotations

import httpx
import pandas as pd

FCFA_EXCHANGE_REFERENCE = [
    {"currency": "EUR", "code": "EUR/XOF", "xof_per_unit": 655.957, "unit_per_xof": 1 / 655.957, "source": "fixed_peg", "as_of": "1999-01-01"},
    {"currency": "USD", "code": "USD/XOF", "xof_per_unit": 605.0, "unit_per_xof": 1 / 605.0, "source": "static_reference", "as_of": "2026-01-01"},
    {"currency": "GBP", "code": "GBP/XOF", "xof_per_unit": 780.0, "unit_per_xof": 1 / 780.0, "source": "static_reference", "as_of": "2026-01-01"},
    {"currency": "NGN", "code": "NGN/XOF", "xof_per_unit": 0.41, "unit_per_xof": 1 / 0.41, "source": "static_reference", "as_of": "2026-01-01"},
    {"currency": "GHS", "code": "GHS/XOF", "xof_per_unit": 41.5, "unit_per_xof": 1 / 41.5, "source": "static_reference", "as_of": "2026-01-01"},
]

UEMOA_INFLATION_REFERENCE = [
    {"date": "2021-12-31", "inflation": 3.6, "source": "static_reference"},
    {"date": "2022-12-31", "inflation": 7.4, "source": "static_reference"},
    {"date": "2023-12-31", "inflation": 3.7, "source": "static_reference"},
    {"date": "2024-12-31", "inflation": 2.9, "source": "static_reference"},
    {"date": "2025-12-31", "inflation": 2.6, "source": "static_reference"},
]

MACRO_EVENTS_REFERENCE = [
    {"date": "2024-03-06", "event": "BCEAO rate decision", "category": "Monetary Policy", "region": "UEMOA", "source": "static_reference"},
    {"date": "2024-09-04", "event": "BCEAO rate decision", "category": "Monetary Policy", "region": "UEMOA", "source": "static_reference"},
    {"date": "2025-03-05", "event": "BCEAO rate decision", "category": "Monetary Policy", "region": "UEMOA", "source": "static_reference"},
    {"date": "2025-09-03", "event": "BCEAO rate decision", "category": "Monetary Policy", "region": "UEMOA", "source": "static_reference"},
]


def get_fcfa_exchange_rates() -> pd.DataFrame:
    live = _fetch_live_exchange_rates()
    if live is not None and not live.empty:
        return live
    return pd.DataFrame(FCFA_EXCHANGE_REFERENCE)


def get_macro_events() -> pd.DataFrame:
    return pd.DataFrame(MACRO_EVENTS_REFERENCE)


def get_inflation_series() -> pd.DataFrame:
    frame = pd.DataFrame(UEMOA_INFLATION_REFERENCE)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


def _fetch_live_exchange_rates() -> pd.DataFrame | None:
    try:
        eur_base = _fetch_frankfurter_rates("EUR", ["USD", "GBP", "NGN", "GHS"])
        if eur_base is None:
            return None

        as_of = eur_base["date"]
        rates = eur_base["rates"]
        eur_xof = 655.957

        records = [
            {
                "currency": "EUR",
                "code": "EUR/XOF",
                "xof_per_unit": eur_xof,
                "unit_per_xof": 1 / eur_xof,
                "source": "ecb_peg",
                "as_of": as_of,
            }
        ]
        for currency in ["USD", "GBP", "NGN", "GHS"]:
            eur_per_unit = _safe_float(rates.get(currency))
            if eur_per_unit is None or eur_per_unit <= 0:
                continue
            xof_per_unit = eur_xof / eur_per_unit
            records.append(
                {
                    "currency": currency,
                    "code": f"{currency}/XOF",
                    "xof_per_unit": xof_per_unit,
                    "unit_per_xof": 1 / xof_per_unit,
                    "source": "frankfurter_live",
                    "as_of": as_of,
                }
            )

        return pd.DataFrame(records)
    except Exception:
        return None


def _fetch_frankfurter_rates(base: str, symbols: list[str]) -> dict | None:
    url = "https://api.frankfurter.app/latest"
    with httpx.Client(timeout=1.5, follow_redirects=True) as client:
        response = client.get(url, params={"from": base, "to": ",".join(symbols)})
        response.raise_for_status()
        payload = response.json()
    if "rates" not in payload:
        return None
    return payload


def _safe_float(value: object) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
