"""
quant/backtest/costs.py
-----------------------
Configurable transaction cost model for QuantEdge Sprint 3.

Responsibility:
  - Encapsulate commission and slippage parameters.
  - Provide effective price calculations for entries and exits.
  - Provide total cost calculation for a trade leg.

==============================================================
COST MODEL CONVENTIONS
==============================================================

Slippage (long position):
  Effective entry = reference_open × (1 + slippage_rate)
    → we pay MORE on the buy
  Effective exit  = reference_price × (1 - slippage_rate)
    → we receive LESS on the sell

Commission:
  Per-leg cost = effective_price × quantity × commission_rate
  Applied at both entry and exit.

Total transaction cost for a round trip:
  = entry_commission + exit_commission

These are RESEARCH DEFAULTS, not claims about actual broker charges.
They are configurable so they can be updated when real fee schedules
are available.

Default values:
  commission_rate = 0.0005   (0.05% per side)
  slippage_rate   = 0.0005   (0.05% per side)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """
    Immutable cost model configuration.

    Parameters
    ----------
    commission_rate : float
        Fraction of trade value charged as commission per side.
        Default: 0.0005 (0.05% — research default, not a real broker rate).
    slippage_rate : float
        Fraction of reference price applied as execution slippage per side.
        Default: 0.0005 (0.05% — research default).

    Notes
    -----
    This model is intentionally simple and symmetric. Real-world costs
    depend on broker, order type, lot size, exchange taxes, STT, etc.
    Parameterisation is the first step toward a realistic model.
    """

    commission_rate: float = 0.0005
    slippage_rate: float = 0.0005

    def effective_entry_price(self, reference_price: float) -> float:
        """
        Effective buy price after slippage.

        For a long entry we pay MORE than the reference price.

        Parameters
        ----------
        reference_price : float
            Raw execution price (e.g. next-day open).

        Returns
        -------
        float
            Effective price after slippage.
        """
        return reference_price * (1.0 + self.slippage_rate)

    def effective_exit_price(self, reference_price: float) -> float:
        """
        Effective sell price after slippage.

        For a long exit we receive LESS than the reference price.

        Parameters
        ----------
        reference_price : float
            Raw exit price (e.g. next-day open, stop price, or close).

        Returns
        -------
        float
            Effective price after slippage.
        """
        return reference_price * (1.0 - self.slippage_rate)

    def entry_commission(self, effective_entry: float, quantity: int) -> float:
        """Total commission cost for entering a position."""
        return effective_entry * quantity * self.commission_rate

    def exit_commission(self, effective_exit: float, quantity: int) -> float:
        """Total commission cost for exiting a position."""
        return effective_exit * quantity * self.commission_rate

    def total_transaction_cost(
        self,
        effective_entry: float,
        effective_exit: float,
        quantity: int,
    ) -> float:
        """
        Total round-trip transaction cost (entry + exit commissions).

        Parameters
        ----------
        effective_entry : float
            Post-slippage entry price.
        effective_exit : float
            Post-slippage exit price.
        quantity : int
            Number of shares.

        Returns
        -------
        float
            Total commission cost for the full round trip.
        """
        return self.entry_commission(effective_entry, quantity) + \
               self.exit_commission(effective_exit, quantity)


# Default cost model instance (used when no custom model is provided).
DEFAULT_COST_MODEL = CostModel(
    commission_rate=0.0005,
    slippage_rate=0.0005,
)
