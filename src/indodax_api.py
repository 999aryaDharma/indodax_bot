"""
indodax_api.py — Indodax HTTP Client

Menangani SEMUA komunikasi dengan Indodax:
  - Public API  : OHLCV candlestick & ticker harga
  - Private API : Saldo dompet (HMAC-SHA512, Read-Only)
  - Private V2  : Trade history (HMAC-SHA512, Read-Only)
  - Context APIs: Fear & Greed Index + BTC Dominance

Prinsip keamanan:
  - TIDAK ADA endpoint /trade, /cancelOrder, atau /withdraw
  - Private key TIDAK PERNAH masuk ke log
  - Semua request dibungkus retry + timeout
"""

import hashlib
import hmac
import logging
import time
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    APP_CONFIG,
    CONTEXT_CONFIG,
    CREDENTIALS,
    INDODAX_CONFIG,
    TIMEFRAMES,
)

logger = logging.getLogger(__name__)


# ==============================================================================
# DATA CLASSES — Output contracts yang dipakai modul hilir
# ==============================================================================

@dataclass
class OHLCVCandle:
    """Satu candle OHLCV yang sudah bersih dan siap dipakai TA Processor."""
    timestamp: int   # Unix timestamp (detik)
    open:   float
    high:   float
    low:    float
    close:  float
    volume: float


@dataclass
class WalletBalance:
    """Saldo wallet yang relevan untuk kalkulasi risk management."""
    idr_available: float     # Saldo IDR aktif (bisa digunakan)
    idr_on_order: float      # IDR yang sedang terkunci di order
    idr_total: float         # idr_available + idr_on_order
    crypto_balances: Dict[str, float]  # Saldo koin lain {symbol: amount}


@dataclass
class TradeRecord:
    """Satu record trade dari trade history."""
    pair: str
    trade_type: str   # "buy" | "sell"
    price: float
    amount: float     # Jumlah koin
    timestamp: int


@dataclass
class MarketContext:
    """Konteks makro market (Fear & Greed + BTC Dominance)."""
    fear_greed_value: int          # 0-100
    fear_greed_label: str          # "Extreme Fear", "Fear", "Greed", dll.
    btc_dominance_pct: float       # Persentase dominasi BTC (0-100)
    fetched_at: float              # Unix timestamp saat data diambil


# ==============================================================================
# HTTP SESSION FACTORY
# Menggunakan session dengan retry otomatis untuk koneksi yang lebih resilient.
# ==============================================================================

def _build_session() -> requests.Session:
    """
    Membuat HTTP session dengan retry strategy yang sudah dikonfigurasi.

    Retry hanya dilakukan untuk HTTP error 5xx (server error) dan
    connection error. HTTP 4xx (client error seperti auth failed) TIDAK
    di-retry karena retry tidak akan mengubah hasilnya.
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=INDODAX_CONFIG.max_retries,
        backoff_factor=INDODAX_CONFIG.retry_backoff_sec,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# Session dibuat sekali, di-reuse oleh semua request (lebih efisien)
_SESSION: requests.Session = _build_session()


# ==============================================================================
# HMAC-SHA512 SIGNATURE GENERATOR
# ==============================================================================

def _sign_payload(payload: str) -> str:
    """
    Menghasilkan HMAC-SHA512 signature dari payload string.

    Args:
        payload: String yang akan di-sign (request body atau query string).

    Returns:
        Hex-encoded HMAC-SHA512 signature.
    """
    secret = CREDENTIALS.indodax_secret_key.encode("utf-8")
    message = payload.encode("utf-8")
    return hmac.new(secret, message, hashlib.sha512).hexdigest()


def _get_timestamp_ms() -> int:
    """Timestamp saat ini dalam milidetik (dibutuhkan Indodax API)."""
    return int(time.time() * 1000)


# ==============================================================================
# PUBLIC API — Market Data
# ==============================================================================

def fetch_ohlcv(pair: str, timeframe_key: str) -> List[OHLCVCandle]:
    """
    Mengambil data OHLCV candlestick dari Indodax Public API.

    Args:
        pair: Pair ID format lowercase underscore, e.g. "btc_idr".
        timeframe_key: Key dari dict TIMEFRAMES, e.g. "1h", "4h".

    Returns:
        List OHLCVCandle terurut dari lama ke baru.
        List kosong jika terjadi error.

    Note:
        Indodax OHLCV endpoint menggunakan symbol uppercase tanpa underscore
        (e.g. "BTCIDR"), berbeda dari format pair standar ("btc_idr").
        Response menggunakan PascalCase keys: Time, Open, High, Low, Close, Volume
    """
    # Convert format: "btc_idr" → "BTCIDR" (Indodax requires uppercase, no underscore)
    symbol = pair.replace("_", "").upper()
    tf = TIMEFRAMES.get(timeframe_key)
    if not tf:
        logger.error(f"Timeframe tidak dikenal: '{timeframe_key}'. Pilih dari {list(TIMEFRAMES.keys())}")
        return []

    # Hitung rentang waktu: dari (limit * tf menit) yang lalu sampai sekarang
    now = int(time.time())
    
    # Menerjemahkan timeframe string Indodax menjadi detik
    if tf == '1D':
        tf_seconds = 24 * 60 * 60
    elif tf == '3D':
        tf_seconds = 3 * 24 * 60 * 60
    elif tf == '1W':
        tf_seconds = 7 * 24 * 60 * 60
    else:
        # Untuk timeframe menit seperti '15', '60', '240'
        tf_seconds = int(tf) * 60
    
    from_ts = now - (INDODAX_CONFIG.ohlcv_candle_limit * tf_seconds)

    url = f"{INDODAX_CONFIG.public_base_url}/tradingview/history_v2"
    params = {
        "symbol": symbol,
        "tf": tf,
        "from": from_ts,
        "to": now,
    }

    try:
        # ⏳ Tambahkan jeda sebelum request untuk menghormati rate limit (180 req/min)
        time.sleep(1)
        
        response = _SESSION.get(
            url,
            params=params,
            timeout=INDODAX_CONFIG.request_timeout_sec,
        )
        response.raise_for_status()
        data = response.json()

        # Validasi struktur response - Indodax returns list of dicts with PascalCase keys
        if isinstance(data, list):
            if len(data) == 0:
                logger.warning(f"[{pair}/{timeframe_key}] Response OHLCV kosong")
                return []
            
            # Check for PascalCase keys (Indodax format)
            first_item = data[0]
            if "Time" not in first_item and "time" not in first_item:
                logger.warning(f"[{pair}/{timeframe_key}] Struktur data OHLCV tidak sesuai: {list(first_item.keys())}")
                return []
            
            # Normalize PascalCase keys to lowercase for pandas-ta compatibility
            candles: List[OHLCVCandle] = []
            for row in data:
                try:
                    candles.append(OHLCVCandle(
                        timestamp=int(row.get("Time", row.get("time", 0))),
                        open=float(row.get("Open", row.get("open", 0))),
                        high=float(row.get("High", row.get("high", 0))),
                        low=float(row.get("Low", row.get("low", 0))),
                        close=float(row.get("Close", row.get("close", 0))),
                        volume=float(row.get("Volume", row.get("volume", 0))),
                    ))
                except (ValueError, KeyError) as e:
                    logger.debug(f"[{pair}/{timeframe_key}] Skip candle: {e}")
                    continue
            
            logger.debug(f"[{pair}/{timeframe_key}] Fetched {len(candles)} candles")
            time.sleep(INDODAX_CONFIG.rate_limit_sleep_sec)
            return candles
        else:
            # Fallback for dict format (single candle or error)
            required_keys = {"t", "o", "h", "l", "c", "v"}
            if not required_keys.issubset(data.keys()):
                logger.warning(f"[{pair}/{timeframe_key}] Response OHLCV tidak lengkap: {list(data.keys())}")
                return []
            
            candles: List[OHLCVCandle] = []
            timestamps = data["t"]
            for i, ts in enumerate(timestamps):
                try:
                    candles.append(OHLCVCandle(
                        timestamp=int(ts),
                        open=float(data["o"][i]),
                        high=float(data["h"][i]),
                        low=float(data["l"][i]),
                        close=float(data["c"][i]),
                        volume=float(data["v"][i]),
                    ))
                except (ValueError, IndexError) as e:
                    logger.debug(f"[{pair}/{timeframe_key}] Skip candle index {i}: {e}")
                    continue
            
            logger.debug(f"[{pair}/{timeframe_key}] Fetched {len(candles)} candles")
            time.sleep(INDODAX_CONFIG.rate_limit_sleep_sec)
            return candles

    except requests.exceptions.ReadTimeout:
        logger.warning(f"[{pair}/{timeframe_key}] ReadTimeout (15s) saat fetch OHLCV - server lambat atau mati")
        return []
    except requests.exceptions.ConnectTimeout:
        logger.warning(f"[{pair}/{timeframe_key}] ConnectTimeout saat fetch OHLCV")
        return []
    except requests.exceptions.Timeout:
        logger.warning(f"[{pair}/{timeframe_key}] Timeout saat fetch OHLCV")
        return []
    except requests.exceptions.ConnectionError as e:
        logger.warning(f"[{pair}/{timeframe_key}] Connection error saat fetch OHLCV: {e}")
        return []
    except requests.exceptions.HTTPError as e:
        logger.warning(f"[{pair}/{timeframe_key}] HTTP error: {e}")
        return []
    except (KeyError, ValueError) as e:
        logger.error(f"[{pair}/{timeframe_key}] Parse error OHLCV: {e}")
        return []
    except Exception as e:
        logger.error(f"[{pair}/{timeframe_key}] Unexpected error OHLCV: {e}", exc_info=True)
        return []


def fetch_ticker(pair: str) -> Optional[float]:
    """
    Mengambil harga terakhir (last price) dari ticker.

    Args:
        pair: Pair ID format lowercase underscore, e.g. "btc_idr".

    Returns:
        Harga terakhir sebagai float, atau None jika error.
    """
    # Convert: "btc_idr" → "btcidr" (Indodax ticker endpoint pakai format ini)
    pair_id = pair.replace("_", "")
    url = f"{INDODAX_CONFIG.public_base_url}/api/ticker/{pair_id}"

    try:
        response = _SESSION.get(url, timeout=INDODAX_CONFIG.request_timeout_sec)
        response.raise_for_status()
        data = response.json()
        last_price = float(data["ticker"]["last"])
        logger.debug(f"[{pair}] Ticker: Rp {last_price:,.0f}")
        time.sleep(INDODAX_CONFIG.rate_limit_sleep_sec)
        return last_price

    except requests.exceptions.Timeout:
        logger.warning(f"[{pair}] Timeout saat fetch ticker")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"[{pair}] HTTP error ticker: {e}")
    except (KeyError, ValueError) as e:
        logger.error(f"[{pair}] Parse error ticker: {e}")
    except Exception as e:
        logger.error(f"[{pair}] Unexpected error ticker: {e}", exc_info=True)

    return None


# ==============================================================================
# PRIVATE API — Wallet Balance (Read-Only, HMAC-SHA512)
# ==============================================================================

def fetch_wallet_balance() -> Optional[WalletBalance]:
    """
    Mengambil saldo dompet dari Indodax Private API.

    Menggunakan metode HMAC-SHA512 authentication dengan method=getInfo.
    HANYA membaca saldo — tidak ada akses ke endpoint trading.

    Returns:
        WalletBalance object, atau None jika terjadi error.
    """
    url = f"{INDODAX_CONFIG.private_base_url}/tapi"

    # Payload harus mengandung timestamp ms untuk mencegah replay attack
    payload_str = f"method=getInfo&timestamp={_get_timestamp_ms()}"
    signature = _sign_payload(payload_str)

    headers = {
        "Key": CREDENTIALS.indodax_api_key,
        "Sign": signature,
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        response = _SESSION.post(
            url,
            data=payload_str,
            headers=headers,
            timeout=INDODAX_CONFIG.request_timeout_sec,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("success") != 1:
            error_msg = data.get("error", "Unknown error")
            logger.error(f"Indodax Private API error: {error_msg}")
            return None

        balance_data = data["return"]["balance"]
        balance_hold = data["return"].get("balance_hold", {})

        idr_available = float(balance_data.get("idr", 0))
        idr_on_order = float(balance_hold.get("idr", 0))

        # Kumpulkan saldo kripto (filter yang nilainya > 0)
        crypto_balances: Dict[str, float] = {}
        for symbol, amount in balance_data.items():
            if symbol == "idr":
                continue
            amt = float(amount)
            if amt > 0:
                crypto_balances[symbol] = amt

        balance = WalletBalance(
            idr_available=idr_available,
            idr_on_order=idr_on_order,
            idr_total=idr_available + idr_on_order,
            crypto_balances=crypto_balances,
        )

        logger.info(
            f"💰 Saldo — IDR: Rp {idr_available:,.0f} | "
            f"Kripto aktif: {list(crypto_balances.keys())}"
        )
        return balance

    except requests.exceptions.Timeout:
        logger.warning("Timeout saat fetch wallet balance")
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error wallet balance: {e}")
    except (KeyError, ValueError) as e:
        logger.error(f"Parse error wallet balance: {e}")
    except Exception as e:
        logger.error(f"Unexpected error wallet balance: {e}", exc_info=True)

    return None


# ==============================================================================
# PRIVATE API V2 — Trade History (Read-Only, HMAC-SHA512)
# Subdomain berbeda: tapi.indodax.com
# ==============================================================================

def fetch_recent_trades(pair: str, limit: int = 10) -> List[TradeRecord]:
    """
    Mengambil riwayat trade terakhir pengguna untuk satu pair.

    Digunakan untuk mendeteksi apakah pengguna sudah memegang posisi
    di pair tertentu — mencegah sinyal duplikat.

    Args:
        pair: Pair ID, e.g. "btc_idr".
        limit: Jumlah record terakhir yang diambil (default 10).

    Returns:
        List TradeRecord, atau list kosong jika error.
    """
    url = f"{INDODAX_CONFIG.private_v2_base_url}/api/v2/myTrades"
    ts = _get_timestamp_ms()

    # HAPUS underscore dari pair: "btc_idr" → "btcidr"
    # V2 API menuntut format tanpa underscore (Error 1110 jika pakai underscore)
    symbol = pair.replace("_", "")

    # Query string harus persis seperti ini untuk signing yang benar
    query_str = f"symbol={symbol}&limit={limit}&timestamp={ts}"
    signature = _sign_payload(query_str)

    headers = {
        "X-APIKEY": CREDENTIALS.indodax_api_key,
        "Sign": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        response = _SESSION.get(
            url,
            params={"symbol": symbol, "limit": limit, "timestamp": ts},
            headers=headers,
            timeout=INDODAX_CONFIG.request_timeout_sec,
        )
        response.raise_for_status()
        data = response.json()

        trades: List[TradeRecord] = []
        raw_trades = data if isinstance(data, list) else data.get("data", [])

        for item in raw_trades:
            try:
                trades.append(TradeRecord(
                    pair=pair,
                    trade_type=str(item.get("type", "")).lower(),
                    price=float(item.get("price", 0)),
                    amount=float(item.get("amount", 0)),
                    timestamp=int(item.get("time", 0)),
                ))
            except (ValueError, KeyError) as e:
                logger.debug(f"[{pair}] Skip trade record: {e}")
                continue

        logger.debug(f"[{pair}] Fetched {len(trades)} trade records")
        return trades

    except requests.exceptions.Timeout:
        logger.warning(f"[{pair}] Timeout saat fetch trade history")
    except requests.exceptions.HTTPError as e:
        logger.warning(f"[{pair}] HTTP error trade history: {e}")
    except (KeyError, ValueError) as e:
        logger.error(f"[{pair}] Parse error trade history: {e}")
    except Exception as e:
        logger.error(f"[{pair}] Unexpected error trade history: {e}", exc_info=True)

    return []


def is_pair_already_held(pair: str) -> bool:
    """
    Cek apakah pengguna saat ini sudah memegang posisi di pair tertentu.

    Logika: Ambil trade history terakhir. Jika trade terakhir adalah BUY
    dan belum ada SELL setelahnya, anggap posisi masih terbuka.

    Args:
        pair: Pair ID, e.g. "btc_idr".

    Returns:
        True jika posisi masih terbuka, False jika tidak.
    """
    trades = fetch_recent_trades(pair, limit=10)
    if not trades:
        return False

    # Urutkan dari terbaru
    trades.sort(key=lambda t: t.timestamp, reverse=True)

    # Jika trade terbaru adalah BUY → anggap masih pegang posisi
    if trades[0].trade_type == "buy":
        logger.debug(f"[{pair}] Posisi masih terbuka (last trade: BUY)")
        return True

    return False


# ==============================================================================
# CONTEXT APIs — Fear & Greed + BTC Dominance
# ==============================================================================

def fetch_market_context() -> Optional[MarketContext]:
    """
    Mengambil Fear & Greed Index dan BTC Dominance sebagai konteks makro.

    Kedua data ini digunakan sebagai context filter (penyesuai bobot sinyal),
    BUKAN sebagai trigger sinyal utama.

    Returns:
        MarketContext object, atau None jika kedua API gagal.
    """
    fear_greed_value = _fetch_fear_greed()
    btc_dominance = _fetch_btc_dominance()

    if fear_greed_value is None and btc_dominance is None:
        logger.warning("Gagal fetch market context (F&G dan BTC Dom)")
        return None

    # Gunakan nilai default jika salah satu gagal
    fg_value = fear_greed_value if fear_greed_value is not None else 50
    btc_dom = btc_dominance if btc_dominance is not None else 50.0
    fg_label = _classify_fear_greed(fg_value)

    ctx = MarketContext(
        fear_greed_value=fg_value,
        fear_greed_label=fg_label,
        btc_dominance_pct=btc_dom,
        fetched_at=time.time(),
    )

    logger.info(
        f"🌡 Market Context — F&G: {fg_value} ({fg_label}) | "
        f"BTC Dom: {btc_dom:.1f}%"
    )
    return ctx


def _fetch_fear_greed() -> Optional[int]:
    """Fetch Fear & Greed Index dari alternative.me."""
    try:
        response = _SESSION.get(
            CONTEXT_CONFIG.fear_greed_url,
            timeout=INDODAX_CONFIG.request_timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        value = int(data["data"][0]["value"])
        return value
    except Exception as e:
        logger.warning(f"Gagal fetch Fear & Greed Index: {e}")
        return None


def _fetch_btc_dominance() -> Optional[float]:
    """Fetch BTC Dominance dari CoinGecko."""
    try:
        response = _SESSION.get(
            CONTEXT_CONFIG.btc_dominance_url,
            timeout=INDODAX_CONFIG.request_timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        dominance = float(data["data"]["market_cap_percentage"]["btc"])
        return dominance
    except Exception as e:
        logger.warning(f"Gagal fetch BTC Dominance: {e}")
        return None


def _classify_fear_greed(value: int) -> str:
    """Konversi nilai F&G index ke label klasifikasi."""
    if value <= 24:
        return "Extreme Fear"
    elif value <= 49:
        return "Fear"
    elif value <= 74:
        return "Greed"
    else:
        return "Extreme Greed"
