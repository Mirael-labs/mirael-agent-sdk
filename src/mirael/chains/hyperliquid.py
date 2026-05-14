"""
Hyperliquid read-only on-chain reader.

Implements the ``OnchainReader`` Protocol via direct async HTTP calls to
the Hyperliquid Info API (no broker SDK dependency at runtime).

All methods return serialised ``dict`` / ``list[dict]`` values to satisfy
the Protocol interface while internally using Pydantic models for
validation.

Example::

    async with HyperliquidReader() as reader:
        balance = await reader.get_user_balance("0xabc123")
        positions = await reader.get_user_positions("0xabc123")
"""

from __future__ import annotations

from typing import Any, Literal

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from mirael.chains.models import (
    BalanceSummary,
    FundingRateInfo,
    MarketInfo,
    PositionSummary,
    TradeRecord,
)
from mirael.exceptions import ChainConnectionError, ChainDataError
from mirael.logging import get_logger

_log = get_logger(__name__)

_MAINNET_URL = "https://api.hyperliquid.xyz"
_TESTNET_URL = "https://api.hyperliquid-testnet.xyz"

_RETRY_ON = (
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)


class HyperliquidReader:
    """
    Async read-only client for the Hyperliquid L1 Info API.

    Satisfies the ``OnchainReader`` Protocol.

    Args:
        network: ``"mainnet"`` (default) or ``"testnet"``.
        timeout: Per-request timeout in seconds.
        max_retries: Maximum retry attempts on transient network errors.
    """

    def __init__(
        self,
        network: Literal["mainnet", "testnet"] = "mainnet",
        *,
        timeout: float = 15.0,
        max_retries: int = 3,
    ) -> None:
        base_url = _MAINNET_URL if network == "mainnet" else _TESTNET_URL
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )
        self._network = network
        self._max_retries = max_retries

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> HyperliquidReader:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    # ── Public API (satisfies OnchainReader Protocol) ─────────────────────────

    async def get_user_positions(self, wallet: str) -> list[dict[str, Any]]:
        """
        Return all open perpetual positions for a wallet address.

        Returns an empty list if the wallet has no open positions.

        Args:
            wallet: Hex wallet address (``0x...``).

        Returns:
            List of dicts with keys: ``asset``, ``size``, ``entry_price``,
            ``mark_price``, ``unrealized_pnl``, ``liquidation_price``,
            ``margin_used``, ``leverage``, ``funding_since_open``.
        """
        data = await self._post({"type": "clearinghouseState", "user": wallet})
        positions = _parse_positions(data)
        _log.debug("hl_positions_fetched", wallet=wallet[:10], count=len(positions))
        return [p.model_dump() for p in positions]

    async def get_user_balance(self, wallet: str) -> dict[str, Any]:
        """
        Return account margin summary for a wallet address.

        Args:
            wallet: Hex wallet address (``0x...``).

        Returns:
            Dict with keys: ``account_value``, ``total_position_notional``,
            ``total_margin_used``, ``free_margin``.
        """
        data = await self._post({"type": "clearinghouseState", "user": wallet})
        balance = _parse_balance(data)
        _log.debug(
            "hl_balance_fetched",
            wallet=wallet[:10],
            account_value=balance.account_value,
        )
        return balance.model_dump()

    async def get_recent_trades(self, wallet: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Return the most recent fills (executed trades) for a wallet.

        Args:
            wallet: Hex wallet address (``0x...``).
            limit: Maximum number of fills to return (applied client-side).

        Returns:
            List of dicts with keys: ``asset``, ``side``, ``size``, ``price``,
            ``fee``, ``realized_pnl``, ``timestamp_ms``.
        """
        data = await self._post({"type": "userFills", "user": wallet})
        if not isinstance(data, list):
            raise ChainDataError(f"Expected list from userFills, got {type(data).__name__}")
        trades = [_parse_fill(fill) for fill in data[:limit]]
        _log.debug("hl_trades_fetched", wallet=wallet[:10], count=len(trades))
        return [t.model_dump() for t in trades]

    async def get_funding_rate(self, asset: str) -> dict[str, Any]:
        """
        Return current funding rate information for a perpetual asset.

        Args:
            asset: Asset symbol (e.g. ``"BTC"``, ``"ETH"``).

        Returns:
            Dict with keys: ``asset``, ``rate``, ``annualized``,
            ``open_interest``, ``mark_price``, ``oracle_price``,
            ``prev_day_price``.

        Raises:
            ChainDataError: If the asset is not found in the universe.
        """
        info = await self._fetch_asset_ctx(asset)
        _log.debug("hl_funding_fetched", asset=asset, rate=info.rate)
        return info.model_dump()

    async def get_market_info(self, asset: str) -> dict[str, Any]:
        """
        Return market metadata for a perpetual asset.

        Args:
            asset: Asset symbol (e.g. ``"BTC"``).

        Returns:
            Dict with keys: ``asset``, ``mark_price``, ``oracle_price``,
            ``mid_price``, ``open_interest``, ``funding_rate``,
            ``max_leverage``, ``prev_day_price``, ``day_notional_volume``.

        Raises:
            ChainDataError: If the asset is not found.
        """
        data = await self._post({"type": "metaAndAssetCtxs"})
        market = _parse_market_info(data, asset)
        _log.debug("hl_market_fetched", asset=asset, mark=market.mark_price)
        return market.model_dump()

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _post(self, payload: dict[str, Any]) -> Any:  # noqa: ANN401
        """POST to /info with exponential back-off retry on transient errors."""
        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(_RETRY_ON),
                wait=wait_exponential(multiplier=1, min=1, max=30),
                stop=stop_after_attempt(self._max_retries),
                reraise=True,
            ):
                with attempt:
                    try:
                        resp = await self._http.post("/info", json=payload)
                        resp.raise_for_status()
                        return resp.json()
                    except httpx.HTTPStatusError as exc:
                        raise ChainConnectionError(
                            f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
                            code="CHAIN_HTTP_ERROR",
                        ) from exc
        except Exception as exc:
            if isinstance(exc, ChainConnectionError):
                raise
            raise ChainConnectionError(
                f"Connection failed after {self._max_retries} attempts: {exc}",
                code="CHAIN_CONNECTION",
            ) from exc
        # unreachable — satisfies mypy
        raise RuntimeError("no attempts made")  # pragma: no cover

    async def _fetch_asset_ctx(self, asset: str) -> FundingRateInfo:
        data = await self._post({"type": "metaAndAssetCtxs"})
        return _parse_funding_rate(data, asset)


# ── Parsing helpers ────────────────────────────────────────────────────────────


def _parse_positions(data: dict[str, Any]) -> list[PositionSummary]:
    results: list[PositionSummary] = []

    for ap in data.get("assetPositions", []):
        p = ap.get("position", {})
        size = float(p.get("szi", 0))
        if size == 0.0:
            continue

        notional = float(p.get("positionValue", 0))
        mark_price = notional / abs(size) if size != 0 else 0.0

        liq_raw = p.get("liquidationPx")
        liq: float | None = float(liq_raw) if liq_raw else None

        leverage_raw = p.get("leverage", {})
        if isinstance(leverage_raw, dict):
            leverage = float(leverage_raw.get("value", 1))
        else:
            leverage = float(leverage_raw or 1)

        cum_funding = p.get("cumFunding", {})
        funding_all_time = float(
            cum_funding.get("allTime", 0) if isinstance(cum_funding, dict) else 0
        )

        results.append(
            PositionSummary(
                asset=str(p.get("coin", "")),
                size=size,
                entry_price=float(p.get("entryPx", 0)),
                mark_price=mark_price,
                unrealized_pnl=float(p.get("unrealizedPnl", 0)),
                liquidation_price=liq,
                margin_used=float(p.get("marginUsed", 0)),
                leverage=leverage,
                funding_since_open=funding_all_time,
            )
        )
    return results


def _parse_balance(data: dict[str, Any]) -> BalanceSummary:
    margin = data.get("marginSummary", {})
    account_value = float(margin.get("accountValue", 0))
    total_margin = float(margin.get("totalMarginUsed", 0))
    return BalanceSummary(
        account_value=account_value,
        total_position_notional=float(margin.get("totalNtlPos", 0)),
        total_margin_used=total_margin,
        free_margin=max(0.0, account_value - total_margin),
    )


def _parse_fill(fill: dict[str, Any]) -> TradeRecord:
    side_raw = str(fill.get("side", "B"))
    side = "buy" if side_raw == "B" else "sell"
    return TradeRecord(
        asset=str(fill.get("coin", "")),
        side=side,
        size=float(fill.get("sz", 0)),
        price=float(fill.get("px", 0)),
        fee=float(fill.get("fee", 0)),
        realized_pnl=float(fill.get("closedPnl", 0)),
        timestamp_ms=int(fill.get("time", 0)),
    )


def _find_asset_pair(
    data: Any,  # noqa: ANN401
    asset: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Extract (meta_entry, ctx_entry) for ``asset`` from ``metaAndAssetCtxs``.

    Raises:
        ChainDataError: If response format is unexpected or asset not found.
    """
    if not isinstance(data, list) or len(data) < 2:
        raise ChainDataError(
            "metaAndAssetCtxs returned unexpected format",
            code="CHAIN_DATA",
        )
    meta_obj: dict[str, Any] = data[0]
    ctx_list: list[dict[str, Any]] = data[1]
    universe: list[dict[str, Any]] = meta_obj.get("universe", [])

    for idx, meta_entry in enumerate(universe):
        if meta_entry.get("name") == asset:
            if idx >= len(ctx_list):
                raise ChainDataError(
                    f"No context entry for asset '{asset}'",
                    code="CHAIN_DATA",
                )
            return meta_entry, ctx_list[idx]

    raise ChainDataError(
        f"Asset '{asset}' not found in Hyperliquid universe",
        code="CHAIN_DATA",
    )


def _parse_funding_rate(data: Any, asset: str) -> FundingRateInfo:  # noqa: ANN401
    meta_entry, ctx = _find_asset_pair(data, asset)
    del meta_entry  # unused — only ctx needed for funding
    rate = float(ctx.get("funding", 0))
    return FundingRateInfo(
        asset=asset,
        rate=rate,
        annualized=rate * 24 * 365,
        open_interest=float(ctx.get("openInterest", 0)),
        mark_price=float(ctx.get("markPx", 0)),
        oracle_price=float(ctx.get("oraclePx", 0)),
        prev_day_price=float(ctx.get("prevDayPx", 0)),
    )


def _parse_market_info(data: Any, asset: str) -> MarketInfo:  # noqa: ANN401
    meta_entry, ctx = _find_asset_pair(data, asset)
    mid_raw = ctx.get("midPx")
    return MarketInfo(
        asset=asset,
        mark_price=float(ctx.get("markPx", 0)),
        oracle_price=float(ctx.get("oraclePx", 0)),
        mid_price=float(mid_raw) if mid_raw else None,
        open_interest=float(ctx.get("openInterest", 0)),
        funding_rate=float(ctx.get("funding", 0)),
        max_leverage=int(meta_entry.get("maxLeverage", 1)),
        prev_day_price=float(ctx.get("prevDayPx", 0)),
        day_notional_volume=float(ctx.get("dayNtlVlm", 0)),
    )


def create_from_settings(settings: Any) -> HyperliquidReader:  # noqa: ANN401
    """Factory: build a ``HyperliquidReader`` from a ``MiraelSettings`` instance."""
    return HyperliquidReader(network=settings.hl_network)
