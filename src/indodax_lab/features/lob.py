"""Limit Order Book (LOB) feature extraction and tensor construction (LOB-01).

Guarantees:
1. Microstructure features strictly derived from top-N order book depth levels.
2. Depth imbalance, spread, and microprice calculated with exact numerical bounds.
3. No forward-looking aggregation or temporal lookahead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from indodax_lab.models.lob.dataset import BookSnapshot


def extract_lob_tensor(snapshots: list[BookSnapshot], levels: int = 10) -> np.ndarray:
    """Extract standard limit order book tensor of shape (T, 4 * levels).

    Columns per level k: [bid_price_k, bid_vol_k, ask_price_k, ask_vol_k]
    """
    if not snapshots:
        return np.empty((0, 4 * levels), dtype=float)

    tensor = np.zeros((len(snapshots), 4 * levels), dtype=float)
    for t_idx, snap in enumerate(snapshots):
        for k in range(levels):
            base_col = 4 * k
            # Bid level k
            if k < len(snap.bids):
                tensor[t_idx, base_col] = float(snap.bids[k].price)
                tensor[t_idx, base_col + 1] = float(snap.bids[k].volume)
            # Ask level k
            if k < len(snap.asks):
                tensor[t_idx, base_col + 2] = float(snap.asks[k].price)
                tensor[t_idx, base_col + 3] = float(snap.asks[k].volume)

    return tensor


def compute_depth_imbalance(lob_tensor: np.ndarray, levels: int = 1) -> np.ndarray:
    """Compute order book volume imbalance across top N depth levels.

    Imbalance = (Total_Bid_Vol - Total_Ask_Vol) / (Total_Bid_Vol + Total_Ask_Vol)
    Output values bounded in [-1.0, 1.0].
    """
    if lob_tensor.shape[0] == 0:
        return np.empty((0,), dtype=float)

    total_levels = lob_tensor.shape[1] // 4
    eff_levels = min(levels, total_levels)

    bid_vol_indices = [4 * k + 1 for k in range(eff_levels)]
    ask_vol_indices = [4 * k + 3 for k in range(eff_levels)]

    total_bid_vol = np.sum(lob_tensor[:, bid_vol_indices], axis=1)
    total_ask_vol = np.sum(lob_tensor[:, ask_vol_indices], axis=1)

    denom = total_bid_vol + total_ask_vol
    # Numerical stability epsilon
    eps = 1e-12
    imbalance = np.where(denom > eps, (total_bid_vol - total_ask_vol) / np.maximum(denom, eps), 0.0)
    return np.clip(imbalance, -1.0, 1.0)


def compute_spread(lob_tensor: np.ndarray) -> np.ndarray:
    """Compute top-of-book bid-ask spread: ask_price_0 - bid_price_0."""
    if lob_tensor.shape[0] == 0:
        return np.empty((0,), dtype=float)
    ask_p0 = lob_tensor[:, 2]
    bid_p0 = lob_tensor[:, 0]
    return ask_p0 - bid_p0


def compute_microprice(lob_tensor: np.ndarray) -> np.ndarray:
    """Compute volume-weighted microprice from top-of-book levels.

    Microprice = (P_ask * V_bid + P_bid * V_ask) / (V_bid + V_ask)
    """
    if lob_tensor.shape[0] == 0:
        return np.empty((0,), dtype=float)

    bid_p0 = lob_tensor[:, 0]
    bid_v0 = lob_tensor[:, 1]
    ask_p0 = lob_tensor[:, 2]
    ask_v0 = lob_tensor[:, 3]

    denom = bid_v0 + ask_v0
    eps = 1e-12
    mid_price = (bid_p0 + ask_p0) / 2.0
    micro = np.where(denom > eps, (ask_p0 * bid_v0 + bid_p0 * ask_v0) / np.maximum(denom, eps), mid_price)
    return micro
