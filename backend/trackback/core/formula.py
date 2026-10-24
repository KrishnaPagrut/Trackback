"""Safe expression evaluator for emit_number. No eval(). Names are input aliases; a few functions are allowed."""
from __future__ import annotations

import ast
import math
from typing import Any

FUNCS = {"sum": lambda *a: sum(a[0]) if len(a) == 1 and isinstance(a[0], (list, tuple)) else sum(a),
         "min": min, "max": max, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil}
ALLOWED_NODES = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant, ast.Name, ast.Call, ast.Compare, ast.IfExp, ast.BoolOp,
                 ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd, ast.Load, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq,
                 ast.And, ast.Or, ast.List, ast.Tuple, ast.Mod, ast.FloorDiv)


class FormulaError(ValueError):
    pass


def evaluate(expr: str, values: dict[str, Any]) -> float:
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"syntax: {e}") from e
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_NODES):
            raise FormulaError(f"disallowed syntax: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in FUNCS:
                raise FormulaError("only sum/min/max/abs/round/floor/ceil are allowed")
        if isinstance(node, ast.Name) and node.id not in values and node.id not in FUNCS:
            raise FormulaError(f"unknown input '{node.id}'")
    env = {**FUNCS, **{k: (float(v) if v is not None else float("nan")) for k, v in values.items()}}
    try:
        result = eval(compile(tree, "<formula>", "eval"), {"__builtins__": {}}, env)  # noqa: S307 (AST was validated above)
    except ZeroDivisionError as e:
        raise FormulaError("division by zero") from e
    if isinstance(result, bool):
        return 1.0 if result else 0.0
    if not isinstance(result, (int, float)):
        raise FormulaError("formula must produce a number")
    return float(result)
