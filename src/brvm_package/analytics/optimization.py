from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class OptimizationResult:
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe: float
    method: str


def optimize_portfolio(
    returns_frame: pd.DataFrame,
    method: str = "markowitz",
    risk_free_rate: float = 0.02,
    simulations: int = 5000,
    seed: int = 42,
) -> OptimizationResult:
    clean = returns_frame.dropna(how="all")
    if clean.empty:
        return OptimizationResult(weights={}, expected_return=0.0, volatility=0.0, sharpe=0.0, method=method)

    clean = clean.dropna(axis=1, how="all").fillna(0.0)
    tickers = list(clean.columns)
    rng = np.random.default_rng(seed)
    annual_returns = clean.mean().to_numpy() * 252
    annual_cov = clean.cov().to_numpy() * 252

    best_weights: np.ndarray | None = None
    best_return = 0.0
    best_vol = 0.0
    best_score = None

    candidates = [np.repeat(1 / len(tickers), len(tickers))]
    for i in range(len(tickers)):
        unit = np.zeros(len(tickers))
        unit[i] = 1.0
        candidates.append(unit)
    candidates.extend(_random_weights(rng, len(tickers), simulations))

    for weights in candidates:
        port_return = float(weights @ annual_returns)
        port_vol = float(np.sqrt(weights @ annual_cov @ weights))
        sharpe = (port_return - risk_free_rate) / port_vol if port_vol else 0.0

        score = sharpe if method == "markowitz" else -port_vol
        if best_score is None or score > best_score:
            best_score = score
            best_weights = weights.copy()
            best_return = port_return
            best_vol = port_vol

    assert best_weights is not None
    best_sharpe = (best_return - risk_free_rate) / best_vol if best_vol else 0.0
    return OptimizationResult(
        weights={ticker: float(weight) for ticker, weight in zip(tickers, best_weights)},
        expected_return=best_return,
        volatility=best_vol,
        sharpe=best_sharpe,
        method=method,
    )


def efficient_frontier(
    returns_frame: pd.DataFrame,
    points: int = 25,
    simulations: int = 5000,
    seed: int = 42,
) -> pd.DataFrame:
    clean = returns_frame.dropna(axis=1, how="all").fillna(0.0)
    if clean.empty:
        return pd.DataFrame(columns=["return", "volatility", "sharpe"])

    rng = np.random.default_rng(seed)
    annual_returns = clean.mean().to_numpy() * 252
    annual_cov = clean.cov().to_numpy() * 252

    rows: list[dict[str, float]] = []
    for weights in _random_weights(rng, len(clean.columns), simulations):
        port_return = float(weights @ annual_returns)
        port_vol = float(np.sqrt(weights @ annual_cov @ weights))
        sharpe = port_return / port_vol if port_vol else 0.0
        rows.append({"return": port_return, "volatility": port_vol, "sharpe": sharpe})

    frontier = pd.DataFrame(rows).sort_values("volatility").reset_index(drop=True)
    if len(frontier) <= points:
        return frontier
    indices = np.linspace(0, len(frontier) - 1, points, dtype=int)
    return frontier.iloc[indices].reset_index(drop=True)


def _random_weights(rng: np.random.Generator, size: int, simulations: int) -> list[np.ndarray]:
    samples = rng.random((simulations, size))
    samples = samples / samples.sum(axis=1, keepdims=True)
    return [row for row in samples]
