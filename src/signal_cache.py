"""
signal_cache.py — Shared cache for signal metadata

Modul ini memisahkan global state (_signal_entry_cache) dari entry point (main.py)
untuk menghindari circular imports dan memudahkan testing.

State disimpan in-memory di dict karena APScheduler berjalan single-process.
"""

# Cache entry price per pair — diset saat sinyal dikirim, diambil saat exec
# Format: {"btc_idr": 67500000.0, "eth_idr": 3500000.0, ...}
signal_entry_cache: dict = {}


def set_entry(pair: str, price: float) -> None:
    """Set harga entry untuk pair."""
    signal_entry_cache[pair] = price


def get_entry(pair: str, default: float = None) -> float:
    """Get harga entry untuk pair, atau default jika tidak ada."""
    return signal_entry_cache.get(pair, default)


def clear_entry(pair: str) -> None:
    """Hapus entry cache untuk pair (setelah posisi ditutup)."""
    if pair in signal_entry_cache:
        del signal_entry_cache[pair]


def clear_all() -> None:
    """Bersihkan semua cache."""
    signal_entry_cache.clear()
