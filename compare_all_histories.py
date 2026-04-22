import argparse
import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from brvm_package.scraper.richbourse import RichbourseClient
from brvm_package.scraper.sikafinance import SIKA_TICKER_MAP, SikaFinanceClient


DEFAULT_OUTPUT = Path("history_comparison_report.json")
DATE_FORMAT = "%d/%m/%Y"
SAMPLE_START_DATE = "2025-01-01"


@dataclass
class NormalizedRow:
    date: str
    close: float | None
    volume: int | None
    raw: dict[str, Any]


@dataclass
class SourceSnapshot:
    source: str
    elapsed_seconds: float
    total_rows: int
    normalized_rows: int
    first_date: str | None
    last_date: str | None
    sample_keys: list[str]
    fetch_error: str | None = None


@dataclass
class ComparisonReport:
    symbol: str
    overlap_days: int
    sika_only_days: int
    rich_only_days: int
    close_match_ratio: float | None
    volume_match_ratio: float | None
    max_close_gap: float | None
    recommended_source: str
    recommendation_reason: str
    sika: SourceSnapshot
    richbourse: SourceSnapshot
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare les historiques journaliers SikaFinance et RichBourse."
    )
    parser.add_argument(
        "--symbols",
        nargs="*",
        help="Liste explicite de symboles BRVM à comparer. Par défaut: tous les tickers connus.",
    )
    parser.add_argument(
        "--start-date",
        default=SAMPLE_START_DATE,
        help="Date de début pour SikaFinance au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Date de fin pour SikaFinance au format YYYY-MM-DD.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Nombre maximal de symboles traités en parallèle.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Chemin du rapport JSON généré.",
    )
    parser.add_argument(
        "--min-overlap",
        type=int,
        default=20,
        help="Nombre minimal de jours communs avant de recommander la source la plus rapide.",
    )
    parser.add_argument(
        "--close-threshold",
        type=float,
        default=0.98,
        help="Taux minimal de correspondance des clôtures pour considérer les sources conformes.",
    )
    return parser.parse_args()


def normalize_numeric(value: Any) -> float | None:
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


def normalize_int(value: Any) -> int | None:
    number = normalize_numeric(value)
    if number is None:
        return None
    return int(number)


def find_first_key(row: dict[str, Any], candidates: tuple[str, ...]) -> Any:
    lowered = {key.lower(): key for key in row}
    for candidate in candidates:
        exact = lowered.get(candidate.lower())
        if exact is not None:
            return row[exact]
    return None


def normalize_date(raw_date: Any) -> str | None:
    if raw_date is None:
        return None

    text = str(raw_date).strip()
    if not text:
        return None

    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).strftime(DATE_FORMAT)
        except ValueError:
            continue
    return None


def normalize_row(row: dict[str, Any]) -> NormalizedRow | None:
    date_value = find_first_key(row, ("Date", "date", "DateCours", "jour"))
    normalized_date = normalize_date(date_value)
    if normalized_date is None:
        return None

    close_value = find_first_key(
        row,
        ("close", "close_price", "Close", "Cours", "CoursCloture", "Dernier", "Valeur"),
    )
    volume_value = find_first_key(row, ("volume", "Volume", "Quantite", "Vol"))

    return NormalizedRow(
        date=normalized_date,
        close=normalize_numeric(close_value),
        volume=normalize_int(volume_value),
        raw=row,
    )


def build_snapshot(
    source: str,
    elapsed_seconds: float,
    rows: list[dict[str, Any]],
    fetch_error: str | None = None,
) -> tuple[SourceSnapshot, dict[str, NormalizedRow]]:
    normalized_rows: dict[str, NormalizedRow] = {}
    for row in rows:
        normalized = normalize_row(row)
        if normalized is not None:
            normalized_rows[normalized.date] = normalized

    ordered_dates = sorted(
        normalized_rows,
        key=lambda value: datetime.strptime(value, DATE_FORMAT),
    )

    snapshot = SourceSnapshot(
        source=source,
        elapsed_seconds=elapsed_seconds,
        total_rows=len(rows),
        normalized_rows=len(normalized_rows),
        first_date=ordered_dates[0] if ordered_dates else None,
        last_date=ordered_dates[-1] if ordered_dates else None,
        sample_keys=sorted(rows[0].keys()) if rows else [],
        fetch_error=fetch_error,
    )
    return snapshot, normalized_rows


def close_enough(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) < 0.01


def compute_report(
    symbol: str,
    sika_snapshot: SourceSnapshot,
    rich_snapshot: SourceSnapshot,
    sika_rows: dict[str, NormalizedRow],
    rich_rows: dict[str, NormalizedRow],
    min_overlap: int,
    close_threshold: float,
) -> ComparisonReport:
    sika_dates = set(sika_rows)
    rich_dates = set(rich_rows)
    overlap_dates = sorted(
        sika_dates & rich_dates,
        key=lambda value: datetime.strptime(value, DATE_FORMAT),
    )

    close_matches = 0
    close_comparable = 0
    volume_matches = 0
    volume_comparable = 0
    max_close_gap = 0.0

    for day in overlap_dates:
        sika_row = sika_rows[day]
        rich_row = rich_rows[day]

        if sika_row.close is not None and rich_row.close is not None:
            close_comparable += 1
            gap = abs(sika_row.close - rich_row.close)
            max_close_gap = max(max_close_gap, gap)
            if close_enough(sika_row.close, rich_row.close):
                close_matches += 1

        if sika_row.volume is not None and rich_row.volume is not None:
            volume_comparable += 1
            if sika_row.volume == rich_row.volume:
                volume_matches += 1

    close_match_ratio = (
        close_matches / close_comparable if close_comparable > 0 else None
    )
    volume_match_ratio = (
        volume_matches / volume_comparable if volume_comparable > 0 else None
    )

    recommended_source = "undetermined"
    recommendation_reason = "Aucune source exploitable."

    if sika_snapshot.fetch_error and rich_snapshot.fetch_error:
        recommended_source = "undetermined"
        recommendation_reason = "Les deux sources ont echoue pendant la recuperation."
    elif sika_snapshot.fetch_error and rich_snapshot.normalized_rows > 0:
        recommended_source = "richbourse"
        recommendation_reason = "SikaFinance a echoue, RichBourse a renvoye des donnees."
    elif rich_snapshot.fetch_error and sika_snapshot.normalized_rows > 0:
        recommended_source = "sikafinance"
        recommendation_reason = "RichBourse a echoue, SikaFinance a renvoye des donnees."
    elif sika_snapshot.normalized_rows == 0 and rich_snapshot.normalized_rows == 0:
        recommended_source = "undetermined"
        recommendation_reason = "Aucune des deux sources n'a renvoye de donnees comparables."
    elif sika_snapshot.normalized_rows == 0 and rich_snapshot.normalized_rows > 0:
        recommended_source = "richbourse"
        recommendation_reason = "RichBourse renvoie des données alors que SikaFinance est vide."
    elif rich_snapshot.normalized_rows == 0 and sika_snapshot.normalized_rows > 0:
        recommended_source = "sikafinance"
        recommendation_reason = "SikaFinance renvoie des données alors que RichBourse est vide."
    elif close_match_ratio is not None and close_match_ratio >= close_threshold and len(overlap_dates) >= min_overlap:
        if sika_snapshot.elapsed_seconds <= rich_snapshot.elapsed_seconds:
            recommended_source = "sikafinance"
            recommendation_reason = "Sources conformes sur les clôtures, SikaFinance est plus rapide."
        else:
            recommended_source = "richbourse"
            recommendation_reason = "Sources conformes sur les clôtures, RichBourse est plus rapide."
    elif sika_snapshot.normalized_rows > rich_snapshot.normalized_rows:
        recommended_source = "sikafinance"
        recommendation_reason = "SikaFinance couvre plus de jours, mais la conformité doit être revue."
    elif rich_snapshot.normalized_rows > sika_snapshot.normalized_rows:
        recommended_source = "richbourse"
        recommendation_reason = "RichBourse couvre plus de jours, mais la conformité doit être revue."
    elif sika_snapshot.elapsed_seconds <= rich_snapshot.elapsed_seconds:
        recommended_source = "sikafinance"
        recommendation_reason = "Couverture proche, SikaFinance est légèrement plus rapide."
    else:
        recommended_source = "richbourse"
        recommendation_reason = "Couverture proche, RichBourse est légèrement plus rapide."

    return ComparisonReport(
        symbol=symbol,
        overlap_days=len(overlap_dates),
        sika_only_days=len(sika_dates - rich_dates),
        rich_only_days=len(rich_dates - sika_dates),
        close_match_ratio=close_match_ratio,
        volume_match_ratio=volume_match_ratio,
        max_close_gap=max_close_gap if close_comparable > 0 else None,
        recommended_source=recommended_source,
        recommendation_reason=recommendation_reason,
        sika=sika_snapshot,
        richbourse=rich_snapshot,
        error=None,
    )


async def timed_fetch(
    label: str,
    func: Any,
    *args: Any,
) -> tuple[str, float, list[dict[str, Any]], str | None]:
    start = time.perf_counter()
    try:
        rows = await func(*args)
        elapsed = time.perf_counter() - start
        return label, elapsed, rows, None
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return label, elapsed, [], str(exc)


async def compare_symbol(
    symbol: str,
    start_date: str,
    end_date: str,
    min_overlap: int,
    close_threshold: float,
) -> ComparisonReport:
    sika_client = SikaFinanceClient()
    rich_client = RichbourseClient()

    sika_task = timed_fetch(
        "sikafinance",
        sika_client.get_historical_data,
        symbol,
        start_date,
        end_date,
        0,
    )
    rich_task = timed_fetch("richbourse", rich_client.get_historical_prices, symbol)

    sika_result, rich_result = await asyncio.gather(sika_task, rich_task, return_exceptions=False)

    _, sika_elapsed, sika_rows_raw, sika_error = sika_result
    _, rich_elapsed, rich_rows_raw, rich_error = rich_result

    sika_snapshot, sika_rows = build_snapshot(
        "sikafinance",
        sika_elapsed,
        sika_rows_raw,
        sika_error,
    )
    rich_snapshot, rich_rows = build_snapshot(
        "richbourse",
        rich_elapsed,
        rich_rows_raw,
        rich_error,
    )

    report = compute_report(
        symbol=symbol,
        sika_snapshot=sika_snapshot,
        rich_snapshot=rich_snapshot,
        sika_rows=sika_rows,
        rich_rows=rich_rows,
        min_overlap=min_overlap,
        close_threshold=close_threshold,
    )
    if sika_error or rich_error:
        details = [item for item in (sika_error, rich_error) if item]
        report.error = " | ".join(details)
    return report


async def run_comparison(args: argparse.Namespace) -> list[ComparisonReport]:
    symbols = args.symbols or [
        symbol for symbol in sorted(SIKA_TICKER_MAP) if not symbol.startswith("BRVM")
    ]
    semaphore = asyncio.Semaphore(args.concurrency)
    reports: list[ComparisonReport] = []

    async def worker(symbol: str) -> None:
        async with semaphore:
            report = await compare_symbol(
                symbol=symbol,
                start_date=args.start_date,
                end_date=args.end_date,
                min_overlap=args.min_overlap,
                close_threshold=args.close_threshold,
            )
            reports.append(report)
            if report.error:
                print(f"{symbol:>6} | error={report.error}")
                return

            print(
                f"{symbol:>6} | overlap={report.overlap_days:>4} | "
                f"close_match={format_ratio(report.close_match_ratio):>7} | "
                f"winner={report.recommended_source}"
            )

    await asyncio.gather(*(worker(symbol) for symbol in symbols))
    reports.sort(key=lambda report: report.symbol)
    return reports


def format_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.1%}"


def summarize(reports: list[ComparisonReport]) -> dict[str, Any]:
    winners = {"sikafinance": 0, "richbourse": 0, "undetermined": 0}
    for report in reports:
        winners[report.recommended_source] = winners.get(report.recommended_source, 0) + 1

    conforming = [
        report
        for report in reports
        if report.close_match_ratio is not None and report.close_match_ratio >= 0.98
    ]
    failures = [report for report in reports if report.error]

    return {
        "generated_at": datetime.now().isoformat(),
        "symbols_compared": len(reports),
        "recommended_sources": winners,
        "conforming_symbols": len(conforming),
        "failed_symbols": len(failures),
    }


def save_report(path: Path, reports: list[ComparisonReport]) -> None:
    payload = {
        "summary": summarize(reports),
        "reports": [asdict(report) for report in reports],
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")


def main() -> None:
    args = parse_args()
    reports = asyncio.run(run_comparison(args))
    output_path = Path(args.output)
    save_report(output_path, reports)
    summary = summarize(reports)

    print("\nResume")
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    print(f"\nRapport ecrit dans {output_path}")


if __name__ == "__main__":
    main()
