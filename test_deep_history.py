import asyncio
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from brvm_package.scraper.richbourse import RichbourseClient
from brvm_package.scraper.sikafinance import SikaFinanceClient

SYMBOLS = ["SNTS", "SGBC", "BOAB", "CABC", "CIEC", "ONEC", "SIVC", "TTRC"]
START_DATE = "2024-01-01"
CLOSE_TOLERANCE = 1.0
SLEEP_BETWEEN_SYMBOLS = 1.0
DATE_FORMAT = "%Y-%m-%d"


@dataclass
class FetchResult:
    rows: list[dict[str, Any]]
    elapsed_seconds: float
    error: str | None


def normalize_date(date_str: Any) -> str | None:
    if date_str is None:
        return None

    text = str(date_str).strip()
    if not text:
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime(DATE_FORMAT)
        except ValueError:
            continue
    return None


def normalize_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text or text in {"-", "--", "N/A", "null"}:
        return None

    cleaned = (
        text.replace("\xa0", "")
        .replace(" ", "")
        .replace("FCFA", "")
        .replace("XOF", "")
        .replace("%", "")
    )

    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")

    try:
        return float(cleaned)
    except ValueError:
        return None


def find_first_value(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    lowered = {key.lower(): key for key in row}
    for candidate in candidates:
        key = lowered.get(candidate.lower())
        if key is not None:
            return row[key]
    return None


def normalize_history(
    rows: list[dict[str, Any]],
    start_date: str,
    end_date: str,
) -> dict[str, float]:
    start_bound = datetime.strptime(start_date, DATE_FORMAT).date()
    end_bound = datetime.strptime(end_date, DATE_FORMAT).date()
    normalized: dict[str, float] = {}

    for row in rows:
        normalized_date = normalize_date(
            find_first_value(row, ("Date", "date", "DateCours", "jour"))
        )
        if normalized_date is None:
            continue

        current_date = datetime.strptime(normalized_date, DATE_FORMAT).date()
        if current_date < start_bound or current_date > end_bound:
            continue

        close_price = normalize_float(
            find_first_value(
                row,
                ("Cloture", "Clôture", "close", "Close", "CoursCloture", "Dernier", "Valeur"),
            )
        )
        if close_price is None:
            continue

        normalized[normalized_date] = close_price

    return normalized


async def timed_fetch(coro: Any) -> FetchResult:
    start = time.perf_counter()
    try:
        rows = await coro
        return FetchResult(rows=rows, elapsed_seconds=time.perf_counter() - start, error=None)
    except Exception as exc:
        return FetchResult(rows=[], elapsed_seconds=time.perf_counter() - start, error=str(exc))


def build_recommendation(
    points_sika: int,
    points_rich: int,
    match_rate: float,
    time_sika: float,
    time_rich: float,
    error_sika: str | None,
    error_rich: str | None,
) -> str:
    if error_sika and error_rich:
        return "Impossible a comparer"
    if error_sika and points_rich > 0:
        return "Richbourse (Sika en erreur)"
    if error_rich and points_sika > 0:
        return "SikaFinance (Rich en erreur)"
    if points_sika == 0 and points_rich == 0:
        return "Aucune source exploitable"
    if match_rate >= 99.0 and points_sika > 0 and points_rich > 0:
        if time_sika <= time_rich:
            return "SikaFinance (Rapide + Conforme)"
        return "Richbourse (Rapide + Conforme)"
    if points_sika > points_rich:
        return "SikaFinance (Plus de donnees)"
    if points_rich > points_sika:
        return "Richbourse (Plus de donnees)"
    if points_sika > 0 and points_rich > 0:
        if time_sika <= time_rich:
            return "SikaFinance (Tie-break vitesse)"
        return "Richbourse (Tie-break vitesse)"
    return "A definir"


async def compare_symbol(
    sika: SikaFinanceClient,
    rich: RichbourseClient,
    symbol: str,
    start_date: str,
    end_date: str,
) -> dict[str, Any]:
    sika_fetch, rich_fetch = await asyncio.gather(
        timed_fetch(sika.get_historical_data(symbol, start_date, end_date, period=0)),
        timed_fetch(rich.get_historical_prices(symbol)),
    )

    dict_sika = normalize_history(sika_fetch.rows, start_date, end_date)
    dict_rich = normalize_history(rich_fetch.rows, start_date, end_date)

    common_dates = sorted(set(dict_sika).intersection(dict_rich))
    matching_prices = 0

    for date in common_dates:
        if abs(dict_sika[date] - dict_rich[date]) <= CLOSE_TOLERANCE:
            matching_prices += 1

    match_rate = (matching_prices / len(common_dates) * 100) if common_dates else 0.0
    fastest = "Sika" if sika_fetch.elapsed_seconds <= rich_fetch.elapsed_seconds else "Richbourse"
    recommended = build_recommendation(
        points_sika=len(dict_sika),
        points_rich=len(dict_rich),
        match_rate=match_rate,
        time_sika=sika_fetch.elapsed_seconds,
        time_rich=rich_fetch.elapsed_seconds,
        error_sika=sika_fetch.error,
        error_rich=rich_fetch.error,
    )

    return {
        "symbol": symbol,
        "points_sika": len(dict_sika),
        "points_rich": len(dict_rich),
        "common_dates": len(common_dates),
        "time_sika": sika_fetch.elapsed_seconds,
        "time_rich": rich_fetch.elapsed_seconds,
        "match_rate": match_rate,
        "fastest": fastest,
        "recommended": recommended,
        "error_sika": sika_fetch.error,
        "error_rich": rich_fetch.error,
    }


async def run_benchmark() -> None:
    sika = SikaFinanceClient()
    rich = RichbourseClient()
    end_date = datetime.now().strftime(DATE_FORMAT)

    print("\nLancement du benchmark global des sources historiques BRVM...")
    print("=" * 136)
    print(
        f"{'Ticker':<8} | {'Pts Sika':<9} | {'Pts Rich':<9} | {'Communs':<8} | "
        f"{'Tps Sika':<9} | {'Tps Rich':<9} | {'Alignement':<12} | {'Reco':<34} | "
        f"{'Etat':<18}"
    )
    print("-" * 136)

    results: list[dict[str, Any]] = []

    for symbol in SYMBOLS:
        result = await compare_symbol(sika, rich, symbol, START_DATE, end_date)
        results.append(result)

        status = "OK"
        if result["error_sika"] and result["error_rich"]:
            status = "2 erreurs"
        elif result["error_sika"]:
            status = "Erreur Sika"
        elif result["error_rich"]:
            status = "Erreur Rich"

        print(
            f"{result['symbol']:<8} | {result['points_sika']:<9} | {result['points_rich']:<9} | "
            f"{result['common_dates']:<8} | {result['time_sika']:<8.2f}s | "
            f"{result['time_rich']:<8.2f}s | {result['match_rate']:>6.1f}%      | "
            f"{result['recommended']:<34} | {status:<18}"
        )

        await asyncio.sleep(SLEEP_BETWEEN_SYMBOLS)

    print("=" * 136)
    print("Resume du benchmark :")

    sika_reco = sum(1 for item in results if item["recommended"].startswith("SikaFinance"))
    rich_reco = sum(1 for item in results if item["recommended"].startswith("Richbourse"))
    failed = sum(1 for item in results if item["error_sika"] or item["error_rich"])

    print(f"- SikaFinance recommandee pour : {sika_reco}/{len(SYMBOLS)} actions")
    print(f"- Richbourse recommandee pour : {rich_reco}/{len(SYMBOLS)} actions")
    print(f"- Symboles avec au moins une erreur de fetch : {failed}/{len(SYMBOLS)}")
    print(
        "\nNote: un faible alignement peut venir d'un parsing different, d'une couverture "
        "historique incomplete, ou d'un vrai ecart entre les sources."
    )


if __name__ == "__main__":
    asyncio.run(run_benchmark())
