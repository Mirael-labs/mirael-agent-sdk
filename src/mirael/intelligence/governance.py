"""
Governance proposal AI summarizer.

Fetches governance proposals from on-chain or API sources and uses
Claude to generate plain-language summaries for Discord/Telegram.

Supports: Arbitrum DAO, Aave Governance, Snapshot (for any protocol).

Usage::

    digest = GovernanceDigest(
        llm=AnthropicLLM(api_key="..."),
        snapshot_spaces=["aave.eth", "arbitrumfoundation.eth"],
    )
    proposals = await digest.fetch_active()
    for p in proposals:
        print(p.summary)
        print(p.discord_message)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from mirael.logging import get_logger

_log = get_logger(__name__)

_SNAPSHOT_API = "https://hub.snapshot.org/graphql"
_ARBITRUM_DAO_SPACE = "arbitrumfoundation.eth"


@dataclass
class GovernanceProposal:
    """A governance proposal with AI-generated summary."""

    proposal_id: str
    title: str
    space: str
    body: str
    start: float
    end: float
    state: str       # "active", "closed", "pending"
    scores_total: float = 0.0
    quorum: float = 0.0
    url: str = ""

    # AI-generated fields
    summary: str = ""           # 2-3 sentence plain-language summary
    impact_analysis: str = ""   # how it affects users
    discord_message: str = ""   # formatted for Discord


class GovernanceDigest:
    """
    Fetches and summarizes DeFi governance proposals using Claude.

    Args:
        llm: AnthropicLLM instance for summaries.
        snapshot_spaces: List of Snapshot space IDs to monitor.
    """

    def __init__(
        self,
        llm: Any,  # noqa: ANN401
        *,
        snapshot_spaces: list[str] | None = None,
    ) -> None:
        self._llm = llm
        self._spaces = snapshot_spaces or [_ARBITRUM_DAO_SPACE, "aave.eth", "gmx.eth"]

    async def fetch_active(self) -> list[GovernanceProposal]:
        """Fetch all active proposals from configured spaces."""
        proposals: list[GovernanceProposal] = []
        for space in self._spaces:
            try:
                space_proposals = await self._fetch_snapshot(space, state="active")
                proposals.extend(space_proposals)
            except Exception as exc:
                _log.warning("governance_fetch_error", space=space, error=str(exc))
        return proposals

    async def summarize(self, proposal: GovernanceProposal) -> GovernanceProposal:
        """Generate AI summary for a proposal. Modifies in place and returns it."""
        from mirael.llm.models import ChatMessage

        body_preview = proposal.body[:2000] if proposal.body else "(no body)"
        hours_left = max(0, (proposal.end - time.time()) / 3600)

        prompt = (
            f"Governance proposal: '{proposal.title}'\n"
            f"Space: {proposal.space}\n"
            f"Time left to vote: {hours_left:.0f} hours\n\n"
            f"Proposal text:\n{body_preview}\n\n"
            "Please provide:\n"
            "1. SUMMARY (2 sentences): What does this proposal do in plain language?\n"
            "2. IMPACT (1-2 sentences): How does this affect users of the protocol?\n"
            "3. RECOMMENDATION (1 sentence): Vote yes/no/abstain and why (neutral framing).\n"
            "Keep it short and accessible to non-technical users."
        )

        try:
            response = await self._llm.chat(
                [ChatMessage(role="user", content=prompt)],
                max_tokens=300,
            )
            text = response.text
            proposal.summary = text

            # Build Discord message
            time_str = f"{hours_left:.0f}h" if hours_left < 48 else f"{hours_left/24:.0f}d"
            proposal.discord_message = (
                f"📋 **New Governance Proposal** — {proposal.space}\n"
                f"**{proposal.title}**\n\n"
                f"{text}\n\n"
                f"⏰ Voting ends in **{time_str}**"
                + (f" · [Vote]({proposal.url})" if proposal.url else "")
            )
        except Exception as exc:
            _log.warning("governance_summary_failed", error=str(exc))
            proposal.summary = f"[Summary unavailable: {exc}]"

        return proposal

    async def fetch_and_summarize(self) -> list[GovernanceProposal]:
        """Fetch active proposals and generate AI summaries for all."""
        proposals = await self.fetch_active()
        for p in proposals:
            await self.summarize(p)
        return proposals

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _fetch_snapshot(self, space: str, state: str = "active") -> list[GovernanceProposal]:
        query = """
        query Proposals($space: String!, $state: String!) {
          proposals(
            first: 10,
            skip: 0,
            where: { space: $space, state: $state },
            orderBy: "created",
            orderDirection: desc
          ) {
            id title body start end state scores_total quorum space
          }
        }
        """
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _SNAPSHOT_API,
                json={"query": query, "variables": {"space": space, "state": state}},
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            GovernanceProposal(
                proposal_id=str(p.get("id", "")),
                title=str(p.get("title", "")),
                space=str(p.get("space", space)),
                body=str(p.get("body", "")),
                start=float(p.get("start", 0)),
                end=float(p.get("end", 0)),
                state=str(p.get("state", "")),
                scores_total=float(p.get("scores_total", 0)),
                quorum=float(p.get("quorum", 0)),
                url=f"https://snapshot.org/#/{space}/proposal/{p.get('id', '')}",
            )
            for p in data.get("data", {}).get("proposals", [])
        ]
