"""
ZenScript Parser

Parses ZenScript DSL code into an AST using Lark.
Provides friendly error messages for common mistakes.
"""

import logging
from pathlib import Path
from typing import Optional, List, Union
from dataclasses import dataclass

from lark import (
    Lark,
    Tree,
    Token,
    UnexpectedInput,
    UnexpectedCharacters,
    UnexpectedToken,
)
from lark.exceptions import VisitError

from .ast_nodes import (
    ASTNode,
    StrategyNode,
    IfStatement,
    ConditionGroup,
    Condition,
    IndicatorExpr,
    Action,
    ExitStatement,
    ExitCondition,
    ActionType,
    ComparisonOp,
    LogicalOp,
    Indicator,
    ExitType,
)

logger = logging.getLogger(__name__)


# Error message mappings for friendly feedback
ERROR_MESSAGES = {
    "missing_colon": "You forgot a colon (:) at the end of the IF statement",
    "missing_condition": "You need a condition after IF. Example: IF RSI(14) < 30",
    "missing_action": "You need an action after the colon. Use BUY or SELL",
    "missing_indicator_params": "Indicators need parameters. Example: RSI(14), SMA(20)",
    "invalid_indicator": "Unknown indicator. Available: RSI, SMA, EMA, SUPERTREND, MACD, BBANDS, ADX, CCI, STOCH, ATR",
    "invalid_comparison": "Invalid comparison. Use: <, >, <=, >=, ==, !=",
    "missing_value": "You need a value to compare. Example: RSI(14) < 30",
    "invalid_action": "Invalid action. Use: BUY, SELL, EXIT, SHORT, COVER",
    "mismatched_parens": "Unmatched parentheses. Check your indicator parameters.",
    "unexpected_token": "Unexpected token. Check your syntax.",
    "empty_strategy": "Your strategy is empty. Add some conditions like: IF RSI(14) < 30: BUY",
    "invalid_time": "Invalid time format. Use: HH:MM or HH:MM:SS. Example: 15:15",
    "invalid_number": "Invalid number format. Use digits only. Example: 30, 14.5, -5",
    "and_or_format": "For multiple conditions, use: IF RSI(14) < 30 AND RSI(14) > 70: BUY",
}


class ParseError(Exception):
    """Structured parse error with helpful message."""

    def __init__(
        self,
        message: str,
        line: Optional[int] = None,
        column: Optional[int] = None,
        unexpected_token: Optional[str] = None,
        expected: Optional[List[str]] = None,
        hint: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column
        self.unexpected_token = unexpected_token
        self.expected = expected
        self.hint = hint


class ZenScriptParser:
    """
    Parser for ZenScript v1 DSL.

    Usage:
        parser = ZenScriptParser()
        ast = parser.parse("IF RSI(14) < 30: BUY")
        strategy = parser.compile("IF RSI(14) < 30: BUY")
    """

    # Grammar definition - simple and working
    GRAMMAR = r"""
        start: (statement | NEWLINE | COMMENT)*
        
        statement: if_statement
                 | exit_statement
                 | assignment
                  
        if_statement: "IF" condition (LOGICAL_OP condition)* ":" entry_action
        
        condition: expr
        
        expr: func_call COMPARISON NUMBER
            | func_call COMPARISON func_call
            | price_ref COMPARISON NUMBER
            | price_ref COMPARISON func_call
            | "(" condition ")"
        
        func_call: NAME "(" NUMBER ("," NUMBER)* ")"
        
        price_ref: NAME
                 | IDENTIFIER
        
        entry_action: TRADE_ACTION
                   | TRADE_ACTION "AT" TIME
             
        exit_statement: "EXIT" exit_condition (","? exit_condition)*
        
        exit_condition: AT TIME
                      | TARGET NUMBER
                      | SL NUMBER
                      | STOPLOSS NUMBER
                      | TRAILING NUMBER
        
        AT: "AT"
        TARGET: "TARGET"
        SL: "SL"
        STOPLOSS: "STOPLOSS"
        TRAILING: "TRAILING"
        
        assignment: NAME "=" value
        
        value: NUMBER
              | STRING
              | NAME
        
        COMMENT: /#.*/
        NEWLINE: /\n+/
        
        TRADE_ACTION: "BUY" | "SELL" | "SHORT" | "COVER"
        LOGICAL_OP: "AND" | "OR"
        COMPARISON: "<" | ">" | "<=" | ">=" | "==" | "!="
        TIME: /\d{1,2}:\d{2}(:\d{2})?/
        NUMBER: /-?\d+(\.\d+)?/
        NAME: /[A-Z][A-Z0-9]*/
        IDENTIFIER: /[a-z][a-z0-9_]*/
        STRING: /"[^"]*"|'[^']*'/
        
        %ignore COMMENT
        %ignore /\s+/
    """

    def __init__(self):
        """Initialize the parser with the ZenScript grammar."""
        self.parser = Lark(
            self.GRAMMAR,
            parser="lalr",
            start="start",
        )
        self._valid_indicators = {
            "RSI",
            "SMA",
            "EMA",
            "SUPERTREND",
            "MACD",
            "BBANDS",
            "ADX",
            "CCI",
            "STOCH",
            "ATR",
            "VWAP",
        }
        self._valid_price_data = {
            "CLOSE",
            "OPEN",
            "HIGH",
            "LOW",
            "VOLUME",
            "close",
            "open",
            "high",
            "low",
            "volume",
        }
        self._valid_actions = {"BUY", "SELL", "EXIT", "SHORT", "COVER"}

    def parse(self, code: str) -> StrategyNode:
        """
        Parse ZenScript code into an AST.

        Args:
            code: ZenScript strategy code

        Returns:
            StrategyNode: The root AST node

        Raises:
            ParseError: If parsing fails with helpful error message
        """
        if not code or not code.strip():
            raise ParseError(
                message=ERROR_MESSAGES["empty_strategy"],
                hint="Start with a condition like: IF RSI(14) < 30: BUY",
            )

        try:
            tree = self.parser.parse(code)
            return self._build_ast(tree, code)
        except UnexpectedCharacters as e:
            return self._handle_unexpected_character(e, code)
        except UnexpectedToken as e:
            return self._handle_unexpected_token(e, code)
        except UnexpectedInput as e:
            return self._handle_unexpected_input(e, code)
        except Exception as e:
            logger.error(f"Parse error: {e}")
            raise ParseError(
                message=f"Parsing failed: {str(e)}", hint="Check your syntax for typos"
            )

    def _build_ast(self, tree: Tree, raw_code: str) -> StrategyNode:
        """Build AST from parse tree."""
        strategy = StrategyNode()
        strategy.raw_script = raw_code

        for child in tree.children:
            if isinstance(child, Tree):
                # Skip comment/newline nodes
                if child.data in ("comment", "newline", None):
                    continue
                if child.data == "statement":
                    # statement contains the actual statement
                    for stmt_child in child.children:
                        if isinstance(stmt_child, Tree):
                            if stmt_child.data == "if_statement":
                                stmt = self._build_if_statement(stmt_child)
                                strategy.add_entry(stmt)
                            elif stmt_child.data == "exit_statement":
                                stmt = self._build_exit_statement(stmt_child)
                                strategy.set_exit(stmt)
                elif child.data == "if_statement":
                    stmt = self._build_if_statement(child)
                    strategy.add_entry(stmt)
                elif child.data == "exit_statement":
                    stmt = self._build_exit_statement(child)
                    strategy.set_exit(stmt)

        return strategy

    def _build_if_statement(self, tree: Tree) -> IfStatement:
        """Build an IF statement from parse tree."""
        conditions = ConditionGroup()
        action = None

        for child in tree.children:
            if isinstance(child, Tree):
                if child.data == "condition":
                    # Condition contains expr
                    for c2 in child.children:
                        if isinstance(c2, Tree) and c2.data == "expr":
                            cond = self._build_expr(c2)
                            conditions.add_condition(cond)
                elif child.data in ("action", "entry_action"):
                    action = self._build_action(child)

        return IfStatement(conditions, action)

    def _build_condition(self, tree: Tree) -> Condition:
        """Build a condition from parse tree."""
        for child in tree.children:
            if isinstance(child, Tree) and child.data == "expr":
                return self._build_expr(child)
        return Condition(None)

    def _build_expr(self, tree: Tree) -> IndicatorExpr:
        """Build an indicator expression from expr node."""
        indicator_name = None
        params = []
        comparison = "<"
        value = 0.0
        ref_indicator = None
        ref_params = []

        # Process tree children
        for child in tree.children:
            if isinstance(child, Tree):
                if child.data == "func_call":
                    if indicator_name is None:
                        indicator_name, params = self._parse_func_call(child)
                    else:
                        ref_indicator, ref_params = self._parse_func_call(child)
                elif child.data == "price_ref":
                    # Handle price_ref (price comparison)
                    for pr_child in child.children:
                        if hasattr(pr_child, "type"):
                            id_name = str(pr_child).upper()
                            if indicator_name is None:
                                indicator_name = id_name
                                params = []
                            else:
                                ref_indicator = id_name
            elif hasattr(child, "type"):
                if child.type == "COMPARISON":
                    comparison = str(child)
                elif child.type == "NUMBER":
                    value = float(child)

        return IndicatorExpr(
            indicator=indicator_name or "RSI",
            params=params,
            comparison=comparison,
            value=value,
            ref_indicator=ref_indicator,
            ref_params=ref_params,
        )

    def _parse_func_call(self, tree: Tree) -> tuple:
        """Parse a function call like RSI(14)."""
        name = None
        params = []

        for child in tree.children:
            if isinstance(child, Token):
                if child.type == "NAME" and str(child) in self._valid_indicators:
                    name = str(child)
                elif child.type == "NUMBER":
                    params.append(float(child))

        return name or "RSI", params

    def _build_action(self, tree: Tree) -> Action:
        """Build an action from parse tree."""
        action_type = "BUY"
        time = None

        tokens = [c for c in tree.children if isinstance(c, Token)]

        for token in tokens:
            if token.type in ("ACTION", "TRADE_ACTION"):
                action_type = str(token)
            elif token.type == "TIME":
                time = str(token)

        return Action(action_type, time)

    def _build_exit_statement(self, tree: Tree) -> ExitStatement:
        """Build an exit statement from parse tree."""
        exit_stmt = ExitStatement()

        for child in tree.children:
            if isinstance(child, Tree) and child.data == "exit_condition":
                cond = self._build_exit_type(child)
                exit_stmt.add_condition(cond)

        return exit_stmt

    def _build_exit_type(self, tree: Tree) -> ExitCondition:
        """Build an exit type condition."""
        exit_type = "EXIT"
        value = None
        time = None

        # Get the type from the first token
        tokens = [c for c in tree.children if isinstance(c, Token)]

        for token in tokens:
            upper = str(token).upper()
            if upper in {"AT", "TARGET", "SL", "STOPLOSS", "TRAILING"}:
                exit_type = upper
            elif token.type == "TIME":
                time = str(token)
            elif token.type == "NUMBER":
                value = float(token)

        return ExitCondition(exit_type, value, time)

    def _handle_unexpected_character(
        self, e: UnexpectedCharacters, code: str
    ) -> ParseError:
        """Handle UnexpectedCharacter errors with friendly messages."""
        line, col = e.line, e.column

        # Check for common patterns
        char = e.char
        before = (
            code[e.pos_in_stream - 10 : e.pos_in_stream] if e.pos_in_stream > 0 else ""
        )

        if char == ":" and "IF" in before:
            raise ParseError(
                message="You forgot a condition before the colon",
                line=line,
                column=col,
                hint="Example: IF RSI(14) < 30: BUY",
            )

        if not char.strip():
            raise ParseError(
                message="Unexpected whitespace or newline",
                line=line,
                column=col,
                hint="Make sure your condition is complete before the colon",
            )

        raise ParseError(
            message=f"Unexpected character '{char}'",
            line=line,
            column=col,
            unexpected_token=char,
            hint="Check for typos in your code",
        )

    def _handle_unexpected_token(self, e: UnexpectedToken, code: str) -> ParseError:
        """Handle UnexpectedToken errors with friendly messages."""
        line = getattr(e, "line", None) or 1
        column = getattr(e, "column", None) or 1

        # Map expected tokens to friendly messages
        expected = list(e.expected) if hasattr(e, "expected") else []

        unexpected = str(e.token) if hasattr(e, "token") else "unknown"

        # Check for missing colon
        if ":" in expected or "COLON" in str(expected).upper():
            raise ParseError(
                message=ERROR_MESSAGES["missing_colon"],
                line=line,
                column=column,
                unexpected_token=unexpected,
                expected=expected,
                hint="Add a colon (:) at the end of your IF statement",
            )

        # Check for missing condition
        if "CONDITION" in str(expected).upper():
            raise ParseError(
                message=ERROR_MESSAGES["missing_condition"],
                line=line,
                column=column,
                hint="Example: IF RSI(14) < 30: BUY",
            )

        raise ParseError(
            message=f"Unexpected token '{unexpected}'",
            line=line,
            column=column,
            unexpected_token=unexpected,
            expected=expected,
            hint="Check your syntax",
        )

    def _handle_unexpected_input(self, e: UnexpectedInput, code: str) -> ParseError:
        """Handle UnexpectedInput errors."""
        line = getattr(e, "line", None) or 1
        column = getattr(e, "column", None) or 1

        raise ParseError(
            message=str(e), line=line, column=column, hint="Check your ZenScript syntax"
        )

    def validate(self, code: str) -> List[ParseError]:
        """
        Validate ZenScript code and return list of errors/warnings.

        Args:
            code: ZenScript strategy code

        Returns:
            List of ParseError objects (empty if valid)
        """
        errors = []

        if not code or not code.strip():
            errors.append(
                ParseError(
                    message=ERROR_MESSAGES["empty_strategy"],
                    hint="Add a condition like: IF RSI(14) < 30: BUY",
                )
            )
            return errors

        # Check for balanced parentheses
        paren_count = code.count("(") - code.count(")")
        if paren_count != 0:
            if paren_count > 0:
                errors.append(
                    ParseError(
                        message="Missing closing parenthesis )",
                        hint="Check your indicator parameters",
                    )
                )
            else:
                errors.append(
                    ParseError(
                        message="Extra closing parenthesis )", hint="Remove the extra )"
                    )
                )

        # Check for balanced quotes
        single_quotes = code.count("'")
        double_quotes = code.count('"')
        if single_quotes % 2 != 0:
            errors.append(
                ParseError(
                    message="Missing closing quote '", hint="Complete your string"
                )
            )
        if double_quotes % 2 != 0:
            errors.append(
                ParseError(
                    message='Missing closing quote "', hint="Complete your string"
                )
            )

        # Try to parse
        try:
            self.parse(code)
        except ParseError as e:
            errors.append(e)

        return errors

    def format_error(self, error: ParseError) -> str:
        """
        Format a ParseError into a user-friendly message.

        Args:
            error: The ParseError to format

        Returns:
            Formatted error message string
        """
        msg = f"Line {error.line or '?'}: {error.message}"
        if error.hint:
            msg += f"\n💡 Hint: {error.hint}"
        return msg


# Convenience function
def parse_zenscript(code: str) -> StrategyNode:
    """Parse ZenScript code into a StrategyNode."""
    parser = ZenScriptParser()
    return parser.parse(code)


def validate_zenscript(code: str) -> List[ParseError]:
    """Validate ZenScript code and return errors."""
    parser = ZenScriptParser()
    return parser.validate(code)
