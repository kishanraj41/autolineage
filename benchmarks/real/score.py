"""Scores for one planted fault. No rate is computed here from a corpus.

A case enters the detection denominator only when the mutated script
finishes and a recorded metric changes. The other outcomes are counted
beside that rate, not folded into it.
"""

from __future__ import annotations

import ast
import os
import random
from typing import Dict, Iterable, List, Optional


METRIC_EPS = 1e-6

# Fixed before any corpus score. A call counts toward coverage when its
# leftmost name is a pandas or sklearn import, or its attribute is one of
# these operations. Ordinary calls such as print() do not.
PIPELINE_ATTRS = frozenset({
    "read_csv", "read_excel", "read_parquet", "read_json", "read_sql",
    "to_csv", "to_parquet", "to_json",
    "dropna", "drop", "fillna", "merge", "join", "concat", "get_dummies",
    "drop_duplicates", "sample", "astype", "query", "groupby", "reset_index",
    "sort_values", "rename", "replace", "apply", "map", "assign", "pivot",
    "melt", "copy", "head", "tail", "iloc", "loc",
    "fit", "transform", "fit_transform", "predict", "predict_proba",
    "train_test_split", "accuracy_score", "f1_score", "precision_score",
    "recall_score", "roc_auc_score", "classification_report",
    "LabelEncoder", "OneHotEncoder", "OrdinalEncoder", "StandardScaler",
    "MinMaxScaler", "LogisticRegression", "RandomForestClassifier",
})


def metric_changed(before: Dict, after: Dict) -> bool:
    """True when some recorded metric moves by more than METRIC_EPS."""
    names = set(before) | set(after)
    if not names:
        return False
    for name in names:
        left = before.get(name)
        right = after.get(name)
        if left is None or right is None:
            return True
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            return left != right
        if isinstance(left, bool) or isinstance(right, bool):
            return left != right
        if left == 0:
            if abs(right) > METRIC_EPS:
                return True
        elif abs(right - left) / abs(left) > METRIC_EPS:
            return True
    return False


def pipeline_call_lines(source: str) -> set:
    """Lines that count as pipeline operations for the coverage denominator."""
    tree = ast.parse(source)
    roots = _import_roots(tree)
    lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if _counts_as_pipeline_call(node, roots):
                lines.add(node.lineno)
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Subscript):
            lines.add(node.lineno)
    return lines


# Methods that also exist on hand-written classes. They count in the frozen
# denominator, and in framework-call coverage only when the leftmost name
# was imported from pandas or sklearn.
_FOREIGN_UNLESS_FRAMEWORK = frozenset({
    "fit", "predict", "predict_proba", "score", "astype",
})


def framework_call_lines(source: str) -> set:
    """Frozen pipeline calls without subscript assigns or foreign methods.

    A call named fit, predict, predict_proba, score, or astype is kept
    only when its leftmost name was imported from pandas or sklearn.
    Constructors stay out of this filter; they are listed by
    ``constructor_lines``.
    """
    tree = ast.parse(source)
    roots = _import_roots(tree)
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _counts_as_pipeline_call(node, roots):
            continue
        func = node.func
        attr = func.attr if isinstance(func, ast.Attribute) else None
        if attr in _FOREIGN_UNLESS_FRAMEWORK:
            if _leftmost_name(func.value) not in roots:
                continue
        lines.add(node.lineno)
    return lines


def constructor_lines(source: str) -> List[int]:
    """Lines that call a pandas or sklearn class, listed beside coverage.

    They remain inside the frozen denominator. A name imported from those
    packages counts as a constructor when it starts with a capital letter.
    """
    tree = ast.parse(source)
    roots = _import_roots(tree)
    lines = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        name = node.func.id
        if name in roots and name[:1].isupper():
            lines.add(node.lineno)
    return sorted(lines)


def coverage(source: str, records: List[dict], script: str) -> Optional[float]:
    """Share of pipeline-call lines that produced at least one record.

    None when the script has no pipeline call, so an empty file cannot
    become a coverage of 1.
    """
    return _line_coverage(pipeline_call_lines(source), records, script)


def framework_coverage(source: str, records: List[dict], script: str) -> Optional[float]:
    """Share of framework-call lines that produced at least one record."""
    return _line_coverage(framework_call_lines(source), records, script)


def _line_coverage(calls: set, records: List[dict], script: str) -> Optional[float]:
    if not calls:
        return None
    seen = set()
    for rec in records:
        if not _from_script(rec, script):
            continue
        line = rec.get("source_line")
        if line in calls:
            seen.add(line)
    return len(seen) / len(calls)


def largest_row_drop_line(records: List[dict], script: str) -> Optional[int]:
    """User line of the mutated-run record that dropped the largest row fraction.

    Ties keep the earliest record. No positive drop means the baseline
    has no guess.
    """
    best_line = None
    best_drop = 0.0
    for rec in records:
        if not _from_script(rec, script):
            continue
        before, after = rec.get("rows_before"), rec.get("rows_after")
        if not before or after is None or before <= 0:
            continue
        dropped = (before - after) / before
        if dropped > best_drop:
            best_drop = dropped
            best_line = rec.get("source_line")
    return best_line


def last_changed_line(clean: List[dict], mutated: List[dict],
                      clean_script: str, mutated_script: str) -> Optional[int]:
    """Last user line whose operation or row delta differs from the clean run.

    The two runs are different files (the mutated copy sits beside the
    original), so each side is filtered by its own path. Line numbers still
    correspond: the mutator does not shift them.
    """
    before = [r for r in clean if _from_script(r, clean_script) and r.get("category") != "evaluate"]
    after = [r for r in mutated if _from_script(r, mutated_script) and r.get("category") != "evaluate"]
    changed = None
    for i in range(max(len(before), len(after))):
        if i >= len(before):
            changed = after[i].get("source_line")
            continue
        if i >= len(after):
            continue
        if before[i].get("operation") != after[i].get("operation") or _row_delta(before[i]) != _row_delta(after[i]):
            changed = after[i].get("source_line")
    return changed


def random_line(source: str, case_id: str, mutated_line: int) -> int:
    """Seeded pick among the script's pipeline-call lines.

    The mutated line is always in the pool, so a fault on a line the
    coverage definition would otherwise miss is still a possible guess.
    """
    lines = sorted(pipeline_call_lines(source))
    if mutated_line not in lines:
        lines.append(mutated_line)
        lines.sort()
    return random.Random(str(case_id)).choice(lines)


def autolineage_lines(ranking: List[dict], script: str) -> List[int]:
    """Source lines of the ranked causes that belong to this script, best first."""
    lines = []
    for entry in ranking:
        if entry.get("source_file") and not _same_file(entry.get("source_file"), script):
            continue
        line = entry.get("source_line")
        if isinstance(line, int):
            lines.append(line)
    return lines


def detected(anomalies: Iterable[dict]) -> bool:
    return any(a.get("severity") in {"warning", "critical"} for a in anomalies)


def score_case(*, fault: str, mutated_line: int, clean_script: str,
               mutated_script: str, case_id: str, clean: dict, mutated: dict,
               unmutated_rerun: Optional[dict], wall_without_hooks_s: Optional[float],
               mutated_source: str) -> dict:
    """One case. Status decides whether the booleans enter a published rate."""
    if clean.get("status") != "ok" or mutated.get("status") != "ok":
        status = "crash"
    elif not metric_changed(clean.get("metrics") or {}, mutated.get("metrics") or {}):
        status = "no_metric_change"
    else:
        status = "scored"

    ranking = mutated.get("ranking") or []
    lines = autolineage_lines(ranking, mutated_script)
    fp_anomalies = None
    if unmutated_rerun is not None and unmutated_rerun.get("status") == "ok":
        fp_anomalies = detected(unmutated_rerun.get("anomalies") or [])

    overhead = None
    if wall_without_hooks_s is not None and clean.get("wall_s") is not None:
        overhead = clean["wall_s"] - wall_without_hooks_s

    drop_line = largest_row_drop_line(mutated.get("records") or [], mutated_script)
    changed_line = last_changed_line(
        clean.get("records") or [], mutated.get("records") or [],
        clean_script, mutated_script,
    )
    guess = random_line(mutated_source, case_id, mutated_line)

    return {
        "fault": fault,
        "status": status,
        "mutated_line": mutated_line,
        "detected": detected(mutated.get("anomalies") or []) if status == "scored" else None,
        "top1": (bool(lines) and lines[0] == mutated_line) if status == "scored" else None,
        "top3": (mutated_line in lines[:3]) if status == "scored" else None,
        "false_positive": fp_anomalies,
        "coverage": coverage(mutated_source, mutated.get("records") or [], mutated_script),
        "framework_coverage": framework_coverage(
            mutated_source, mutated.get("records") or [], mutated_script,
        ),
        "constructor_lines": constructor_lines(mutated_source),
        "overhead_s": overhead,
        "hooked_duration_ms": sum(
            r.get("duration_ms") or 0 for r in (clean.get("records") or [])
        ),
        "baseline_largest_row_drop": (drop_line == mutated_line) if status == "scored" else None,
        "baseline_last_changed_step": (changed_line == mutated_line) if status == "scored" else None,
        "baseline_random": (guess == mutated_line) if status == "scored" else None,
        "random_guess_line": guess,
        "largest_row_drop_line": drop_line,
        "last_changed_line": changed_line,
        "ranked_lines": lines[:3],
    }


def summarize(cases: List[dict]) -> dict:
    """Rates over scored cases only. The other counts stay visible."""
    scored = [c for c in cases if c.get("status") == "scored"]
    n = len(scored)

    def rate(key):
        if not n:
            return None
        return sum(1 for c in scored if c.get(key)) / n

    fp_cases = [c for c in scored if c.get("false_positive") is not None]
    return {
        "n_cases": len(cases),
        "n_scored": n,
        "n_not_applicable": sum(c.get("status") == "not_applicable" for c in cases),
        "n_no_metric_change": sum(c.get("status") == "no_metric_change" for c in cases),
        "n_crash": sum(c.get("status") == "crash" for c in cases),
        "detection": rate("detected"),
        "top1": rate("top1"),
        "top3": rate("top3"),
        "false_positive_rate": (
            None if not fp_cases else sum(1 for c in fp_cases if c["false_positive"]) / len(fp_cases)
        ),
        "baseline_largest_row_drop": rate("baseline_largest_row_drop"),
        "baseline_last_changed_step": rate("baseline_last_changed_step"),
        "baseline_random": rate("baseline_random"),
        "mean_coverage": _mean(c.get("coverage") for c in scored),
        "mean_framework_coverage": _mean(c.get("framework_coverage") for c in scored),
        "mean_overhead_s": _mean(c.get("overhead_s") for c in scored),
    }


def _mean(values) -> Optional[float]:
    nums = [v for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return sum(nums) / len(nums)


def _row_delta(rec: dict):
    before, after = rec.get("rows_before"), rec.get("rows_after")
    if before is None or after is None:
        return None
    return after - before


def _same_file(left: str, right: str) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def _from_script(rec: dict, script: str) -> bool:
    src = rec.get("source_file")
    return bool(src) and _same_file(src, script)


def _leftmost_name(node) -> Optional[str]:
    seen = 0
    while node is not None and seen < 40:
        seen += 1
        if isinstance(node, ast.Attribute):
            node = node.value
        elif isinstance(node, ast.Call):
            node = node.func
        elif isinstance(node, ast.Subscript):
            node = node.value
        elif isinstance(node, ast.Name):
            return node.id
        else:
            return None
    return None


def _import_roots(tree: ast.AST) -> set:
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in {"pandas", "sklearn"}:
                    roots.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in {"pandas", "sklearn"}:
                for alias in node.names:
                    roots.add(alias.asname or alias.name)
    return roots


def _counts_as_pipeline_call(node: ast.Call, roots: set) -> bool:
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else None)
    left = func
    while isinstance(left, ast.Attribute):
        left = left.value
    if isinstance(left, ast.Call):
        left_name = None
    else:
        left_name = left.id if isinstance(left, ast.Name) else None
    return left_name in roots or name in PIPELINE_ATTRS
