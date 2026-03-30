# Indodax API Specification

> Based on official Indodax API documentation. Use these exact endpoints and authentication methods.

---

## 📋 Table of Contents

1. [Public API (Market Data)](#public-api)
2. [Private API (Portfolio Data)](#private-api)
3. [Private API V2 (Trade History)](#private-api-v2)
4. [Security & Safety Rules](#security-rules)

---

## Public API

**Base URL:** `https://indodax.com`  
**Rate Limit:** 180 requests/minute  
**Authentication:** None

### Get Ticker (Current Price)

```
GET /api/ticker/<pair_id>
```

| Parameter | Value                       | Example            |
| --------- | --------------------------- | ------------------ |
| `pair_id` | Pair identifier (lowercase) | `btcidr`, `ethidr` |

**Usage:** Fetch current last price for a trading pair.

**⚠️ Important:** Implement `time.sleep(1)` between requests to respect the 180 req/min rate limit.

---

### Get OHLCV (Candlestick Data)

```
GET /tradingview/history_v2
```

| Parameter | Description          | Example            |
| --------- | -------------------- | ------------------ |
| `symbol`  | Pair (uppercase)     | `BTCIDR`, `ETHIDR` |
| `tf`      | Timeframe            | `15`, `60`, `240`  |
| `from`    | Start Unix timestamp | `1774039848`       |
| `to`      | End Unix timestamp   | `1774759848`       |

**Usage:** Retrieve historical candlestick data for technical analysis.

---

## Private API

**Base URL:** `https://indodax.com`  
**Rate Limit:** Standard  
**Authentication:** HMAC-SHA512

### Get Portfolio Info

```
POST /tapi
```

**Request Body:**

```
method=getInfo&timestamp=<current_timestamp_ms>
```

**Headers:**

| Header | Value                                 |
| ------ | ------------------------------------- |
| `Key`  | Your API Key                          |
| `Sign` | HMAC-SHA512(request_body, secret_key) |

**Response:** IDR balance location

```python
response.json()["return"]["balance"]["idr"]
```

**Usage:** Fetch current account balance in IDR.

---

## Private API V2

**Base URL:** `https://tapi.indodax.com`  
**Rate Limit:** Standard  
**Authentication:** HMAC-SHA512

### Get Trade History

```
GET /api/v2/myTrades
```

**Query Parameters:**

| Parameter   | Description            | Example         |
| ----------- | ---------------------- | --------------- |
| `symbol`    | Pair (lowercase)       | `btcidr`        |
| `limit`     | Max results            | `10`            |
| `timestamp` | Current timestamp (ms) | `1578304294000` |

**Headers:**

| Header         | Value                                 |
| -------------- | ------------------------------------- |
| `Accept`       | `application/json`                    |
| `Content-Type` | `application/json`                    |
| `X-APIKEY`     | Your API Key                          |
| `Sign`         | HMAC-SHA512(query_string, secret_key) |

**Example Sign Calculation:**

```
Query String: symbol=btcidr&limit=10&timestamp=1578304294000
Sign: HMAC-SHA512(query_string, secret_key)
```

**Usage:** Check recent BUY orders to:

- Calculate actual PnL using real entry price
- Monitor active TP/SL targets
- Avoid duplicate buy signals for held assets

---

## Security Rules

⚠️ **STRICT SAFETY RULES** ⚠️

- ✅ **ALLOWED:** `getInfo`, `/api/v2/myTrades` (Info/View permissions only)
- ❌ **FORBIDDEN:** `trade`, `cancelOrder`, or any action-based endpoints
- 👮 **Reason:** Maintain 100% fund safety - read-only operations only
