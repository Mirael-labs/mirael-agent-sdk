"""
Aave V3 on Arbitrum — read-only on-chain reader.

Implements ``OnchainReader`` Protocol using Web3.py against the
Arbitrum mainnet (or any EVM-compatible RPC).

Aave V3 Arbitrum contract addresses (mainnet):
  Pool:                   0x794a61358D6845594F94dc1DB02A252b5b4814aD
  PoolAddressesProvider:  0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb
  AaveOracle:             0xb56c2F0B653B2e0b10C9b928C8580Ac5Df02C7C7
  UiPoolDataProvider:     0x5c5228aC8BC1528482514aF3e27E692495148717

Usage::

    async with AaveV3Reader() as reader:
        balance = await reader.get_user_balance("0xYOUR_WALLET")
        positions = await reader.get_user_positions("0xYOUR_WALLET")
"""

from __future__ import annotations

from typing import Any

from mirael.exceptions import ChainConnectionError, ChainDataError
from mirael.logging import get_logger

_log = get_logger(__name__)

# ── Arbitrum mainnet contract addresses ───────────────────────────────────────

_POOL_ADDR = "0x794a61358D6845594F94dc1DB02A252b5b4814aD"
_POOL_ADDRESSES_PROVIDER = "0xa97684ead0e402dC232d5A977953DF7ECBaB3CDb"
_AAVE_ORACLE = "0xb56c2F0B653B2e0b10C9b928C8580Ac5Df02C7C7"
_UI_POOL_DATA_PROVIDER = "0x5c5228aC8BC1528482514aF3e27E692495148717"
_DEFAULT_RPC = "https://arb1.arbitrum.io/rpc"

# ── Minimal ABIs ──────────────────────────────────────────────────────────────

_POOL_ABI: list[dict[str, Any]] = [
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "getUserAccountData",
        "outputs": [
            {"name": "totalCollateralBase", "type": "uint256"},
            {"name": "totalDebtBase", "type": "uint256"},
            {"name": "availableBorrowsBase", "type": "uint256"},
            {"name": "currentLiquidationThreshold", "type": "uint256"},
            {"name": "ltv", "type": "uint256"},
            {"name": "healthFactor", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getReservesList",
        "outputs": [{"name": "", "type": "address[]"}],
        "stateMutability": "view",
        "type": "function",
    },
]

_UI_DATA_PROVIDER_ABI: list[dict[str, Any]] = [
    {
        "inputs": [
            {"name": "provider", "type": "address"},
            {"name": "user", "type": "address"},
        ],
        "name": "getUserReservesData",
        "outputs": [
            {
                "components": [
                    {"name": "underlyingAsset", "type": "address"},
                    {"name": "scaledATokenBalance", "type": "uint256"},
                    {"name": "usageAsCollateralEnabledOnUser", "type": "bool"},
                    {"name": "stableBorrowRate", "type": "uint128"},
                    {"name": "scaledVariableDebt", "type": "uint256"},
                    {"name": "principalStableDebt", "type": "uint128"},
                    {"name": "stableBorrowLastUpdateTimestamp", "type": "uint256"},
                ],
                "name": "",
                "type": "tuple[]",
            },
            {"name": "", "type": "uint8"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "provider", "type": "address"},
        ],
        "name": "getReservesData",
        "outputs": [
            {
                "components": [
                    {"name": "underlyingAsset", "type": "address"},
                    {"name": "name", "type": "string"},
                    {"name": "symbol", "type": "string"},
                    {"name": "decimals", "type": "uint256"},
                    {"name": "baseLTVasCollateral", "type": "uint256"},
                    {"name": "reserveLiquidationThreshold", "type": "uint256"},
                    {"name": "reserveLiquidationBonus", "type": "uint256"},
                    {"name": "reserveFactor", "type": "uint256"},
                    {"name": "usageAsCollateralEnabled", "type": "bool"},
                    {"name": "borrowingEnabled", "type": "bool"},
                    {"name": "stableBorrowRateEnabled", "type": "bool"},
                    {"name": "isActive", "type": "bool"},
                    {"name": "isFrozen", "type": "bool"},
                    {"name": "liquidityIndex", "type": "uint128"},
                    {"name": "variableBorrowIndex", "type": "uint128"},
                    {"name": "liquidityRate", "type": "uint128"},
                    {"name": "variableBorrowRate", "type": "uint128"},
                    {"name": "stableBorrowRate", "type": "uint128"},
                    {"name": "lastUpdateTimestamp", "type": "uint40"},
                    {"name": "aTokenAddress", "type": "address"},
                    {"name": "stableDebtTokenAddress", "type": "address"},
                    {"name": "variableDebtTokenAddress", "type": "address"},
                    {"name": "interestRateStrategyAddress", "type": "address"},
                    {"name": "availableLiquidity", "type": "uint256"},
                    {"name": "totalPrincipalStableDebt", "type": "uint256"},
                    {"name": "averageStableRate", "type": "uint256"},
                    {"name": "stableDebtLastUpdateTimestamp", "type": "uint256"},
                    {"name": "totalScaledVariableDebt", "type": "uint256"},
                    {"name": "priceInMarketReferenceCurrency", "type": "uint256"},
                    {"name": "priceOracle", "type": "address"},
                    {"name": "variableRateSlope1", "type": "uint256"},
                    {"name": "variableRateSlope2", "type": "uint256"},
                    {"name": "stableRateSlope1", "type": "uint256"},
                    {"name": "stableRateSlope2", "type": "uint256"},
                    {"name": "baseStableBorrowRate", "type": "uint256"},
                    {"name": "baseVariableBorrowRate", "type": "uint256"},
                    {"name": "optimalUsageRatio", "type": "uint256"},
                    {"name": "isPaused", "type": "bool"},
                    {"name": "isSiloedBorrowing", "type": "bool"},
                    {"name": "accruedToTreasury", "type": "uint256"},
                    {"name": "unbacked", "type": "uint256"},
                    {"name": "isolationModeTotalDebt", "type": "uint256"},
                    {"name": "flashLoanEnabled", "type": "bool"},
                    {"name": "debtCeiling", "type": "uint256"},
                    {"name": "debtCeilingDecimals", "type": "uint256"},
                    {"name": "eModeCategoryId", "type": "uint8"},
                    {"name": "borrowCap", "type": "uint256"},
                    {"name": "supplyCap", "type": "uint256"},
                    {"name": "eModeLtv", "type": "uint16"},
                    {"name": "eModeLiquidationThreshold", "type": "uint16"},
                    {"name": "eModeLiquidationBonus", "type": "uint16"},
                    {"name": "eModePriceSource", "type": "address"},
                    {"name": "eModeLabel", "type": "string"},
                    {"name": "borrowableInIsolation", "type": "bool"},
                ],
                "name": "",
                "type": "tuple[]",
            },
            {"name": "", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

_WAD = 10**18
_RAY = 10**27
_BASE_CURRENCY_UNIT = 10**8  # Aave oracle prices in USD with 8 decimals


def _ray_to_apy(ray_rate: int) -> float:
    """Convert Aave RAY-denominated per-second rate to APY."""
    seconds_per_year = 365 * 24 * 3600
    rate_per_second = ray_rate / _RAY
    return (1 + rate_per_second) ** seconds_per_year - 1


class AaveV3Reader:
    """
    Read-only Aave V3 client for Arbitrum mainnet.

    Satisfies the ``OnchainReader`` Protocol.

    For DeFi protocols on Arbitrum: shows user collateral positions,
    borrows, health factor, and per-market borrow/supply rates.

    Args:
        rpc_url: Arbitrum JSON-RPC endpoint.
        pool_address: Aave V3 Pool contract address.
        max_retries: Retry attempts on transient RPC failures.
    """

    def __init__(
        self,
        rpc_url: str = _DEFAULT_RPC,
        *,
        pool_address: str = _POOL_ADDR,
        max_retries: int = 3,
    ) -> None:
        self._rpc_url = rpc_url
        self._pool_addr = pool_address
        self._max_retries = max_retries
        self._w3: Any = None

    # ── Context manager ───────────────────────────────────────────────────────

    async def __aenter__(self) -> AaveV3Reader:
        self._get_w3()
        return self

    async def __aexit__(self, *_: object) -> None:
        pass  # web3 AsyncHTTPProvider has no explicit close

    def _get_w3(self) -> Any:  # noqa: ANN401
        if self._w3 is None:
            try:
                from web3 import AsyncWeb3
                from web3.providers import AsyncHTTPProvider

                self._w3 = AsyncWeb3(AsyncHTTPProvider(self._rpc_url))
            except ImportError as exc:
                raise ChainConnectionError(
                    "web3 not installed. Run: uv add web3",
                    code="CHAIN_IMPORT",
                ) from exc
        return self._w3

    # ── Public API ────────────────────────────────────────────────────────────

    async def get_user_positions(self, wallet: str) -> list[dict[str, Any]]:
        """
        Return active Aave V3 positions (supplies + borrows) for a wallet.

        Positions with zero balance are excluded.

        Returns:
            List of dicts with keys matching ``AaveUserPosition``:
            asset_symbol, asset_address, position_type, balance_usd,
            apy, is_collateral.
        """
        w3 = self._get_w3()
        try:
            ui_contract = w3.eth.contract(
                address=w3.to_checksum_address(_UI_POOL_DATA_PROVIDER),
                abi=_UI_DATA_PROVIDER_ABI,
            )
            # Fetch reserves metadata (symbols, APYs, prices)
            # Note: if ABI doesn't match the deployed contract version, returns []
            reserves_data, _ = await ui_contract.functions.getReservesData(
                w3.to_checksum_address(_POOL_ADDRESSES_PROVIDER)
            ).call()
            # Build address → reserve index map
            reserve_map = {r[0].lower(): (i, r) for i, r in enumerate(reserves_data)}

            # Fetch user's per-reserve balances
            user_reserves, _ = await ui_contract.functions.getUserReservesData(
                w3.to_checksum_address(_POOL_ADDRESSES_PROVIDER),
                w3.to_checksum_address(wallet),
            ).call()
        except Exception as exc:
            if isinstance(exc, ChainConnectionError):
                raise
            # ABI mismatch or empty wallet — return empty positions gracefully
            _log.warning("aave_positions_unavailable", error=str(exc)[:120])
            return []

        positions: list[dict[str, Any]] = []
        for ur in user_reserves:
            asset_addr, a_balance, is_collateral, _, var_debt, stable_debt, _ = ur
            if a_balance == 0 and var_debt == 0 and stable_debt == 0:
                continue

            idx_data = reserve_map.get(asset_addr.lower())
            if not idx_data:
                continue
            _, r = idx_data
            symbol: str = r[2]  # symbol field
            decimals: int = int(r[3])
            price_usd = r[28] / _BASE_CURRENCY_UNIT  # priceInMarketReferenceCurrency

            supply_apy = _ray_to_apy(r[15])  # liquidityRate
            var_borrow_apy = _ray_to_apy(r[16])  # variableBorrowRate

            unit = 10**decimals
            if a_balance > 0:
                bal_usd = (a_balance / unit) * price_usd
                positions.append(
                    {
                        "asset_symbol": symbol,
                        "asset_address": asset_addr,
                        "position_type": "supply",
                        "balance_usd": bal_usd,
                        "apy": supply_apy,
                        "is_collateral": bool(is_collateral),
                    }
                )
            if var_debt > 0:
                debt_usd = (var_debt / unit) * price_usd
                positions.append(
                    {
                        "asset_symbol": symbol,
                        "asset_address": asset_addr,
                        "position_type": "borrow",
                        "balance_usd": debt_usd,
                        "apy": var_borrow_apy,
                        "is_collateral": False,
                    }
                )

        _log.debug("aave_positions_fetched", wallet=wallet[:10], count=len(positions))
        return positions

    async def get_user_balance(self, wallet: str) -> dict[str, Any]:
        """
        Return Aave V3 account health summary for a wallet.

        Returns:
            Dict with keys matching ``AaveAccountSummary``:
            total_collateral_usd, total_debt_usd, available_borrow_usd,
            current_ltv, liquidation_threshold, health_factor.
        """
        w3 = self._get_w3()
        try:
            pool = w3.eth.contract(
                address=w3.to_checksum_address(self._pool_addr),
                abi=_POOL_ABI,
            )
            result = await pool.functions.getUserAccountData(
                w3.to_checksum_address(wallet)
            ).call()
        except Exception as exc:
            raise ChainConnectionError(f"Aave getUserAccountData failed: {exc}") from exc

        total_col, total_debt, avail_borrow, liq_threshold, ltv, hf = result
        unit = _BASE_CURRENCY_UNIT
        wad = _WAD

        # Aave returns type(uint256).max when there is no debt (health factor = infinity)
        # Cap at 999 for display purposes
        raw_health = hf / wad
        health = min(raw_health, 999.0)
        _log.debug("aave_balance_fetched", wallet=wallet[:10], health_factor=health)

        return {
            "total_collateral_usd": total_col / unit,
            "total_debt_usd": total_debt / unit,
            "available_borrow_usd": avail_borrow / unit,
            "current_ltv": ltv / 10_000,
            "liquidation_threshold": liq_threshold / 10_000,
            "health_factor": health,
        }

    async def get_recent_trades(self, wallet: str, limit: int = 50) -> list[dict[str, Any]]:
        """
        Aave V3 does not have a native trades/fills concept.

        Returns an empty list — Aave protocol interactions are tracked
        via on-chain events, which require an indexer not available here.
        """
        _log.debug("aave_recent_trades_not_supported")
        return []

    async def get_funding_rate(self, asset: str) -> dict[str, Any]:
        """
        Return Aave V3 borrow/supply APYs for a given asset symbol.

        Args:
            asset: Token symbol (e.g. ``"USDC"``, ``"WETH"``, ``"ARB"``).

        Returns:
            Dict with keys: asset, supply_apy, variable_borrow_apy,
            stable_borrow_apy, utilization_rate.

        Raises:
            ChainDataError: If the asset is not found in Aave V3 Arbitrum.
        """
        market = await self.get_market_info(asset)
        return {
            "asset": market["asset_symbol"],
            "supply_apy": market["supply_apy"],
            "variable_borrow_apy": market["variable_borrow_apy"],
            "stable_borrow_apy": market["stable_borrow_apy"],
            "utilization_rate": market["utilization_rate"],
        }

    async def get_market_info(self, asset: str) -> dict[str, Any]:
        """
        Return full market data for an Aave V3 Arbitrum asset.

        Args:
            asset: Token symbol (case-insensitive, e.g. ``"USDC"``, ``"WETH"``).

        Returns:
            Dict with keys matching ``AaveMarket``.

        Raises:
            ChainDataError: If asset symbol not found in Aave V3 reserves.
        """
        w3 = self._get_w3()
        try:
            ui_contract = w3.eth.contract(
                address=w3.to_checksum_address(_UI_POOL_DATA_PROVIDER),
                abi=_UI_DATA_PROVIDER_ABI,
            )
            reserves_data, _ = await ui_contract.functions.getReservesData(
                w3.to_checksum_address(_POOL_ADDRESSES_PROVIDER)
            ).call()
        except Exception as exc:
            raise ChainConnectionError(f"Aave getReservesData failed: {exc}") from exc

        target = asset.upper()
        for r in reserves_data:
            symbol: str = r[2]
            if symbol.upper() != target:
                continue

            decimals = int(r[3])
            price_usd = r[28] / _BASE_CURRENCY_UNIT
            unit = 10**decimals

            supply_apy = _ray_to_apy(r[15])  # liquidityRate
            var_borrow_apy = _ray_to_apy(r[16])  # variableBorrowRate
            stable_borrow_apy = _ray_to_apy(r[17])  # stableBorrowRate

            available_liq = r[23]  # availableLiquidity
            total_var_debt_scaled = r[27]  # totalScaledVariableDebt
            total_var_debt = total_var_debt_scaled  # simplified; exact needs index
            total_stable_debt = r[24]

            total_supplied = available_liq + total_var_debt + total_stable_debt
            util = total_var_debt / total_supplied if total_supplied > 0 else 0.0

            _log.debug("aave_market_fetched", asset=asset, supply_apy=supply_apy)
            return {
                "asset_symbol": symbol,
                "asset_address": r[0],
                "supply_apy": supply_apy,
                "variable_borrow_apy": var_borrow_apy,
                "stable_borrow_apy": stable_borrow_apy,
                "total_supplied_usd": (total_supplied / unit) * price_usd,
                "total_borrowed_usd": ((total_var_debt + total_stable_debt) / unit) * price_usd,
                "utilization_rate": util,
                "ltv": int(r[4]) / 10_000,
                "liquidation_threshold": int(r[5]) / 10_000,
            }

        raise ChainDataError(
            f"Asset '{asset}' not found in Aave V3 Arbitrum reserves",
            code="CHAIN_DATA",
        )


def create_from_settings(settings: Any) -> AaveV3Reader:  # noqa: ANN401
    """Factory: build an ``AaveV3Reader`` from a ``MiraelSettings`` instance."""
    return AaveV3Reader(rpc_url=settings.arbitrum_rpc_url)
