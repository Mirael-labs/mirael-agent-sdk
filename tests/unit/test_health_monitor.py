"""Unit tests for HealthMonitor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from mirael.monitoring.health_monitor import (
    HEALTH_CRITICAL,
    HEALTH_WARNING,
    HealthAlert,
    HealthMonitor,
)


class TestHealthAlert:
    def test_fields_stored(self) -> None:
        alert = HealthAlert(
            wallet="0xabc",
            asset="BTC",
            health_factor=1.1,
            liq_distance_pct=5.0,
            message="danger",
            severity="critical",
        )
        assert alert.asset == "BTC"
        assert alert.severity == "critical"
        assert alert.health_factor == pytest.approx(1.1)


class TestHealthMonitorThresholds:
    def test_critical_threshold_is_below_warning(self) -> None:
        assert HEALTH_CRITICAL < HEALTH_WARNING

    def test_critical_value(self) -> None:
        assert pytest.approx(1.2) == HEALTH_CRITICAL

    def test_warning_value(self) -> None:
        assert pytest.approx(1.5) == HEALTH_WARNING


class TestHealthMonitorDedup:
    async def test_does_not_fire_same_severity_twice(self) -> None:
        fired: list[HealthAlert] = []

        async def on_alert(alert: HealthAlert) -> None:
            fired.append(alert)

        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 1.1})
        chain.get_user_positions = AsyncMock(return_value=[])

        monitor = HealthMonitor(chain_reader=chain, check_interval=1, on_alert=on_alert)
        # First check — should fire
        await monitor._check("0xabc")
        assert len(fired) == 1

        # Second check — same severity, should NOT re-fire
        await monitor._check("0xabc")
        assert len(fired) == 1

    async def test_fires_when_severity_increases(self) -> None:
        fired: list[HealthAlert] = []

        async def on_alert(alert: HealthAlert) -> None:
            fired.append(alert)

        chain = AsyncMock()
        # First: warning (1.4)
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 1.4})
        chain.get_user_positions = AsyncMock(return_value=[])

        monitor = HealthMonitor(chain_reader=chain, check_interval=1, on_alert=on_alert)
        await monitor._check("0xabc")
        assert len(fired) == 1
        assert fired[0].severity == "warning"

        # Now: critical (1.1) — should fire again
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 1.1})
        await monitor._check("0xabc")
        assert len(fired) == 2
        assert fired[1].severity == "critical"

    async def test_safe_health_does_not_fire(self) -> None:
        fired: list[HealthAlert] = []

        async def on_alert(alert: HealthAlert) -> None:
            fired.append(alert)

        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 2.5})
        chain.get_user_positions = AsyncMock(return_value=[])

        monitor = HealthMonitor(chain_reader=chain, check_interval=1, on_alert=on_alert)
        await monitor._check("0xabc")
        assert len(fired) == 0

    async def test_position_liq_distance_critical(self) -> None:
        fired: list[HealthAlert] = []

        async def on_alert(alert: HealthAlert) -> None:
            fired.append(alert)

        chain = AsyncMock()
        chain.get_user_balance = AsyncMock(return_value={"health_factor": 999})
        chain.get_user_positions = AsyncMock(return_value=[{
            "asset": "ETH",
            "mark_price": 3000.0,
            "liquidation_price": 2750.0,  # 8.3% away — critical
        }])

        monitor = HealthMonitor(chain_reader=chain, check_interval=1, on_alert=on_alert)
        await monitor._check("0xabc")
        assert len(fired) == 1
        assert fired[0].asset == "ETH"
        assert fired[0].severity == "critical"

    def test_stop_sets_running_false(self) -> None:
        monitor = HealthMonitor(chain_reader=MagicMock(), check_interval=60)
        monitor._running = True
        monitor.stop()
        assert monitor._running is False
