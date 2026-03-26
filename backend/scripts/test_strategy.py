#!/usr/bin/env python3
"""
test_strategy.py - CLI Test Harness for ZenScript Strategies

Usage:
    python backend/scripts/test_strategy.py "IF RSI(14) < 30: BUY"
    python backend/scripts/test_strategy.py --file strategy.zs
    python backend/scripts/test_strategy.py --validate "IF RSI(14) < 30: BUY"
    python backend/scripts/test_strategy.py --backtest "IF RSI(14) < 30: BUY" --symbol RELIANCE
"""

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime, date, timedelta

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.zenscript import (
    parse_zenscript,
    compile_zenscript,
    validate_zenscript,
    ParseError,
    ZenScriptParser,
)
from app.core.backtest_engine import (
    load_equity_candles,
    compute_indicators,
    simulate_strategy,
)


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def print_success(msg: str):
    """Print success message."""
    print(f"✅ {msg}")


def print_error(msg: str):
    """Print error message."""
    print(f"❌ {msg}")


def print_warning(msg: str):
    """Print warning message."""
    print(f"⚠️  {msg}")


def print_info(msg: str):
    """Print info message."""
    print(f"ℹ️  {msg}")


def print_ast(ast):
    """Print AST in a readable format."""
    print(f"\n📋 Strategy: {ast.name}")
    print(f"\n📝 Raw Script:")
    print(f"   {ast.raw_script}")

    print(f"\n📊 Entry Conditions:")
    for i, stmt in enumerate(ast.entry_statements, 1):
        print(f"   {i}. IF ", end="")
        conditions = []
        for cond in stmt.conditions.conditions:
            if hasattr(cond, "indicator"):
                params = ", ".join(str(p) for p in cond.params)
                conditions.append(
                    f"{cond.indicator.value}({params}) {cond.comparison.value} {cond.value}"
                )
        print(" AND ".join(conditions))
        print(f"      THEN {stmt.action.action_type.value}")

    if ast.exit_statement and ast.exit_statement.conditions:
        print(f"\n🚪 Exit Conditions:")
        for cond in ast.exit_statement.conditions:
            if cond.exit_type.value == "AT":
                print(f"   - Time: {cond.time}")
            elif cond.exit_type.value == "TARGET":
                print(f"   - Target: {cond.value}%")
            elif cond.exit_type.value == "STOPLOSS":
                print(f"   - Stop Loss: {cond.value}%")
            elif cond.exit_type.value == "TRAILING":
                print(f"   - Trailing Stop: {cond.value}%")


def print_compiled(compiled):
    """Print compiled strategy."""
    print(f"\n📋 Compiled Strategy: {compiled.name}")
    print(f"\n📊 Entry Conditions (compiled):")

    if compiled.buy_conditions:
        for i, cond in enumerate(compiled.buy_conditions, 1):
            print(
                f"   BUY {i}: {cond.indicator}({cond.params}) {cond.comparison} {cond.value}"
            )
            if cond.ref_indicator:
                print(f"          vs {cond.ref_indicator}({cond.ref_params})")

    if compiled.sell_conditions:
        for i, cond in enumerate(compiled.sell_conditions, 1):
            print(
                f"   SELL {i}: {cond.indicator}({cond.params}) {cond.comparison} {cond.value}"
            )
            if cond.ref_indicator:
                print(f"          vs {cond.ref_indicator}({cond.ref_params})")

    if compiled.short_conditions:
        for i, cond in enumerate(compiled.short_conditions, 1):
            print(
                f"   SHORT {i}: {cond.indicator}({cond.params}) {cond.comparison} {cond.value}"
            )

    if not any(
        [compiled.buy_conditions, compiled.sell_conditions, compiled.short_conditions]
    ):
        print("   (No entry conditions)")

    print(f"\n🚪 Exit Conditions:")
    exit_dict = compiled.exit_conditions.to_dict()
    for key, value in exit_dict.items():
        if value is not None:
            print(f"   - {key}: {value}")


def validate_strategy(code: str):
    """Validate a ZenScript strategy."""
    print_header("Validating ZenScript Strategy")
    print(f"\n📝 Code:\n{code}")

    errors = validate_zenscript(code)

    if not errors:
        print_success("No validation errors found!")
        return True
    else:
        print_error(f"Found {len(errors)} error(s):")
        parser = ZenScriptParser()
        for err in errors:
            print(f"\n   {parser.format_error(err)}")
        return False


def parse_strategy(code: str):
    """Parse and display AST."""
    print_header("Parsing ZenScript Strategy")
    print(f"\n📝 Code:\n{code}")

    try:
        ast = parse_zenscript(code)
        print_success("Parsed successfully!")
        print_ast(ast)
        return ast
    except ParseError as e:
        parser = ZenScriptParser()
        print_error(f"Parse error: {parser.format_error(e)}")
        return None


def compile_strategy(code: str):
    """Parse, compile and display compiled strategy."""
    print_header("Compiling ZenScript Strategy")
    print(f"\n📝 Code:\n{code}")

    try:
        compiled = compile_zenscript(code)
        print_success("Compiled successfully!")
        print_compiled(compiled)
        return compiled
    except ParseError as e:
        parser = ZenScriptParser()
        print_error(f"Compilation error: {parser.format_error(e)}")
        return None


def quick_backtest(code: str, symbol: str = "RELIANCE", days: int = 90):
    """Run a quick backtest on the strategy."""
    print_header("Quick Backtest")
    print(f"\n📝 Strategy:\n{code}")
    print(f"\n📈 Symbol: {symbol}")
    print(f"📅 Period: Last {days} days")

    # Parse and compile
    try:
        compiled = compile_zenscript(code)
    except ParseError as e:
        parser = ZenScriptParser()
        print_error(f"Compilation error: {parser.format_error(e)}")
        return

    # Load data (quick mode - limited candles)
    to_date = date.today()
    from_date = to_date - timedelta(days=days)

    print(f"\n📥 Loading data from {from_date} to {to_date}...")
    df = load_equity_candles(symbol, "1D", from_date, to_date)

    if df.empty:
        print_error(f"No data found for {symbol}")
        print_info("Available data directories:")
        # Use the same path resolution as backtest_engine.py
        data_dir = Path(__file__).parent.parent / "data" / "candles" / "NIFTY500"
        if data_dir.exists():
            for d in sorted(data_dir.iterdir())[:10]:
                print(f"   - {d.name}/")
        return

    print_success(f"Loaded {len(df)} candles")

    # Compute indicators
    print("\n🔢 Computing indicators...")

    # Build conditions for backtest engine
    conditions = []
    for cond in compiled.buy_conditions:
        conditions.append(
            {
                "indicator": cond.indicator,
                "params": {
                    k: v
                    for k, v in zip(
                        ["period", "fast", "slow", "multiplier", "std_dev"], cond.params
                    )
                },
                "logic": "AND",
            }
        )

    df = compute_indicators(df, conditions)
    print_success("Indicators computed")

    # Build strategy dict for backtest
    strategy = compiled.to_strategy_dict()
    strategy["strategy_id"] = "test"
    strategy["symbol"] = symbol
    strategy["asset_type"] = "EQUITY"
    strategy["timeframe"] = "1D"
    strategy["risk"] = {
        "max_trades_per_day": 3,
        "max_loss_per_day": 5000,
        "quantity_lots": 1,
        "lot_size": 1,
        "reentry_after_sl": False,
    }

    # Run simulation
    print("\n🔄 Running simulation...")
    trades = simulate_strategy(df, strategy)

    # Print results
    print_header("Backtest Results")

    if not trades:
        print_warning("No trades generated")
        return

    print(f"\n📊 Trade Statistics:")
    print(f"   Total Trades: {len(trades)}")

    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]

    print(f"   Winning Trades: {len(wins)}")
    print(f"   Losing Trades: {len(losses)}")
    print(f"   Win Rate: {len(wins) / len(trades) * 100:.1f}%")

    total_pnl = sum(t["pnl"] for t in trades)
    print(f"\n💰 Total P&L: ₹{total_pnl:,.2f}")

    if wins:
        print(f"   Best Trade: ₹{max(t['pnl'] for t in wins):,.2f}")
    if losses:
        print(f"   Worst Trade: ₹{min(t['pnl'] for t in losses):,.2f}")

    print(f"\n📋 Trade Details:")
    for t in trades[:10]:  # Show first 10
        print(
            f"   {t['trade_no']}. {t['entry_time'][:10]} → {t['exit_time'][:10]}: "
            f"₹{t['pnl']:,.2f} ({t['pnl_pct']}%) [{t['exit_reason']}]"
        )

    if len(trades) > 10:
        print(f"   ... and {len(trades) - 10} more trades")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="ZenScript Strategy Testing CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "IF RSI(14) < 30: BUY"
  %(prog)s --validate "IF RSI(14) < 30: BUY"
  %(prog)s --compile "IF SMA(20) > SMA(50): BUY"
  %(prog)s --backtest "IF RSI(14) < 30: BUY" --symbol RELIANCE
  %(prog)s --file strategy.zs
        """,
    )

    parser.add_argument("code", nargs="?", help="ZenScript code to test")
    parser.add_argument("--file", "-f", help="Read code from file")
    parser.add_argument("--validate", "-v", action="store_true", help="Validate only")
    parser.add_argument(
        "--parse", "-p", action="store_true", help="Parse only (show AST)"
    )
    parser.add_argument(
        "--compile", "-c", action="store_true", help="Parse and compile"
    )
    parser.add_argument("--backtest", "-b", action="store_true", help="Run backtest")
    parser.add_argument(
        "--symbol", "-s", default="RELIANCE", help="Symbol for backtest"
    )
    parser.add_argument("--days", "-d", type=int, default=90, help="Backtest days")

    args = parser.parse_args()

    # Read code from file or argument
    code = None
    if args.file:
        file_path = Path(args.file)
        if file_path.exists():
            code = file_path.read_text().strip()
            print_info(f"Loaded code from {args.file}")
        else:
            print_error(f"File not found: {args.file}")
            sys.exit(1)
    elif args.code:
        code = args.code.strip()
    else:
        parser.print_help()
        print("\n" + "=" * 60)
        print("Quick Examples:")
        print("=" * 60)
        examples = [
            "IF RSI(14) < 30: BUY",
            "IF RSI(14) > 70: SELL",
            "IF SMA(20) > SMA(50): BUY",
            "IF EMA(9) CROSSES ABOVE EMA(21): BUY",
            "IF RSI(14) < 30 AND RSI(14) > 20: BUY",
        ]
        for ex in examples:
            print(f"  {ex}")
        sys.exit(0)

    # Determine action
    if args.validate:
        validate_strategy(code)
    elif args.parse:
        parse_strategy(code)
    elif args.compile:
        compile_strategy(code)
    elif args.backtest:
        quick_backtest(code, args.symbol, args.days)
    else:
        # Default: parse and compile
        compile_strategy(code)
        print("\n" + "=" * 60)
        print("To run a backtest, add --backtest flag")
        print("=" * 60)


if __name__ == "__main__":
    main()
