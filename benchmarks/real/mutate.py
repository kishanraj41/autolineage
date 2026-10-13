"""AST mutations for the real-pipeline benchmark.

Each fault edits one span and leaves every other line number where it was.
``ast.unparse`` of a whole module is not used: it moves later lines, and the
recorded line would no longer be the line the mutator names.

A fault that cannot find its pattern returns None. The runner counts that
as not applicable. It does not invent a nearby edit.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import List, Optional


FAULTS = (
    "insert_filter",
    "change_filter_threshold",
    "change_join",
    "drop_column",
    "leakage",
    "change_encoding",
    "remove_dedup",
    "change_sampling",
    "coerce_dtype",
)

_ENCODE_FUNCS = {"get_dummies", "OneHotEncoder", "OrdinalEncoder"}
_HOW_SWAP = {"left": "inner", "inner": "left", "right": "outer", "outer": "right"}
_DTYPE_FLIP = {
    "float": "object",
    "float64": "object",
    "float32": "object",
    "int": "object",
    "int64": "object",
    "int32": "object",
    "object": "float64",
    "str": "float64",
    "string": "float64",
}
_NAME_FLIP = {"float": "str", "int": "str", "str": "float"}


@dataclass(frozen=True)
class Mutation:
    fault: str
    line: int
    source: str


def mutate(source: str, fault: str) -> Optional[Mutation]:
    if fault not in FAULTS:
        raise ValueError(f"unknown fault {fault!r}")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    return _MUTATORS[fault](source, tree)


def bump_random_state(source: str) -> Optional[str]:
    """Add 1 to the first ``random_state=<number>``. None if there is none.

    The false-positive run uses this. No match means the rerun is the same
    script: any anomaly on that rerun is still a false positive.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for call in _calls(tree):
        for kw in call.keywords:
            if kw.arg != "random_state":
                continue
            if isinstance(kw.value, ast.Constant) and _is_number(kw.value.value):
                bumped = str(int(kw.value.value) + 1)
                return _splice(
                    source,
                    kw.value.lineno, kw.value.col_offset,
                    kw.value.end_lineno, kw.value.end_col_offset,
                    bumped,
                )
    return None


def _splice(source: str, start_line: int, start_col: int,
            end_line: int, end_col: int, replacement: str) -> str:
    """Replace a span. Later line numbers stay put.

    A span that covers several lines is collapsed onto ``start_line``.
    The rest of the span becomes blank lines.
    """
    lines = source.splitlines(keepends=True)
    if not lines:
        return replacement
    if start_line == end_line:
        raw = lines[start_line - 1]
        nl = ""
        body = raw
        if body.endswith("\r\n"):
            body, nl = body[:-2], "\r\n"
        elif body.endswith("\n"):
            body, nl = body[:-1], "\n"
        elif body.endswith("\r"):
            body, nl = body[:-1], "\r"
        lines[start_line - 1] = body[:start_col] + replacement + body[end_col:] + nl
        return "".join(lines)

    first = lines[start_line - 1]
    body = first.rstrip("\r\n")
    lines[start_line - 1] = body[:start_col] + replacement + "\n"
    for i in range(start_line, end_line - 1):
        lines[i] = "\n"
    last = lines[end_line - 1]
    last_body = last.rstrip("\r\n")
    tail = last_body[end_col:]
    if last.endswith("\r\n"):
        end_nl = "\r\n"
    elif last.endswith("\n"):
        end_nl = "\n"
    else:
        end_nl = ""
    lines[end_line - 1] = (tail + end_nl) if tail else (end_nl or "\n")
    return "".join(lines)


def _calls(tree: ast.AST) -> List[ast.Call]:
    found: List[ast.Call] = []

    class _V(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call) -> None:
            found.append(node)
            self.generic_visit(node)

    _V().visit(tree)
    return found


def _func_name(call: ast.Call) -> Optional[str]:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _parents(tree: ast.AST) -> dict:
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _kw(call: ast.Call, name: str) -> Optional[ast.keyword]:
    for kw in call.keywords:
        if kw.arg == name:
            return kw
    return None


def _done(fault: str, line: int, source: str) -> Mutation:
    return Mutation(fault=fault, line=line, source=source)


def _insert_filter(source: str, tree: ast.AST) -> Optional[Mutation]:
    for call in _calls(tree):
        if _func_name(call) != "read_csv":
            continue
        edited = _splice(
            source,
            call.end_lineno, call.end_col_offset,
            call.end_lineno, call.end_col_offset,
            ".iloc[::2]",
        )
        return _done("insert_filter", call.end_lineno, edited)
    return None


def _in_source_order(nodes):
    return sorted(nodes, key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))


def _change_filter_threshold(source: str, tree: ast.AST) -> Optional[Mutation]:
    parents = _parents(tree)
    compares = _in_source_order(n for n in ast.walk(tree) if isinstance(n, ast.Compare))
    for node in compares:
        if not _under_filter(node, parents):
            continue
        for comp in node.comparators:
            if not (isinstance(comp, ast.Constant) and _is_number(comp.value)):
                continue
            nudged = _nudge(comp.value)
            edited = _splice(
                source,
                comp.lineno, comp.col_offset,
                comp.end_lineno, comp.end_col_offset,
                nudged,
            )
            return _done("change_filter_threshold", comp.lineno, edited)
    return None


def _under_filter(node: ast.AST, parents: dict) -> bool:
    cur = node
    while cur in parents:
        cur = parents[cur]
        if isinstance(cur, ast.Subscript):
            return True
        if isinstance(cur, ast.Call) and _func_name(cur) in {"query", "loc"}:
            return True
    return False


def _nudge(value) -> str:
    if isinstance(value, float):
        return repr(value * 10 if value != 0 else 1.0)
    return str(value * 10 if value != 0 else 1)


def _change_join(source: str, tree: ast.AST) -> Optional[Mutation]:
    for call in _calls(tree):
        if _func_name(call) not in {"merge", "join"}:
            continue
        # threading.Thread.join() and Process.join() take no frame argument.
        # A dataframe join or merge has a frame, an ``on`` key, or a ``how``.
        if not call.args and all(_kw(call, name) is None for name in ("on", "how", "left_on", "right_on")):
            continue
        how = _kw(call, "how")
        if how is not None and isinstance(how.value, ast.Constant) and isinstance(how.value.value, str):
            swapped = _HOW_SWAP.get(how.value.value)
            if swapped is None:
                continue
            edited = _splice(
                source,
                how.value.lineno, how.value.col_offset,
                how.value.end_lineno, how.value.end_col_offset,
                repr(swapped),
            )
            return _done("change_join", how.value.lineno, edited)
        on = _kw(call, "on")
        if on is not None and isinstance(on.value, (ast.List, ast.Tuple)) and len(on.value.elts) >= 2:
            edited = _drop_elt(source, on.value.elts, len(on.value.elts) - 1)
            return _done("change_join", on.value.elts[-1].lineno, edited)
        edited = _splice(
            source,
            call.end_lineno, call.end_col_offset - 1,
            call.end_lineno, call.end_col_offset - 1,
            ("" if not call.args and not call.keywords else ", ") + 'how="inner"',
        )
        return _done("change_join", call.end_lineno, edited)
    return None


def _drop_column(source: str, tree: ast.AST) -> Optional[Mutation]:
    parents = _parents(tree)
    lists = _in_source_order(
        n for n in ast.walk(tree) if isinstance(n, (ast.List, ast.Tuple))
    )
    for node in lists:
        if not _is_column_list(node, parents):
            continue
        edited = _drop_elt(source, node.elts, len(node.elts) - 1)
        return _done("drop_column", node.elts[-1].lineno, edited)
    return None


def _is_column_list(node: ast.AST, parents: dict) -> bool:
    if len(getattr(node, "elts", [])) < 2:
        return False
    if not all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
        return False
    cur = node
    for _ in range(3):
        cur = parents.get(cur)
        if cur is None:
            return False
        if isinstance(cur, ast.keyword):
            return cur.arg in {"columns", "usecols"}
        if isinstance(cur, ast.Subscript):
            return True
    return False


def _drop_elt(source: str, elts: list, index: int) -> str:
    elt = elts[index]
    if len(elts) == 1:
        return _splice(source, elt.lineno, elt.col_offset, elt.end_lineno, elt.end_col_offset, "")
    if index == 0:
        nxt = elts[1]
        return _splice(source, elt.lineno, elt.col_offset, nxt.lineno, nxt.col_offset, "")
    prev = elts[index - 1]
    return _splice(
        source,
        prev.end_lineno, prev.end_col_offset,
        elt.end_lineno, elt.end_col_offset,
        "",
    )


def _leakage(source: str, tree: ast.AST) -> Optional[Mutation]:
    split = _split_names(tree)
    if split is not None:
        full_name, train_name, split_line = split
        for call in _calls(tree):
            if call.lineno < split_line:
                continue
            fname = _func_name(call)
            if fname not in {"fit", "fit_transform"}:
                continue
            if len(call.args) != 1 or call.keywords:
                continue
            arg = call.args[0]
            if isinstance(arg, ast.Name) and arg.id == train_name:
                edited = _splice(
                    source, arg.lineno, arg.col_offset, arg.end_lineno, arg.end_col_offset, full_name,
                )
                return _done("leakage", arg.lineno, edited)
    target = _target_column(tree)
    if target is None:
        return None
    for call in _calls(tree):
        if _func_name(call) != "drop":
            continue
        columns = _kw(call, "columns")
        if columns is None or not isinstance(columns.value, (ast.List, ast.Tuple)):
            continue
        for i, elt in enumerate(columns.value.elts):
            if isinstance(elt, ast.Constant) and elt.value == target:
                edited = _drop_elt(source, columns.value.elts, i)
                return _done("leakage", elt.lineno, edited)
    return None


def _split_names(tree: ast.AST):
    assigns = _in_source_order(n for n in ast.walk(tree) if isinstance(n, ast.Assign))
    for node in assigns:
        if not isinstance(node.value, ast.Call):
            continue
        if _func_name(node.value) != "train_test_split":
            continue
        if not node.value.args or not isinstance(node.value.args[0], ast.Name):
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Tuple) or not target.elts:
            continue
        train = target.elts[0]
        if not isinstance(train, ast.Name):
            continue
        return node.value.args[0].id, train.id, node.lineno
    return None


def _target_column(tree: ast.AST) -> Optional[str]:
    assigns = _in_source_order(n for n in ast.walk(tree) if isinstance(n, ast.Assign))
    for node in assigns:
        if len(node.targets) != 1:
            continue
        if not isinstance(node.targets[0], ast.Name) or node.targets[0].id != "y":
            continue
        value = node.value
        if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant):
            if isinstance(value.slice.value, str):
                return value.slice.value
    return None


def _change_encoding(source: str, tree: ast.AST) -> Optional[Mutation]:
    for call in _calls(tree):
        fname = _func_name(call)
        if fname not in _ENCODE_FUNCS:
            continue
        dropped = _kw(call, "drop_first")
        if dropped is not None and isinstance(dropped.value, ast.Constant) and isinstance(dropped.value.value, bool):
            edited = _splice(
                source,
                dropped.value.lineno, dropped.value.col_offset,
                dropped.value.end_lineno, dropped.value.end_col_offset,
                "False" if dropped.value.value else "True",
            )
            return _done("change_encoding", dropped.value.lineno, edited)
        unknown = _kw(call, "handle_unknown")
        if unknown is not None and isinstance(unknown.value, ast.Constant) and isinstance(unknown.value.value, str):
            flipped = "error" if unknown.value.value == "ignore" else "ignore"
            edited = _splice(
                source,
                unknown.value.lineno, unknown.value.col_offset,
                unknown.value.end_lineno, unknown.value.end_col_offset,
                repr(flipped),
            )
            return _done("change_encoding", unknown.value.lineno, edited)
        if fname == "get_dummies":
            extra = 'drop_first=True' if not call.args and not call.keywords else ', drop_first=True'
        elif fname == "OneHotEncoder":
            extra = 'handle_unknown="ignore"' if not call.args and not call.keywords else ', handle_unknown="ignore"'
        else:
            continue
        edited = _splice(
            source,
            call.end_lineno, call.end_col_offset - 1,
            call.end_lineno, call.end_col_offset - 1,
            extra,
        )
        return _done("change_encoding", call.end_lineno, edited)
    return None


def _remove_dedup(source: str, tree: ast.AST) -> Optional[Mutation]:
    for call in _calls(tree):
        if _func_name(call) != "drop_duplicates":
            continue
        if not isinstance(call.func, ast.Attribute):
            continue
        attr = call.func
        edited = _splice(
            source,
            attr.lineno, attr.col_offset,
            call.end_lineno, call.end_col_offset,
            "copy()",
        )
        return _done("remove_dedup", attr.lineno, edited)
    return None


def _change_sampling(source: str, tree: ast.AST) -> Optional[Mutation]:
    for call in _calls(tree):
        if _func_name(call) != "sample":
            continue
        for arg_name in ("frac", "n"):
            kw = _kw(call, arg_name)
            if kw is None or not isinstance(kw.value, ast.Constant) or not _is_number(kw.value.value):
                continue
            replacement = _resample(arg_name, kw.value.value)
            edited = _splice(
                source,
                kw.value.lineno, kw.value.col_offset,
                kw.value.end_lineno, kw.value.end_col_offset,
                replacement,
            )
            return _done("change_sampling", kw.value.lineno, edited)
    for call in _calls(tree):
        if _func_name(call) != "train_test_split":
            continue
        kw = _kw(call, "test_size")
        if kw is None or not isinstance(kw.value, ast.Constant) or not _is_number(kw.value.value):
            continue
        value = kw.value.value
        replacement = "0.5" if value < 0.5 else "0.2"
        edited = _splice(
            source,
            kw.value.lineno, kw.value.col_offset,
            kw.value.end_lineno, kw.value.end_col_offset,
            replacement,
        )
        return _done("change_sampling", kw.value.lineno, edited)
    return None


def _resample(arg_name: str, value) -> str:
    if arg_name == "n":
        return str(max(1, int(value) // 2))
    if value >= 0.5:
        return f"{value / 2:.4g}"
    return f"{min(value * 2, 0.9):.4g}"


def _coerce_dtype(source: str, tree: ast.AST) -> Optional[Mutation]:
    for call in _calls(tree):
        if _func_name(call) != "astype":
            continue
        if not call.args:
            continue
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value in _DTYPE_FLIP:
            edited = _splice(
                source,
                arg.lineno, arg.col_offset,
                arg.end_lineno, arg.end_col_offset,
                repr(_DTYPE_FLIP[arg.value]),
            )
            return _done("coerce_dtype", arg.lineno, edited)
        if isinstance(arg, ast.Name) and arg.id in _NAME_FLIP:
            edited = _splice(
                source,
                arg.lineno, arg.col_offset,
                arg.end_lineno, arg.end_col_offset,
                _NAME_FLIP[arg.id],
            )
            return _done("coerce_dtype", arg.lineno, edited)
    return None


_MUTATORS = {
    "insert_filter": _insert_filter,
    "change_filter_threshold": _change_filter_threshold,
    "change_join": _change_join,
    "drop_column": _drop_column,
    "leakage": _leakage,
    "change_encoding": _change_encoding,
    "remove_dedup": _remove_dedup,
    "change_sampling": _change_sampling,
    "coerce_dtype": _coerce_dtype,
}
