"""AI features: custom-strategy parsing and the AI Lab assistant (OpenAI / Anthropic / Gemini)."""
from __future__ import annotations

import hashlib
import json
import re

import httpx

from . import config, db

TIMEFRAMES = {"5m", "15m", "1h", "4h"}
INDICATORS = {"close", "open", "high", "low", "volume", "ema", "sma", "rsi", "atr", "atr_pct", "adx", "volume_sma",
              "bb_upper", "bb_lower", "bb_mid", "bb_width", "macd", "macd_signal", "macd_hist", "supertrend",
              "supertrend_dir"}
OPS = {">", "<", ">=", "<=", "crosses_above", "crosses_below", "rising", "falling", "between"}
REGIMES = {"TRENDING", "TRANSITIONAL", "RANGING"}

SCHEMA_PROMPT = """You convert a trader's natural-language strategy description into JSON for a bot.
Return ONLY a JSON object with this shape (omit optional keys you don't need):
{
  "name": string,
  "timeframe": "5m"|"15m"|"1h"|"4h",
  "confirm_timeframe": "1h"|"4h" (optional),
  "symbols": [string] (optional, e.g. ["BTCUSDT"]),
  "direction": "both"|"long"|"short",
  "conditions": {
    "long":  [Condition, ...],
    "short": [Condition, ...]
  },
  "sl_atr": number, "tp_atr": number,
  "order_type": "market"|"limit",
  "partial_tp": {"enabled": bool, "percent": number},
  "trailing": {"enabled": bool, "atr_distance": number},
  "scaling": {"entries": integer 1-4, "step_atr": number},
  "allowed_regimes": ["TRENDING"|"TRANSITIONAL"|"RANGING", ...]
}
Condition = {"left": Series, "op": ">"|"<"|">="|"<="|"crosses_above"|"crosses_below"|"rising"|"falling"|"between",
             "right": Series | number, "factor": number (optional multiplier on right), "range": [lo, hi] (for between),
             "timeframe": (optional, overrides strategy timeframe)}
Series = {"ind": one of close, open, high, low, volume, ema, sma, rsi, atr, atr_pct, adx, volume_sma, bb_upper,
          bb_lower, bb_mid, bb_width (percent), macd, macd_signal, macd_hist, supertrend, supertrend_dir (+1/-1),
          "period": integer, "mult": number (bands / supertrend)}
Mirror long conditions for short when the user says "symmetric opposite"."""


class AIError(RuntimeError):
    pass


def available_provider() -> str | None:
    for name, key in (("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY"), ("gemini", "GEMINI_API_KEY")):
        if config.secret(key):
            return name
    return None


def complete(system: str, user: str, *, provider: str | None = None, user_id=None, feature: str = "chat",
             json_mode: bool = False, http: httpx.Client | None = None) -> str:
    provider = provider or available_provider()
    if not provider:
        raise AIError("No AI provider configured (set ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY)")
    http = http or httpx.Client(timeout=60.0)
    if provider == "anthropic":
        model = config.env("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        r = http.post("https://api.anthropic.com/v1/messages", headers={
            "x-api-key": config.secret("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
            json={"model": model, "max_tokens": 2000, "system": system,
                  "messages": [{"role": "user", "content": user}]})
        data = r.json()
        if r.status_code != 200:
            raise AIError(str(data.get("error", data))[:300])
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = (data.get("usage") or {}).get("input_tokens"), (data.get("usage") or {}).get("output_tokens")
    elif provider == "openai":
        model = config.env("OPENAI_MODEL", "gpt-4o-mini")
        body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = http.post("https://api.openai.com/v1/chat/completions",
                      headers={"Authorization": f"Bearer {config.secret('OPENAI_API_KEY')}"}, json=body)
        data = r.json()
        if r.status_code != 200:
            raise AIError(str(data.get("error", data))[:300])
        text = data["choices"][0]["message"]["content"]
        usage = (data.get("usage") or {}).get("prompt_tokens"), (data.get("usage") or {}).get("completion_tokens")
    elif provider == "gemini":
        model = config.env("GEMINI_MODEL", "gemini-2.0-flash")
        r = http.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": config.secret("GEMINI_API_KEY")},
                      json={"systemInstruction": {"parts": [{"text": system}]},
                            "contents": [{"role": "user", "parts": [{"text": user}]}]})
        data = r.json()
        if r.status_code != 200:
            raise AIError(str(data.get("error", data))[:300])
        text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
        um = data.get("usageMetadata") or {}
        usage = um.get("promptTokenCount"), um.get("candidatesTokenCount")
    else:
        raise AIError(f"unknown provider {provider}")
    if user_id is not None:
        db.execute("INSERT INTO ai_usage (user_id, provider, model, feature, input_tokens, output_tokens) "
                   "VALUES (%s,%s,%s,%s,%s,%s)", (user_id, provider, model, feature, usage[0], usage[1]))
    return text


def extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    raw = m.group(1) if m else text[text.find("{"): text.rfind("}") + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIError(f"AI did not return valid JSON: {exc}") from exc


def _check_series(s, where: str) -> None:
    if isinstance(s, (int, float)):
        return
    if not isinstance(s, dict) or s.get("ind", s.get("indicator")) not in INDICATORS:
        raise ValueError(f"{where}: unknown indicator {s!r}")
    if "period" in s and not (1 <= int(s["period"]) <= 400):
        raise ValueError(f"{where}: period out of range")


def validate_definition(d: dict) -> dict:
    if not isinstance(d, dict):
        raise ValueError("definition must be an object")
    d.setdefault("timeframe", "15m")
    d.setdefault("direction", "both")
    if d["timeframe"] not in TIMEFRAMES:
        raise ValueError(f"timeframe must be one of {sorted(TIMEFRAMES)}")
    if d.get("confirm_timeframe") and d["confirm_timeframe"] not in TIMEFRAMES:
        raise ValueError("invalid confirm_timeframe")
    if d["direction"] not in ("both", "long", "short"):
        raise ValueError("direction must be both|long|short")
    conds = d.get("conditions") or {}
    if not any(conds.get(k) for k in ("long", "short")):
        raise ValueError("at least one long or short condition is required")
    for side in ("long", "short"):
        for i, c in enumerate(conds.get(side) or []):
            where = f"conditions.{side}[{i}]"
            if c.get("op") not in OPS:
                raise ValueError(f"{where}: unsupported op {c.get('op')!r}")
            _check_series(c.get("left", c), where)
            if c["op"] not in ("rising", "falling", "between"):
                _check_series(c.get("right", c.get("value", 0)), where)
            if c["op"] == "between" and not (isinstance(c.get("range"), list) and len(c["range"]) == 2):
                raise ValueError(f"{where}: between needs range [lo, hi]")
            if c.get("timeframe") and c["timeframe"] not in TIMEFRAMES:
                raise ValueError(f"{where}: invalid timeframe")
    for key, lo, hi in (("sl_atr", 0.2, 10), ("tp_atr", 0.2, 20)):
        d[key] = float(d.get(key, 1.5 if key == "sl_atr" else 3.0))
        if not lo <= d[key] <= hi:
            raise ValueError(f"{key} must be between {lo} and {hi}")
    sc = d.get("scaling") or {}
    if sc and not 1 <= int(sc.get("entries", 1)) <= 4:
        raise ValueError("scaling.entries must be 1-4")
    if d.get("allowed_regimes") and not set(d["allowed_regimes"]) <= REGIMES:
        raise ValueError("invalid allowed_regimes")
    return d


def parse_custom_strategy(user_id, description: str, provider: str | None = None, http=None) -> dict:
    key = hashlib.sha256(f"parse:{description.strip()}".encode()).hexdigest()
    cached = db.fetch_one("SELECT response FROM ai_cache WHERE cache_key=%s AND (expires_at IS NULL OR expires_at > NOW())",
                          (key,))
    if cached:
        definition = cached["response"]
    else:
        text = complete(SCHEMA_PROMPT, description, provider=provider, user_id=user_id, feature="parse_strategy",
                        json_mode=True, http=http)
        definition = extract_json(text)
    definition = validate_definition(definition)
    db.execute("""INSERT INTO ai_cache (cache_key, provider, response, expires_at) VALUES (%s,%s,%s,NOW()+interval '30 days')
                  ON CONFLICT (cache_key) DO UPDATE SET response=EXCLUDED.response""",
               (key, provider or available_provider() or "unknown", json.dumps(definition)))
    return definition


def lab_context(user_id) -> str:
    perf = db.fetch(
        """SELECT strategy, COUNT(*) AS n, ROUND(COALESCE(SUM(net_pnl),0)::numeric,2) AS pnl,
                  COUNT(*) FILTER (WHERE net_pnl > 0) AS wins
           FROM trades WHERE user_id=%s AND status='CLOSED' AND closed_at > NOW() - interval '30 days'
           GROUP BY strategy""", (user_id,))
    recent = db.fetch(
        """SELECT symbol, direction, strategy, result, ROUND(net_pnl::numeric,2) AS net_pnl, signal_score, signal_regime,
                  created_at FROM trades WHERE user_id=%s AND status='CLOSED' ORDER BY closed_at DESC LIMIT 30""",
        (user_id,))
    return json.dumps({"strategy_performance_30d": perf, "recent_trades": recent}, default=str)


def lab_chat(user_id, message: str, mode: str = "chat", http=None) -> str:
    system = ("You are the analyst inside the Apex Trader Pro dashboard. Be concise and concrete. Answer in the user's "
              "language; keep trading terms (LONG, SHORT, TP, SL, ATR) in English. You may not place trades. "
              f"Mode: {mode}. Bot data (JSON): {lab_context(user_id)}")
    return complete(system, message, user_id=user_id, feature=f"lab_{mode}", http=http)
