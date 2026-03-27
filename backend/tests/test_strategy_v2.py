"""
Tests for Strategy V2 — JSON-first strategy engine.
"""

import pytest
from datetime import date, timedelta
from typing import List, Dict, Any

# Test imports
import sys

sys.path.insert(0, "backend")

from app.schemas.strategy_v2 import (
    StrategyV2,
    Condition,
    IndicatorRef,
    PriceRef,
    ValueRef,
    MathExpr,
    StopLossRule,
    TargetRule,
    TrailingStopRule,
    TimeExitRule,
    IndicatorExitRule,
    RiskConfig,
    INDICATOR_REGISTRY,
)
from app.core.strategy_engine_v2 import validate_strategy_v2
from app.core.strategy_builder_v2 import (
    StrategyBuilderV2,
    ExecutableStrategy,
    ExpressionEvaluator,
)
from app.core.strategy_engine_v2 import StrategyEngineV2


# ============================================================================
# SCHEMA TESTS
# ============================================================================


class TestIndicatorRegistry:
    """Tests for indicator registry validation."""

    def test_valid_indicator_rsi(self):
        """Test valid RSI indicator."""
        indicator = IndicatorRef(name="RSI", params=[14])
        assert indicator.name == "RSI"
        assert indicator.params == [14]

    def test_valid_indicator_sma(self):
        """Test valid SMA indicator."""
        indicator = IndicatorRef(name="SMA", params=["close", 20])
        assert indicator.name == "SMA"
        assert indicator.params == ["close", 20]

    def test_invalid_indicator_raises_error(self):
        """Test that unknown indicator raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            IndicatorRef(name="INVALID_INDICATOR", params=[14])
        assert "Unknown indicator" in str(exc_info.value)

    def test_all_registry_indicators_valid(self):
        """Test all indicators in registry are valid."""
        for name in INDICATOR_REGISTRY.keys():
            indicator = IndicatorRef(name=name, params=[])
            assert indicator.name == name.upper()


class TestPriceRef:
    """Tests for price reference validation."""

    def test_valid_price_fields(self):
        """Test valid price field values."""
        for field in ["close", "open", "high", "low", "volume"]:
            ref = PriceRef(field=field)
            assert ref.field == field

    def test_invalid_price_field_raises_error(self):
        """Test invalid price field raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            PriceRef(field="invalid_field")
        assert "Invalid price field" in str(exc_info.value)

    def test_price_field_case_insensitive(self):
        """Test price field validation is case insensitive."""
        ref = PriceRef(field="CLOSE")
        assert ref.field == "close"


class TestCondition:
    """Tests for condition validation."""

    def test_simple_condition(self):
        """Test simple condition with indicator and value."""
        cond = Condition(
            left=IndicatorRef(name="RSI", params=[14]),
            operator="<",
            right=ValueRef(value=30),
        )
        assert cond.left.name == "RSI"
        assert cond.operator == "<"
        assert cond.right.value == 30

    def test_math_expression_condition(self):
        """Test condition with math expression."""
        cond = Condition(
            left=PriceRef(field="volume"),
            operator=">",
            right=MathExpr(
                left=IndicatorRef(name="SMA", params=[20, "volume"]),
                operator="*",
                right=1.5,
            ),
        )
        assert cond.left.type == "price"
        assert cond.right.type == "math"
        assert cond.right.operator == "*"


class TestExitRules:
    """Tests for exit rule validation."""

    def test_stoploss_rule(self):
        """Test stop loss rule with priority."""
        rule = StopLossRule(percent=2.0, priority=1)
        assert rule.type == "stoploss"
        assert rule.percent == 2.0
        assert rule.priority == 1

    def test_target_rule(self):
        """Test target rule with priority."""
        rule = TargetRule(percent=5.0, priority=3)
        assert rule.type == "target"
        assert rule.percent == 5.0
        assert rule.priority == 3

    def test_trailing_stop_rule(self):
        """Test trailing stop rule."""
        rule = TrailingStopRule(percent=3.0, priority=2)
        assert rule.type == "trailing"
        assert rule.percent == 3.0

    def test_time_exit_rule(self):
        """Test time exit rule."""
        rule = TimeExitRule(time="15:15", priority=4)
        assert rule.type == "time"
        assert rule.time == "15:15"

    def test_invalid_time_format(self):
        """Test invalid time format raises error."""
        with pytest.raises(ValueError):
            TimeExitRule(time="3:15")  # Should be HH:MM

    def test_exit_rule_priority_order(self):
        """Test exit rules can be sorted by priority."""
        rules = [
            TargetRule(percent=5.0, priority=3),
            StopLossRule(percent=2.0, priority=1),
            TrailingStopRule(percent=3.0, priority=2),
        ]
        sorted_rules = sorted(rules, key=lambda r: r.priority)
        assert sorted_rules[0].priority == 1  # SL first
        assert sorted_rules[1].priority == 2  # Trailing second
        assert sorted_rules[2].priority == 3  # Target third


class TestStrategyV2:
    """Tests for complete Strategy V2 model."""

    def test_minimal_strategy(self):
        """Test minimal valid strategy."""
        strategy = StrategyV2(
            name="Test Strategy",
            symbols=["RELIANCE"],
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator="<",
                    right=ValueRef(value=30),
                )
            ],
            exit_rules=[
                StopLossRule(percent=2.0),
                TargetRule(percent=5.0),
            ],
        )
        assert strategy.name == "Test Strategy"
        assert strategy.symbols == ["RELIANCE"]
        assert strategy.entry_logic == "ALL"  # Default
        assert strategy.exit_logic == "ANY"  # Default

    def test_multi_symbol_strategy(self):
        """Test multi-symbol strategy."""
        strategy = StrategyV2(
            name="Multi Symbol",
            symbols=["RELIANCE", "TCS", "INFY"],
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="SMA", params=["close", 20]),
                    operator=">",
                    right=IndicatorRef(name="SMA", params=["close", 50]),
                )
            ],
            exit_rules=[
                StopLossRule(percent=2.0),
            ],
        )
        assert len(strategy.symbols) == 3
        assert "INFY" in strategy.symbols

    def test_all_logic_entry(self):
        """Test ALL entry logic."""
        strategy = StrategyV2(
            name="All Conditions",
            symbols=["RELIANCE"],
            entry_logic="ALL",
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator="<",
                    right=ValueRef(value=30),
                ),
                Condition(
                    left=PriceRef(field="volume"),
                    operator=">",
                    right=ValueRef(value=1000000),
                ),
            ],
            exit_rules=[StopLossRule(percent=2.0)],
        )
        assert strategy.entry_logic == "ALL"

    def test_any_logic_entry(self):
        """Test ANY entry logic."""
        strategy = StrategyV2(
            name="Any Condition",
            symbols=["RELIANCE"],
            entry_logic="ANY",
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator="<",
                    right=ValueRef(value=30),
                ),
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator=">",
                    right=ValueRef(value=70),
                ),
            ],
            exit_rules=[TargetRule(percent=5.0)],
        )
        assert strategy.entry_logic == "ANY"

    def test_risk_config(self):
        """Test risk configuration."""
        risk = RiskConfig(
            max_trades_per_day=5,
            max_loss_per_day=10000,
            quantity=100,
            reentry_after_sl=True,
        )
        assert risk.max_trades_per_day == 5
        assert risk.reentry_after_sl == True

    def test_fno_strategy_requires_index(self):
        """Test FnO strategy requires index field."""
        with pytest.raises(ValueError) as exc_info:
            StrategyV2(
                name="FnO Test",
                symbols=["NIFTY"],
                asset_type="FNO",
                entry_conditions=[
                    Condition(
                        left=IndicatorRef(name="RSI", params=[14]),
                        operator="<",
                        right=ValueRef(value=30),
                    )
                ],
                exit_rules=[StopLossRule(percent=2.0)],
            )
        assert "FnO strategies require" in str(exc_info.value)


# ============================================================================
# VALIDATION TESTS
# ============================================================================


class TestValidation:
    """Tests for strategy validation."""

    def test_valid_strategy_passes(self):
        """Test valid strategy passes validation."""
        strategy = {
            "name": "Test Strategy",
            "symbols": ["RELIANCE"],
            "entry_conditions": [
                {
                    "left": {"type": "indicator", "name": "RSI", "params": [14]},
                    "operator": "<",
                    "right": {"type": "value", "value": 30},
                }
            ],
            "exit_rules": [
                {"type": "stoploss", "percent": 2.0},
            ],
        }
        result = validate_strategy_v2(strategy)
        assert result["valid"] == True
        assert len(result["errors"]) == 0

    def test_missing_required_field_fails(self):
        """Test missing required field fails validation."""
        strategy = {
            "name": "Test",
            # Missing symbols
        }
        result = validate_strategy_v2(strategy)
        assert result["valid"] == False
        assert any("symbols" in e for e in result["errors"])

    def test_empty_symbols_fails(self):
        """Test empty symbols list fails validation."""
        strategy = {
            "name": "Test",
            "symbols": [],
            "entry_conditions": [],
            "exit_rules": [],
        }
        result = validate_strategy_v2(strategy)
        assert result["valid"] == False

    def test_unknown_indicator_fails(self):
        """Test unknown indicator fails validation."""
        strategy = {
            "name": "Test",
            "symbols": ["RELIANCE"],
            "entry_conditions": [
                {
                    "left": {"type": "indicator", "name": "INVALID", "params": []},
                    "operator": "<",
                    "right": {"type": "value", "value": 30},
                }
            ],
            "exit_rules": [
                {"type": "stoploss", "percent": 2.0},
            ],
        }
        result = validate_strategy_v2(strategy)
        assert result["valid"] == False
        assert any("INVALID" in e for e in result["errors"])


# ============================================================================
# BUILDER TESTS
# ============================================================================


class TestStrategyBuilder:
    """Tests for StrategyBuilderV2."""

    def test_build_minimal_strategy(self):
        """Test building minimal strategy."""
        strategy = StrategyV2(
            name="Test",
            symbols=["RELIANCE"],
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator="<",
                    right=ValueRef(value=30),
                )
            ],
            exit_rules=[StopLossRule(percent=2.0)],
        )

        builder = StrategyBuilderV2()
        executable = builder.build(strategy)

        assert isinstance(executable, ExecutableStrategy)
        assert executable.name == "Test"
        assert executable.symbols == ["RELIANCE"]
        assert executable.entry_logic == "ALL"

    def test_exit_rules_sorted_by_priority(self):
        """Test exit rules are sorted by priority."""
        strategy = StrategyV2(
            name="Test",
            symbols=["RELIANCE"],
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator="<",
                    right=ValueRef(value=30),
                )
            ],
            exit_rules=[
                TargetRule(percent=5.0, priority=3),
                StopLossRule(percent=2.0, priority=1),
                TrailingStopRule(percent=3.0, priority=2),
            ],
        )

        builder = StrategyBuilderV2()
        executable = builder.build(strategy)

        # Check sorted by priority
        priorities = [r.priority for r in executable.exit_rules]
        assert priorities == sorted(priorities)
        assert executable.exit_rules[0].rule_type == "stoploss"  # priority=1


# ============================================================================
# EXPRESSION EVALUATOR TESTS
# ============================================================================


class TestExpressionEvaluator:
    """Tests for ExpressionEvaluator."""

    def test_evaluate_value_ref(self):
        """Test evaluating a value reference."""
        import pandas as pd

        df = pd.DataFrame(
            {
                "close": [100, 101, 102],
                "open": [99, 100, 101],
                "high": [102, 103, 104],
                "low": [98, 99, 100],
                "volume": [1000, 1100, 1200],
            }
        )

        evaluator = ExpressionEvaluator(df)

        # Test ValueRef
        val = evaluator.evaluate(ValueRef(value=30), 0)
        assert val == 30.0

    def test_evaluate_price_ref(self):
        """Test evaluating a price reference."""
        import pandas as pd

        df = pd.DataFrame(
            {
                "close": [100.5, 101.5, 102.5],
                "open": [99.0, 100.0, 101.0],
                "high": [102.0, 103.0, 104.0],
                "low": [98.0, 99.0, 100.0],
                "volume": [1000, 1100, 1200],
            }
        )

        evaluator = ExpressionEvaluator(df)

        assert evaluator.evaluate(PriceRef(field="close"), 0) == 100.5
        assert evaluator.evaluate(PriceRef(field="volume"), 1) == 1100

    def test_evaluate_indicator_ref(self):
        """Test evaluating an indicator reference."""
        import pandas as pd

        df = pd.DataFrame(
            {
                "close": [
                    100.0,
                    101.0,
                    102.0,
                    103.0,
                    104.0,
                    105.0,
                    106.0,
                    107.0,
                    108.0,
                    109.0,
                    110.0,
                    111.0,
                    112.0,
                    113.0,
                    114.0,
                    115.0,
                    116.0,
                    117.0,
                    118.0,
                    119.0,
                    120.0,
                ],
                "open": [99.0] * 21,
                "high": [101.0] * 21,
                "low": [99.0] * 21,
                "volume": [1000] * 21,
            }
        )

        evaluator = ExpressionEvaluator(df)

        # Test SMA indicator (params: period, field)
        sma_val = evaluator.evaluate(IndicatorRef(name="SMA", params=[20, "close"]), 20)
        assert sma_val > 0  # Should have computed value

        # Test EMA indicator (params: period, field)
        ema_val = evaluator.evaluate(IndicatorRef(name="EMA", params=[10, "close"]), 20)
        assert ema_val > 0


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestStrategyEngine:
    """Integration tests for StrategyEngineV2."""

    def test_engine_initialization(self):
        """Test engine can be initialized."""
        engine = StrategyEngineV2()
        assert engine is not None
        assert hasattr(engine, "builder")

    def test_date_range_calculation(self):
        """Test date range calculation."""
        engine = StrategyEngineV2()

        strategy = StrategyV2(
            name="Test",
            symbols=["RELIANCE"],
            entry_conditions=[
                Condition(
                    left=IndicatorRef(name="RSI", params=[14]),
                    operator="<",
                    right=ValueRef(value=30),
                )
            ],
            exit_rules=[StopLossRule(percent=2.0)],
        )

        from_date, to_date = engine._get_date_range(strategy, "quick")
        assert to_date == date.today()
        assert (to_date - from_date).days == 180

        from_date, to_date = engine._get_date_range(strategy, "full")
        assert (to_date - from_date).days >= 365 * 2  # At least 2 years


# ============================================================================
# TEST UTILITIES
# ============================================================================


def create_sample_strategy(
    symbols: List[str] = None,
    entry_logic: str = "ALL",
    exit_logic: str = "ANY",
) -> StrategyV2:
    """Create a sample strategy for testing."""
    if symbols is None:
        symbols = ["RELIANCE"]

    return StrategyV2(
        name="Sample Strategy",
        symbols=symbols,
        timeframe="1d",
        entry_logic=entry_logic,
        entry_conditions=[
            Condition(
                left=IndicatorRef(name="RSI", params=[14]),
                operator="<",
                right=ValueRef(value=30),
            ),
            Condition(
                left=PriceRef(field="close"),
                operator=">",
                right=IndicatorRef(name="SMA", params=[20, "close"]),
            ),
        ],
        exit_logic=exit_logic,
        exit_rules=[
            StopLossRule(percent=2.0, priority=1),
            TargetRule(percent=5.0, priority=3),
            TrailingStopRule(percent=3.0, priority=2),
        ],
        risk=RiskConfig(
            max_trades_per_day=3,
            max_loss_per_day=5000,
            quantity=100,
        ),
    )


# ============================================================================
# RUN TESTS
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
