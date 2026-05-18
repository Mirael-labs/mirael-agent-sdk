"""
Mirael Intelligence — AI-powered monitoring and analysis for DeFi protocols.

Modules:
    alerts       — condition-based alert engine (price, funding, liquidation)
    whale        — on-chain large-wallet movement tracker with AI context
    governance   — governance proposal summarizer powered by Claude
    digest       — daily/weekly portfolio digest generator
"""

from mirael.intelligence.alerts import AlertCondition, AlertEngine, AlertEvent
from mirael.intelligence.digest import PortfolioDigest
from mirael.intelligence.governance import GovernanceDigest
from mirael.intelligence.whale import WhaleAlert, WhaleTracker

__all__ = [
    "AlertCondition",
    "AlertEngine",
    "AlertEvent",
    "GovernanceDigest",
    "PortfolioDigest",
    "WhaleAlert",
    "WhaleTracker",
]
