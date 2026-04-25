"""
Regression tests for the legacy ZenScript parser/compiler.

The product-facing strategy builder remains JSON-first, but these tests keep the
raw ZenScript DSL honest while the UI evolves into a no-code composer.
"""

import sys

sys.path.insert(0, "backend")

from app.core.zenscript import compile_zenscript, parse_zenscript, validate_zenscript


def test_zenscript_parses_simple_rsi_buy_rule():
    script = "IF RSI(14) < 30: BUY"

    errors = validate_zenscript(script)
    ast = parse_zenscript(script)
    compiled = compile_zenscript(script)

    assert errors == []
    assert ast.raw_script == script
    assert len(ast.entry_statements) == 1
    assert len(compiled.buy_conditions) == 1
    assert compiled.buy_conditions[0].to_dict() == {
        "indicator": "RSI",
        "params": {"period": 14},
        "comparison": "<",
        "value": 30.0,
    }


def test_zenscript_compiles_indicator_to_indicator_crossover():
    script = "IF EMA(20) > EMA(50): BUY"

    compiled = compile_zenscript(script)
    condition = compiled.buy_conditions[0].to_dict()

    assert condition["indicator"] == "EMA"
    assert condition["params"] == {"period": 20}
    assert condition["comparison"] == ">"
    assert condition["ref_indicator"] == "EMA"
    assert condition["ref_params"] == [50.0]


def test_zenscript_compiles_exit_rules():
    script = "IF ADX(14) > 25: BUY\nEXIT TARGET 5, SL 2"

    compiled = compile_zenscript(script)

    assert len(compiled.buy_conditions) == 1
    assert compiled.exit_conditions.to_dict() == {
        "time_exit": None,
        "target_pct": 5.0,
        "stoploss_pct": 2.0,
        "trailing_sl_pct": None,
    }
