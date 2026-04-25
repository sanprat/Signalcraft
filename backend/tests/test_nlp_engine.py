from app.services.nlp_engine import parse_section_query


def test_entry_query_returns_conditions():
    result = parse_section_query("entry", "RSI below 30 and EMA 20 crosses above EMA 50")
    assert len(result["conditions"]) == 2
    assert result["conditions"][0]["operator"] == "<"


def test_config_query_returns_strategy_fields():
    result = parse_section_query(
        "config",
        'Create a strategy named "Momentum Alpha" for RELIANCE and TCS on 15 minute candles from 2025-01-01 to 2025-03-31',
    )
    assert result["config"]["name"] == "Momentum Alpha"
    assert result["config"]["timeframe"] == "15m"
    assert result["config"]["symbols"] == ["RELIANCE", "TCS"]
    assert result["config"]["backtest_from"] == "2025-01-01"
    assert result["config"]["backtest_to"] == "2025-03-31"


def test_config_query_resolves_company_name_aliases():
    result = parse_section_query(
        "config",
        "Create a setup for Infosys and Tata Consultancy on 15 minute candles",
    )
    assert result["config"]["symbols"] == ["INFY", "TCS"]
    assert result["symbol_matches"] == [
        {
            "input": "Infosys",
            "matched_alias": "Infosys",
            "symbol": "INFY",
            "confidence": 100,
        },
        {
            "input": "Tata Consultancy",
            "matched_alias": "Tata Consultancy",
            "symbol": "TCS",
            "confidence": 100,
        },
    ]


def test_exit_query_supports_indicator_exit_and_risk_rules():
    result = parse_section_query(
        "exit",
        "Exit with 2% stop loss, 5% target, trailing stop 1.5% after 3% profit, exit at 15:15, and RSI crosses below 60",
    )
    assert [rule["type"] for rule in result["exit_rules"]] == [
        "stoploss",
        "target",
        "trailing",
        "time",
        "indicator_exit",
    ]
    assert result["exit_rules"][-1]["condition"]["operator"] == "<"


def test_risk_query_returns_all_fields():
    result = parse_section_query(
        "risk",
        "Max 3 trades per day, daily loss 5000, quantity 10, max open positions 2, partial exit 50%, enable re-entry",
    )
    assert result["risk"] == {
        "max_trades_per_day": 3,
        "max_loss_per_day": 5000.0,
        "quantity": 10,
        "reentry_after_sl": True,
        "max_concurrent_trades": 2,
        "partial_exit_pct": 50.0,
    }
