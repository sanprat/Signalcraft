import re
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process

# Known dictionary mapping of natural language phrases to exact operators
OPERATOR_SYNONYMS = {
    ">": ["above", "greater than", "over", "higher than", "more than", "bullish than"],
    "<": ["below", "less than", "under", "lower than", "drops below"],
    "==": ["equals", "is exactly", "same as", "is equal to"],
    "!=": ["not equal", "different than", "does not equal"],
    "crosses_above": ["crosses above", "breaks out above", "cuts above", "golden cross", "overtakes", "crosses over"],
    "crosses_below": ["crosses below", "drops below", "breaks down below", "cuts below", "death cross", "crosses under"],
}

# Known indicators and price fields
INDICATOR_SYNONYMS = {
    "RSI": ["rsi", "relative strength index", "relative strength", "momentum index"],
    "SMA": ["sma", "simple moving average", "moving average", "average"],
    "EMA": ["ema", "exponential moving average", "exponential average"],
    "MACD": ["macd", "moving average convergence divergence"],
    "ADX": ["adx", "average directional index", "trend strength"],
    "ATR": ["atr", "average true range", "volatility"],
    "VWAP": ["vwap", "volume weighted average price"],
    "BB_UPPER": ["bollinger upper", "upper bollinger band", "upper bb"],
    "BB_LOWER": ["bollinger lower", "lower bollinger band", "lower bb"],
}

PRICE_FIELDS = ["close", "open", "high", "low", "volume", "price"]

def extract_parameters(text: str, indicator_name: str) -> List[Any]:
    """Extract numeric parameters attached to or near an indicator."""
    # Matches RSI(14)
    paren_match = re.search(r"\((\d+(?:,\s*\d+)*)\)", text)
    if paren_match:
        return [int(x.strip()) if x.strip().isdigit() else float(x.strip()) for x in paren_match.group(1).split(",")]
    
    # Matches 14-period RSI or 200 SMA
    prefix_match = re.search(r"(\d+)(?:-period)?", text)
    if prefix_match:
        return [int(prefix_match.group(1))]
        
    # Defaults
    if indicator_name == "RSI": return [14]
    if indicator_name in ["SMA", "EMA"]: return [20]
    return []

def resolve_entity(phrase: str) -> Dict[str, Any]:
    """Resolves a phrase to an indicator, price field, or raw value."""
    phrase = phrase.strip().lower()
    
    # Raw numeric value
    if re.match(r"^-?\d+(?:\.\d+)?$", phrase):
        return {"type": "value", "value": float(phrase)}
        
    # Check Price Fields
    for field in PRICE_FIELDS:
        # Check if the word exists as a distinct token
        if re.search(r'\b' + field + r'\b', phrase):
            return {"type": "price", "field": "close" if field == "price" else field}
        
    # Check Indicators using RapidFuzz
    best_match = None
    best_score = 0
    
    # Clean phrase of numbers to match indicator names
    clean_phrase = re.sub(r"[\d\(\)-]", "", phrase).strip()
    
    for ind, synonyms in INDICATOR_SYNONYMS.items():
        for syn in synonyms:
            # Exact substring match takes priority
            if syn in clean_phrase.lower():
                params = extract_parameters(phrase, ind)
                return {"type": "indicator", "name": ind, "params": params}
                
        match_result = process.extractOne(clean_phrase, synonyms, scorer=fuzz.partial_ratio)
        if match_result and match_result[1] > best_score:
            best_score = match_result[1]
            best_match = ind
            
    if best_match and best_score > 80:
        params = extract_parameters(phrase, best_match)
        return {"type": "indicator", "name": best_match, "params": params}
        
    # Fallback to assuming it's a raw unknown indicator name typed exactly
    cleaned_name = re.sub(r"[\d\(\)]", "", phrase).strip().upper()
    if cleaned_name:
        params = extract_parameters(phrase, cleaned_name)
        return {"type": "indicator", "name": cleaned_name, "params": params}
        
    return {"type": "value", "value": 0}

def parse_natural_language_condition(sentence: str) -> Optional[Dict[str, Any]]:
    """Parses a single natural language rule into a structured Condition dict."""
    sentence = sentence.lower().strip()
    
    best_operator = None
    best_split = None
    best_score = 0
    
    # Try exact exact math operators first
    math_ops = ["crosses_above", "crosses_below", "<=", ">=", "==", "!=", "<", ">", "="]
    for op in math_ops:
        if f" {op} " in sentence or sentence.find(op) != -1:
            parts = sentence.split(op, 1)
            if len(parts) == 2:
                # Map '=' to '==' for schema compatibility
                op_schema = "==" if op == "=" else op
                return {
                    "left": resolve_entity(parts[0]),
                    "operator": op_schema,
                    "right": resolve_entity(parts[1])
                }
    
    # Use fuzzy matching for natural language operators
    best_op = None
    best_syn = ""
    
    for op, synonyms in OPERATOR_SYNONYMS.items():
        for syn in synonyms:
            if syn in sentence:
                if len(syn) > len(best_syn):
                    best_syn = syn
                    best_op = op
                    
    if best_op:
        parts = sentence.split(best_syn, 1)
        return {
            "left": resolve_entity(parts[0]),
            "operator": best_op,
            "right": resolve_entity(parts[1])
        }
                
    # If no operator found, return None
    return None

def parse_query(query: str) -> List[Dict[str, Any]]:
    """Main entrypoint: Converts a block of text into a list of conditions."""
    # Split by common conjunctions (and, or, newlines, commas)
    sentences = re.split(r'\s+and\s+|\s+or\s+|\n+|,', query, flags=re.IGNORECASE)
    
    conditions = []
    for s in sentences:
        s = s.strip()
        if not s: continue
        parsed = parse_natural_language_condition(s)
        if parsed:
            # Generate a frontend-friendly ID
            import uuid
            parsed["id"] = f"cond_{uuid.uuid4().hex[:8]}"
            conditions.append(parsed)
            
    return conditions

