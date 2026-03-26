"""
ZenScript v1 - Domain Specific Language for Trading Strategies

A trading strategy DSL with trading-friendly syntax built on top of Lark parser.

Example Usage:
    from app.core.zenscript import parse_zenscript, compile_zenscript

    # Parse and compile in one step
    strategy = compile_zenscript("IF RSI(14) < 30: BUY")

    # Or parse first, then compile
    ast = parse_zenscript("IF SMA(20) > SMA(50): BUY")
    strategy = interpret(ast)
"""

from .ast_nodes import (
    StrategyNode,
    IfStatement,
    ConditionGroup,
    Condition,
    IndicatorExpr,
    Action,
    ExitStatement,
    ExitCondition,
    CompiledCondition,
    CompiledExit,
    StrategySignal,
    StrategyContext,
    TradeState,
    NodeType,
    LogicalOp,
    ComparisonOp,
    Indicator,
    ActionType,
    ExitType,
)

from .parser import (
    ZenScriptParser,
    ParseError,
    parse_zenscript,
    validate_zenscript,
)

from .interpreter import (
    ZenScriptInterpreter,
    CompiledStrategy,
    compile_zenscript,
    interpret,
)

__all__ = [
    # AST Nodes
    "StrategyNode",
    "IfStatement",
    "ConditionGroup",
    "Condition",
    "IndicatorExpr",
    "Action",
    "ExitStatement",
    "ExitCondition",
    "CompiledCondition",
    "CompiledExit",
    "CompiledStrategy",
    "StrategySignal",
    "StrategyContext",
    "TradeState",
    # Enums
    "NodeType",
    "LogicalOp",
    "ComparisonOp",
    "Indicator",
    "ActionType",
    "ExitType",
    # Parser
    "ZenScriptParser",
    "ParseError",
    "parse_zenscript",
    "validate_zenscript",
    # Interpreter
    "ZenScriptInterpreter",
    "compile_zenscript",
    "interpret",
]
