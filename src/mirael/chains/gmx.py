"""
GMX V2 on Arbitrum — read-only reader.

Uses the GMX REST stats API (no Web3 required).
Implements the ``OnchainReader`` Protocol.

GMX V2 Arbitrum:
  Stats API: https://arbitrum-api.gmxinfra.io
  DataStore: 0xFD70de6b91282D8017aA4E741e9Ae325CAb992d
  Docs: https://gmx-docs.io/docs/api/rest/

Usage::
    async with GMXReader() as reader:
        positions = await reader.get_user_positions("0xWALLET")
        balance = await reader.get_user_balance("0xWALLET")
"""

from __future__ import annotations

from typing import Any

import httpx

from mirael.exceptions import ChainConnectionError, ChainDataError
from mirael.logging import get_logger

_log = get_logger(__name__)

_GMX_API = "https://arbitrum-api.gmxinfra.io"
_RETRY_COUNT = 3


class GMXReader:
    """
    Read-only GMX V2 client for Arbitrum mainnet.

    Satisfies the ``OnchainReader`` Protocol.

    Reads open perpetual positions, PnL, funding rates, and market
    info from GMX V2 on Arbitrum via the public REST stats API.

    Args:
        api_base: GMX stats API base URL.
        timeout: Per-request timeout in seconds.
    """

    def __init__(
        self,
        api_base: str = _GMX_API,
        *,
        timeout: float = 15.0,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=api_base,
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> GMXReader:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _get(self, path: str, params: dict[str, str] | None = None) -> Any:  # noqa: ANN401
        """GET with basic retry on transient errors."""
        last_exc: BaseException = RuntimeError("no attempts")
        for attempt in range(_RETRY_COUNT):
            try:
                resp = await self._http.get(path, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                raise ChainConnectionError(
                    f"GMX API HTTP {exc.response.status_code}: {path}",
                    code="CHAIN_HTTP_ERROR",
                ) from exc
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                import asyncio
                last_exc = exc
                await asyncio.sleep(2**attempt)
        raise ChainConnectionError(
            f"GMX API unreachable after {_RETRY_COUNT} attempts: {last_exc}",
            code="CHAIN_CONNECTION",
        )

    # ── Public API (OnchainReader Protocol) ───────────────────────────────────

    async def get_user_positions(self, wallet: str) -> list[dict[str, Any]]:
        """
        Return open GMX V2 perpetual positions for a wallet.

        Returns:
            List of dicts with keys: asset, size_usd, entry_price,
            mark_price, unrealized_pnl, is_long, leverage, collateral_usd.
        """
        try:
            data = await self._get("/positions", params={"account": wallet})
        except Exception as exc:
            if isinstance(exc, ChainConnectionError):
                raise
            raise ChainDataError(f"Failed to fetch GMX positions: {exc}") from exc

        positions: list[dict[str, Any]] = []
        for p in data if isinstance(data, list) else data.get("positions", []):
            # Normalise GMX V2 position schema
            market = str(p.get("market", p.get("indexToken", "?")))
            # Strip address suffix if present — keep symbol
            symbol = market.split(":")[-1] if ":" in market else market
            size_usd = float(p.get("sizeInUsd", p.get("size", 0))) / 1e30
            if size_usd < 1:
                continue

            collateral = float(p.get("collateralAmount", p.get("collateral", 0))) / 1e6
            entry_price = float(p.get("entryPrice", p.get("averagePrice", 0))) / 1e30
            mark_price = float(p.get("markPrice", entry_price)) / 1e30
            is_long = bool(p.get("isLong", True))
            leverage = size_usd / collateral if collateral > 0 else 0.0
            pnl = (
                (mark_price - entry_price) / entry_price * size_usd * (1 if is_long else -1)
                if entry_price > 0
                else 0.0
            )

            positions.append({
                "asset": symbol,
                "size_usd": size_usd,
                "entry_price": entry_price,
                "mark_price": mark_price,
                "unrealized_pnl": pnl,
                "is_long": is_long,
                "leverage": round(leverage, 2),
                "collateral_usd": collateral,
            })

        _log.debug("gmx_positions_fetched", wallet=wallet[:10], count=len(positions))
        return positions

    async def get_user_balance(self, wallet: str) -> dict[str, Any]:
        """
        Return GMX V2 account summary for a wallet.

        Returns total collateral, unrealized PnL, and a synthetic
        health factor (collateral / (size / max_leverage)).
        """
        positions = await self.get_user_positions(wallet)

        total_collateral = sum(p["collateral_usd"] for p in positions)
        total_size = sum(p["size_usd"] for p in positions)
        total_pnl = sum(p["unrealized_pnl"] for p in positions)

        # Synthetic health factor: equity / (total_size * maintenance_margin_rate)
        # GMX V2 maintenance margin ~0.5-1% — use 1% as conservative estimate
        maintenance = total_size * 0.01
        health = (total_collateral + total_pnl) / maintenance if maintenance > 0 else 999.0

        _log.debug("gmx_balance_fetched", wallet=wallet[:10], collateral=total_collateral)
        return {
            "total_collateral_usd": total_collateral,
            "total_size_usd": total_size,
            "unrealized_pnl": total_pnl,
            "health_factor": min(health, 999.0),
            "free_margin": max(0.0, total_collateral + total_pnl),
        }

    async def get_recent_trades(
        self, wallet: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Return recent GMX trades for a wallet (best-effort via stats API)."""
        try:
            data = await self._get("/trades", params={"account": wallet, "pageSize": str(limit)})
        except ChainConnectionError:
            _log.warning("gmx_trades_unavailable", wallet=wallet[:10])
            return []

        trades = [
            {
                "asset": str(t.get("indexToken", "?")),
                "side": "buy" if t.get("isLong") else "sell",
                "size": float(t.get("sizeDelta", 0)) / 1e30,
                "price": float(t.get("price", 0)) / 1e30,
                "fee": float(t.get("fee", 0)) / 1e30,
                "realized_pnl": float(t.get("realisedPnl", 0)) / 1e30,
                "timestamp_ms": int(t.get("timestamp", 0)) * 1000,
            }
            for t in (data if isinstance(data, list) else data.get("trades", []))
        ]
        return trades[:limit]

    async def get_funding_rate(self, asset: str) -> dict[str, Any]:
        """
        Return current funding rate for a GMX V2 perpetual market.

        Args:
            asset: Asset symbol, e.g. ``"BTC"``, ``"ETH"``, ``"ARB"``.
        """
        tickers = await self._get("/prices/tickers")
        target = asset.upper()

        for ticker in tickers if isinstance(tickers, list) else []:
            token_symbol = str(ticker.get("tokenSymbol", ""))
            if token_symbol.upper() == target:
                # GMX V2 uses borrow rate (not funding) — expressed per hour
                borrow_rate = float(ticker.get("fundingRate", ticker.get("borrowingRate", 0)))
                return {
                    "asset": target,
                    "rate": borrow_rate,
                    "annualized": borrow_rate * 24 * 365,
                    "open_interest": float(ticker.get("openInterest", 0)),
                    "mark_price": float(ticker.get("markPrice", ticker.get("midPrice", 0))) / 1e30,
                    "oracle_price": float(ticker.get("indexPrice", 0)) / 1e30,
                }

        raise ChainDataError(
            f"Asset '{asset}' not found in GMX V2 Arbitrum markets",
            code="CHAIN_DATA",
        )

    async def get_market_info(self, asset: str) -> dict[str, Any]:
        """
        Return GMX V2 market metadata for an asset.

        Args:
            asset: Asset symbol, e.g. ``"BTC"`` or ``"ETH"``.
        """
        markets = await self._get("/markets")
        target = asset.upper()

        for m in markets if isinstance(markets, list) else markets.get("markets", []):
            symbol = str(m.get("indexToken", {}).get("symbol", m.get("name", "")))
            if target in symbol.upper():
                long_oi = float(m.get("longInterestUsd", 0)) / 1e30
                short_oi = float(m.get("shortInterestUsd", 0)) / 1e30
                return {
                    "asset": target,
                    "mark_price": float(m.get("markPrice", 0)) / 1e30,
                    "oracle_price": float(m.get("indexPrice", 0)) / 1e30,
                    "mid_price": None,
                    "open_interest": long_oi + short_oi,
                    "long_open_interest": long_oi,
                    "short_open_interest": short_oi,
                    "funding_rate": float(m.get("fundingRate", 0)),
                    "max_leverage": 100,  # GMX V2 supports up to 100x
                    "protocol": "GMX V2",
                    "chain": "Arbitrum",
                }

        raise ChainDataError(
            f"Asset '{asset}' not found in GMX V2 markets",
            code="CHAIN_DATA",
        )


def create_from_settings(settings: Any) -> GMXReader:  # noqa: ANN401
    """Factory: build a ``GMXReader`` from a ``MiraelSettings`` instance."""
    return GMXReader()
