import re
import uuid
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional

from app.core.symbols import extract_symbol_matches_from_text, extract_symbols_from_text

SectionName = Literal["entry", "config", "exit", "risk"]

# Known dictionary mapping of natural language phrases to exact operators
OPERATOR_SYNONYMS = {
    ">": ["above", "greater than", "over", "higher than", "more than", "bullish than"],
    "<": ["below", "less than", "under", "lower than"],
    "==": ["equals", "is exactly", "same as", "is equal to"],
    "!=": ["not equal", "different than", "does not equal"],
    "crosses_above": [
        "crosses above",
        "breaks out above",
        "cuts above",
        "golden cross",
        "overtakes",
        "crosses over",
    ],
    "crosses_below": [
        "crosses below",
        "breaks down below",
        "cuts below",
        "death cross",
        "crosses under",
    ],
}

INDICATOR_SYNONYMS = {
    "RSI": ["rsi", "relative strength index", "relative strength", "momentum index"],
    "SMA": ["sma", "simple moving average", "moving average", "average"],
    "EMA": ["ema", "exponential moving average", "exponential average"],
    "MACD": ["macd", "moving average convergence divergence"],
    "ADX": ["adx", "average directional index", "trend strength"],
    "ATR": ["atr", "average true range", "volatility"],
    "VWAP": ["vwap", "volume weighted average price"],
    "SUPERTREND": ["supertrend", "super trend"],
    "BBANDS": ["bollinger bands", "bollinger band", "bbands"],
    "STOCH": ["stochastic", "stoch"],
    "CCI": ["cci", "commodity channel index"],
    "ROC": ["roc", "rate of change"],
    "WILLR": ["williams r", "williams %r", "willr"],
    "OBV": ["obv", "on balance volume"],
    "ORB_HIGH": ["orb high", "opening range high"],
    "ORB_LOW": ["orb low", "opening range low"],
}

PRICE_FIELDS = ["close", "open", "high", "low", "volume", "price"]
TIMEFRAME_ALIASES = {
    "1m": ["1m", "1 min", "1 minute", "one minute"],
    "5m": ["5m", "5 min", "5 minute", "five minute"],
    "15m": ["15m", "15 min", "15 minute", "fifteen minute"],
    "30m": ["30m", "30 min", "30 minute", "thirty minute"],
    "1h": ["1h", "1 hour", "60 minute", "60 min", "hourly"],
    "1d": ["1d", "1 day", "daily", "day"],
    "1w": ["1w", "1 week", "weekly", "week"],
}
COMMON_SYMBOL_STOPWORDS = {
    "RSI",
    "SMA",
    "EMA",
    "MACD",
    "ADX",
    "ATR",
    "VWAP",
    "BUY",
    "SELL",
    "AND",
    "OR",
    "ALL",
    "ANY",
    "EXIT",
    "RISK",
    "CONFIG",
    "STRATEGY",
    "LOSS",
    "TARGET",
    "TIME",
}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def extract_parameters(text: str, indicator_name: str) -> List[Any]:
    """Extract numeric parameters attached to or near an indicator."""
    paren_match = re.search(r"\((\d+(?:\.\d+)?(?:,\s*\d+(?:\.\d+)?)*)\)", text)
    if paren_match:
        values: list[Any] = []
        for raw in paren_match.group(1).split(","):
            raw = raw.strip()
            values.append(int(raw) if raw.isdigit() else float(raw))
        return values

    prefix_match = re.search(r"(\d+)(?:-period)?", text)
    if prefix_match:
        return [int(prefix_match.group(1))]

    if indicator_name == "RSI":
        return [14]
    if indicator_name in ["SMA", "EMA"]:
        return [20]
    return []


def resolve_entity(phrase: str) -> Dict[str, Any]:
    """Resolve a phrase to an indicator, price field, or raw value."""
    phrase = phrase.strip().lower()

    if re.match(r"^-?\d+(?:\.\d+)?$", phrase):
        return {"type": "value", "value": float(phrase)}

    for field in PRICE_FIELDS:
        if re.search(r"\b" + re.escape(field) + r"\b", phrase):
            return {"type": "price", "field": "close" if field == "price" else field}

    clean_phrase = re.sub(r"[\d\(\)-]", "", phrase).strip()

    for ind, synonyms in INDICATOR_SYNONYMS.items():
        for syn in synonyms:
            if syn in clean_phrase:
                return {
                    "type": "indicator",
                    "name": ind,
                    "params": extract_parameters(phrase, ind),
                }

    cleaned_name = re.sub(r"[\d\(\)]", "", phrase).strip().upper()
    if cleaned_name:
        return {
            "type": "indicator",
            "name": cleaned_name,
            "params": extract_parameters(phrase, cleaned_name),
        }

    return {"type": "value", "value": 0.0}


def parse_natural_language_condition(sentence: str) -> Optional[Dict[str, Any]]:
    """Parse a single natural language rule into a structured Condition dict."""
    sentence = sentence.lower().strip()
    if not sentence:
        return None

    math_ops = ["crosses_above", "crosses_below", "<=", ">=", "==", "!=", "<", ">", "="]
    for op in math_ops:
        if f" {op} " in sentence or sentence.find(op) != -1:
            parts = sentence.split(op, 1)
            if len(parts) == 2:
                right = resolve_entity(parts[1])
                operator = "==" if op == "=" else op
                if right.get("type") == "value" and operator in ("crosses_above", "crosses_below"):
                    operator = ">" if operator == "crosses_above" else "<"
                return {
                    "left": resolve_entity(parts[0]),
                    "operator": operator,
                    "right": right,
                }

    best_op = None
    best_syn = ""
    for op, synonyms in OPERATOR_SYNONYMS.items():
        for syn in synonyms:
            if syn in sentence and len(syn) > len(best_syn):
                best_syn = syn
                best_op = op

    if not best_op:
        return None

    parts = sentence.split(best_syn, 1)
    if len(parts) != 2:
        return None

    right = resolve_entity(parts[1])
    operator = best_op
    if right.get("type") == "value" and operator in ("crosses_above", "crosses_below"):
        operator = ">" if operator == "crosses_above" else "<"

    return {"left": resolve_entity(parts[0]), "operator": operator, "right": right}


def parse_entry_query(query: str) -> List[Dict[str, Any]]:
    sentences = re.split(r"\s+and\s+|\s+or\s+|\n+|,", query, flags=re.IGNORECASE)
    conditions = []
    for sentence in sentences:
        parsed = parse_natural_language_condition(sentence.strip())
        if parsed:
            parsed["id"] = _new_id("cond")
            conditions.append(parsed)
    return conditions


def _extract_strategy_name(query: str) -> Optional[str]:
    quoted = re.search(r'["\']([^"\']{3,100})["\']', query)
    if quoted:
        return quoted.group(1).strip()

    named = re.search(r"(?:named|called)\s+([a-z0-9][a-z0-9\s\-_]{2,80})", query, flags=re.IGNORECASE)
    if named:
        candidate = re.split(r"\bwith\b|\bfor\b|\bon\b", named.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
        return candidate.strip(" ,.-")
    return None


def _extract_timeframe(query: str) -> Optional[str]:
    text = query.lower()
    for timeframe, aliases in TIMEFRAME_ALIASES.items():
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", text):
                return timeframe
    return None


def _extract_symbols(query: str) -> List[str]:
    if re.search(r"\bnifty\s*50\b", query, flags=re.IGNORECASE):
        return ["NIFTY50"]

    scoped_segments = re.findall(
        r"(?:for|symbols?|stocks?|tickers?)\s+(?:are\s+)?([A-Za-z0-9,\s&.-]+?)(?=\s+(?:on|from|between|with)\b|$)",
        query,
        flags=re.IGNORECASE,
    )

    matches: list[str] = []
    for segment in scoped_segments or [query]:
        for symbol in extract_symbols_from_text(segment):
            if symbol not in matches and symbol not in COMMON_SYMBOL_STOPWORDS:
                matches.append(symbol)
    return matches


def _extract_date_range(query: str) -> Dict[str, str]:
    payload: Dict[str, str] = {}
    iso_dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", query)
    if len(iso_dates) >= 2:
        payload["backtest_from"] = iso_dates[0]
        payload["backtest_to"] = iso_dates[1]
        return payload

    range_match = re.search(
        r"last\s+(\d+)\s+(day|days|week|weeks|month|months|year|years)",
        query,
        flags=re.IGNORECASE,
    )
    if range_match:
        count = int(range_match.group(1))
        unit = range_match.group(2).lower()
        days = count
        if "week" in unit:
            days = count * 7
        elif "month" in unit:
            days = count * 30
        elif "year" in unit:
            days = count * 365
        end = date.today()
        start = end - timedelta(days=days)
        payload["backtest_from"] = start.isoformat()
        payload["backtest_to"] = end.isoformat()
    return payload


def parse_config_query(query: str) -> Dict[str, Any]:
    config: Dict[str, Any] = {}
    name = _extract_strategy_name(query)
    if name:
        config["name"] = name

    timeframe = _extract_timeframe(query)
    if timeframe:
        config["timeframe"] = timeframe

    symbol_matches = extract_symbol_matches_from_text(query)
    symbols = [match["symbol"] for match in symbol_matches] or _extract_symbols(query)
    if symbols:
        config["symbols"] = symbols

    if re.search(r"\bequity|equities|cash\b", query, flags=re.IGNORECASE):
        config["asset_type"] = "EQUITY"

    config.update(_extract_date_range(query))

    result: Dict[str, Any] = {"config": config}
    if symbol_matches:
        result["symbol_matches"] = symbol_matches
    return result


def _extract_percent(text: str) -> Optional[float]:
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))
    return None


def _extract_time(text: str) -> Optional[str]:
    match = re.search(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b", text)
    if match:
        return f"{int(match.group(1)):02d}:{match.group(2)}"
    return None


def _extract_logic(text: str) -> Optional[str]:
    lowered = text.lower()
    if " all " in f" {lowered} " or "all exit" in lowered or "all conditions" in lowered:
        return "ALL"
    if " any " in f" {lowered} " or "any exit" in lowered or "any condition" in lowered:
        return "ANY"
    return None


def _parse_exit_rule(sentence: str) -> Optional[Dict[str, Any]]:
    text = sentence.strip().lower()
    if not text:
        return None

    if "stop loss" in text or "stoploss" in text:
        percent = _extract_percent(text)
        if percent is not None:
            return {
                "type": "stoploss",
                "id": _new_id("exit"),
                "percent": percent,
                "priority": 1,
                "trailing": "trailing" in text,
            }

    if "target" in text or "take profit" in text or "profit target" in text:
        percent = _extract_percent(text)
        if percent is not None:
            return {
                "type": "target",
                "id": _new_id("exit"),
                "percent": percent,
                "priority": 1,
            }

    if "trailing" in text:
        percent = _extract_percent(text)
        if percent is not None:
            activation_match = re.search(
                r"(?:activate(?:s|d)?|after|once|at)\s+(?:profit\s+)?(\d+(?:\.\d+)?)\s*%",
                text,
            )
            rule: Dict[str, Any] = {
                "type": "trailing",
                "id": _new_id("exit"),
                "percent": percent,
                "priority": 1,
            }
            if activation_match:
                rule["activationPercent"] = float(activation_match.group(1))
            return rule

    if "time exit" in text or "exit at" in text or text.startswith("at "):
        exit_time = _extract_time(text)
        if exit_time:
            return {
                "type": "time",
                "id": _new_id("exit"),
                "time": exit_time,
                "priority": 1,
            }

    condition = parse_natural_language_condition(sentence)
    if condition:
        condition["id"] = _new_id("cond")
        return {
            "type": "indicator_exit",
            "id": _new_id("exit"),
            "condition": condition,
            "priority": 1,
        }

    return None


def parse_exit_query(query: str) -> Dict[str, Any]:
    sentences = re.split(r"\n+|,", query)
    rules: list[Dict[str, Any]] = []
    for sentence in sentences:
        fragments = re.split(r"\s+\band\b\s+", sentence, flags=re.IGNORECASE)
        for fragment in fragments:
            rule = _parse_exit_rule(fragment.strip())
            if rule:
                rules.append(rule)

    for index, rule in enumerate(rules, start=1):
        rule["priority"] = index

    payload: Dict[str, Any] = {"exit_rules": rules}
    logic = _extract_logic(query)
    if logic:
        payload["exit_logic"] = logic
    return payload


def parse_risk_query(query: str) -> Dict[str, Any]:
    text = query.lower()
    risk: Dict[str, Any] = {
        "max_trades_per_day": 0,
        "max_loss_per_day": 0.0,
        "quantity": 1,
        "reentry_after_sl": False,
        "max_concurrent_trades": 1,
        "partial_exit_pct": None,
    }

    trades = re.search(r"max\s+(\d+)\s+trades?(?:\s+per\s+day|\s+a\s+day)?", text)
    if trades:
        risk["max_trades_per_day"] = int(trades.group(1))
    elif "no trade limit" in text or "no max trades" in text:
        risk["max_trades_per_day"] = 0

    loss = re.search(r"(?:max|daily)\s+loss(?:\s+of)?\s+(?:rs\.?|₹|inr)?\s*(\d+(?:\.\d+)?)", text)
    if loss:
        risk["max_loss_per_day"] = float(loss.group(1))
    elif "no loss cap" in text or "no daily loss cap" in text:
        risk["max_loss_per_day"] = 0.0

    quantity = re.search(r"\b(?:quantity|qty|size)\s+(?:of\s+)?(\d+)\b", text)
    if quantity:
        risk["quantity"] = int(quantity.group(1))

    concurrent = re.search(r"max\s+(?:open\s+positions|concurrent\s+trades?)\s+(\d+)", text)
    if concurrent:
        risk["max_concurrent_trades"] = int(concurrent.group(1))

    partial = re.search(r"partial\s+exit(?:\s+at\s+target)?\s+(\d+(?:\.\d+)?)\s*%", text)
    if partial:
        risk["partial_exit_pct"] = float(partial.group(1))

    if "re-entry" in text or "reentry" in text:
        risk["reentry_after_sl"] = not bool(
            re.search(r"(?:disable|no|without)\s+(?:re-entry|reentry)", text)
        )

    return risk


def parse_section_query(section: SectionName, query: str) -> Dict[str, Any]:
    if section == "entry":
        return {"conditions": parse_entry_query(query)}
    if section == "config":
        return parse_config_query(query)
    if section == "exit":
        return parse_exit_query(query)
    if section == "risk":
        return {"risk": parse_risk_query(query)}
    raise ValueError(f"Unsupported section '{section}'")
