"""Corpus selection. Reads the frozen pool and appends skips.

``--static`` applies the licence, path, import, and dataset rules.
``--run`` is the unmutated qualification run for hits that already passed
``--static``. It does not plant faults, and it does not call
``run_heldout.py``.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REAL = ROOT / "benchmarks" / "real"
MANIFEST = REAL / "manifest.json"
SKIPPED = REAL / "skipped.jsonl"
SEARCH = REAL / "search_2026-10-10.json"
POOL2 = REAL / "search_2026-10-10_pool2.json"
QUERY2 = "fetch_openml train_test_split accuracy_score extension:py"
POOL3 = REAL / "search_2026-10-10_pool3.json"
QUERY3 = '"from sklearn.datasets import" train_test_split accuracy_score extension:py'
POOL4 = REAL / "search_2026-10-11_study2.json"
QUERY4 = "astype drop train_test_split accuracy_score extension:py"
POOL4B = REAL / "search_2026-10-11_study2b.json"
QUERY4B = "read_csv dropna train_test_split accuracy_score extension:py -filename:app.py"
POOL4C = REAL / "search_2026-10-11_study2c.json"
QUERY4C = "get_dummies train_test_split accuracy_score read_csv extension:py -filename:app.py"
# Written after pools A-C closed at one runnable script, before any of
# these queries was sent, and before any Study 2 mutation was scored.
POOL4_FOLLOWUPS = (
    (REAL / "search_2026-10-11_study2d.json",
     "make_classification train_test_split astype accuracy_score extension:py -filename:app.py",
     "next_index_d"),
    (REAL / "search_2026-10-11_study2e.json",
     "load_breast_cancer train_test_split get_dummies accuracy_score extension:py -filename:app.py",
     "next_index_e"),
    (REAL / "search_2026-10-11_study2f.json",
     "load_iris train_test_split dropna accuracy_score extension:py -filename:app.py",
     "next_index_f"),
    (REAL / "search_2026-10-11_study2g.json",
     "make_classification train_test_split get_dummies accuracy_score extension:py -filename:app.py",
     "next_index_g"),
)
STUDY2_DEV = 5
STUDY2_HELDOUT = 15

OSI = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "MPL-2.0"}
LOADERS = (
    "fetch_openml", "sklearn.datasets", "load_iris", "load_breast_cancer",
    "load_diabetes", "load_wine", "load_digits", "fetch_california_housing",
    "fetch_covtype", "fetch_20newsgroups",
)
QUERY = "accuracy_score train_test_split read_csv extension:py"
DEV_FROM_POOL = 4
HELDOUT_FROM_POOL = 10


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--static", action="store_true")
    parser.add_argument("--fetch", action="store_true", help="download the frozen search pool")
    parser.add_argument("--run", action="store_true",
                        help="unmutated qualification run; does not plant faults")
    parser.add_argument("--fetch2", action="store_true",
                        help="download and statically filter pool 2")
    parser.add_argument("--fetch3", action="store_true",
                        help="download and statically filter pool 3 into held-out only")
    parser.add_argument("--fetch4", action="store_true",
                        help="download the Study 2 pool and statically filter it")
    parser.add_argument("--fetch4b", action="store_true",
                        help="download Study 2 pool B and statically filter it")
    parser.add_argument("--fetch4c", action="store_true",
                        help="download Study 2 pool C and statically filter it")
    parser.add_argument("--fetch4d", action="store_true",
                        help="download the four pre-registered follow-up pools and filter them")
    parser.add_argument("--run4", action="store_true",
                        help="qualify Study 2 hits; does not plant faults")
    args = parser.parse_args(argv)
    if args.fetch:
        _fetch_pool()
    if args.static:
        _static_pass()
    if args.fetch2:
        _fetch_into(POOL2, QUERY2)
        _static_from(POOL2, "next_index_pool2")
    if args.fetch3:
        _fetch_into(POOL3, QUERY3)
        _static_from(POOL3, "next_index_pool3", skip_known=True, heldout_only=True)
    if args.fetch4:
        if not POOL4.exists():
            _fetch_into(POOL4, QUERY4)
        _study2_static(POOL4, "next_index")
    if args.fetch4b:
        if not POOL4B.exists():
            _fetch_into(POOL4B, QUERY4B)
        _study2_static(POOL4B, "next_index_b")
    if args.fetch4c:
        if not POOL4C.exists():
            _fetch_into(POOL4C, QUERY4C)
        _study2_static(POOL4C, "next_index_c")
    if args.fetch4d:
        for path, query, index_key in POOL4_FOLLOWUPS:
            if not path.exists():
                _fetch_into(path, query)
            _study2_static(path, index_key)
    if args.run4:
        _study2_run()
    if args.run:
        _run_pass()
    return 0


def _fetch_pool() -> None:
    _fetch_into(SEARCH, QUERY)


def _fetch_into(path: Path, query: str) -> None:
    items = []
    for page in (1, 2):
        payload = _gh([
            "api", "--method", "GET", "search/code",
            "-f", f"q={query}",
            "-f", "per_page=50",
            "-f", f"page={page}",
        ])
        for item in payload.get("items", []):
            items.append({
                "repo": item["repository"]["full_name"],
                "path": item["path"],
                "html_url": item.get("html_url"),
            })
        time.sleep(1)
    path.write_text(json.dumps(items, indent=2), encoding="utf-8")
    print(f"saved {len(items)} hits to {path.name}")


def _static_pass() -> None:
    _static_from(SEARCH, "next_index")


def _static_from(pool_path: Path, index_key: str, *, skip_known: bool = False,
                 heldout_only: bool = False) -> None:
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    known = _known_hits() if skip_known else set()
    start = int(manifest.get(index_key) or 0)
    for index in range(start, len(pool)):
        if _filled(manifest):
            break
        hit = pool[index]
        manifest[index_key] = index + 1
        if (hit["repo"], hit["path"]) in known:
            _skip(hit, "already_in_earlier_pool", "")
            print(_ascii(f"skip {hit['repo']} {hit['path']}: already_in_earlier_pool"))
            MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            continue
        reason = _classify(hit)
        if reason is None:
            _assign(manifest, hit, heldout_only=heldout_only)
            print(_ascii(f"keep {hit['repo']} {hit['path']} -> {_last_slot(manifest)}"))
        else:
            _skip(hit, reason[0], reason[1])
            print(_ascii(f"skip {hit['repo']} {hit['path']}: {reason[0]}"))
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        index_key: manifest.get(index_key),
        "dev": len(manifest.get("dev", [])),
        "heldout": len(manifest.get("heldout", [])),
    }))


def _ascii(text: str) -> str:
    return text.encode("ascii", errors="backslashreplace").decode("ascii")


def _filled(manifest: dict) -> bool:
    dev = [s for s in manifest.get("dev", []) if s.get("scored")]
    return len(dev) >= DEV_FROM_POOL and len(manifest.get("heldout", [])) >= HELDOUT_FROM_POOL


def _known_hits() -> set:
    """Files already judged by pool 1 or pool 2."""
    known = set()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for key in ("dev", "heldout", "rejected_after_static"):
        for slot in manifest.get(key) or []:
            if slot.get("repo") and slot.get("path"):
                known.add((slot["repo"], slot["path"]))
    for path in (SEARCH, POOL2):
        if path.exists():
            for hit in json.loads(path.read_text(encoding="utf-8")):
                known.add((hit["repo"], hit["path"]))
    return known


def _assign(manifest: dict, hit: dict, heldout_only: bool = False) -> None:
    dev = [s for s in manifest.get("dev", []) if s.get("scored")]
    slot_body = {
        "role": "heldout" if heldout_only or len(dev) >= DEV_FROM_POOL else "development",
        "scored": True,
        "qualified_run": False,
        "repo": hit["repo"],
        "url": f"https://github.com/{hit['repo']}",
        "commit": hit["commit"],
        "path": hit["path"],
        "license": hit["license"],
        "dataset": hit.get("dataset"),
        "adapter": [],
    }
    if slot_body["role"] == "development":
        slot_body["slot"] = f"dev-{len(manifest['dev']) + 1}"
        manifest["dev"].append(slot_body)
    else:
        slot_body["slot"] = f"heldout-{len(manifest.get('heldout', [])) + 1}"
        manifest.setdefault("heldout", []).append(slot_body)


def _last_slot(manifest: dict) -> str:
    if manifest.get("heldout"):
        return manifest["heldout"][-1]["slot"]
    return manifest["dev"][-1]["slot"]


def _classify(hit: dict):
    if _is_test_path(hit["path"]):
        return "test_path", hit["path"]
    meta = _gh_json(f"repos/{hit['repo']}")
    licence = (meta.get("license") or {}).get("spdx_id")
    hit["license"] = licence
    if licence not in OSI:
        return "no_osi_license", licence
    branch = meta.get("default_branch") or "HEAD"
    commit = _gh_json(f"repos/{hit['repo']}/commits/{branch}")["sha"]
    hit["commit"] = commit
    content, missing = _file_text(hit["repo"], hit["path"], commit)
    if content is None:
        return "file_unavailable", missing
    if "pandas" not in content or "sklearn" not in content:
        return "missing_pandas_or_sklearn", ""
    dataset = _dataset(hit["repo"], commit, hit["path"], content)
    if dataset is None:
        return "dataset_not_identified", ""
    hit["dataset"] = dataset
    hit["_source"] = content
    return None


def _dataset(repo: str, commit: str, script_path: str, content: str):
    if any(name in content for name in LOADERS):
        return {"kind": "sklearn_or_openml", "locator": _first_loader(content)}
    if "archive.ics.uci.edu" in content:
        return {"kind": "uci", "locator": "archive.ics.uci.edu"}
    local = _local_csv(repo, commit, script_path, content)
    if local is not None:
        return local
    if "kaggle" in content.lower():
        readme = _readme(repo, commit)
        if readme and any(mark in readme for mark in ("CC0", "CC BY", "CC-BY", "public domain")):
            return {"kind": "kaggle", "locator": "stated in README"}
        return None
    return None


def _local_csv(repo: str, commit: str, script_path: str, content: str):
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return None
    script_dir = str(Path(script_path).parent).replace("\\", "/")
    if script_dir == ".":
        script_dir = ""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        if name != "read_csv" or not node.args:
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            continue
        raw = arg.value
        if raw.startswith("http://") or raw.startswith("https://"):
            if "archive.ics.uci.edu" in raw:
                return {"kind": "uci", "locator": raw}
            continue
        if not raw.lower().endswith(".csv"):
            continue
        for candidate in _candidate_paths(script_dir, raw):
            text, _missing = _file_text(repo, candidate, commit)
            if text is not None:
                return {"kind": "repo_csv", "locator": candidate}
    return None


def _candidate_paths(script_dir: str, raw: str):
    cleaned = raw.replace("\\", "/").lstrip("./")
    yield cleaned
    if script_dir:
        yield f"{script_dir}/{cleaned}"


def _first_loader(content: str) -> str:
    for name in LOADERS:
        if name in content:
            return name
    return ""


def _readme(repo: str, commit: str) -> str:
    for name in ("README.md", "README.rst", "readme.md"):
        text, _missing = _file_text(repo, name, commit)
        if text:
            return text
    return ""


def _file_text(repo: str, path: str, commit: str):
    quoted = path.replace(" ", "%20")
    try:
        payload = _gh_json(f"repos/{repo}/contents/{quoted}?ref={commit}")
    except subprocess.CalledProcessError as exc:
        return None, str(exc)[-200:]
    if payload.get("encoding") == "base64" and payload.get("content"):
        return base64.b64decode(payload["content"]).decode("utf-8", errors="replace"), ""
    return None, payload.get("message", "no content")


def _is_test_path(path: str) -> bool:
    parts = path.replace("\\", "/").split("/")
    if any(part.lower() in {"test", "tests", "testing"} for part in parts):
        return True
    name = parts[-1].lower()
    return name.startswith("test_") or name.endswith("_test.py")


def _skip(hit: dict, reason: str, detail) -> None:
    row = {
        "repo": hit.get("repo"),
        "path": hit.get("path"),
        "reason": reason,
        "detail": detail,
    }
    with SKIPPED.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")


def _gh(args: list) -> dict:
    proc = subprocess.run(["gh", *args], check=True, capture_output=True)
    return json.loads(proc.stdout.decode("utf-8"))


def _gh_json(path: str) -> dict:
    time.sleep(0.25)
    return _gh(["api", path])


def _run_pass() -> None:
    """Unmutated run. A failure removes the slot. Nothing is mutated."""
    import hashlib
    import urllib.request

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    telco = [s for s in manifest["dev"] if s.get("slot") == "dev-1"]
    already = [s for s in manifest["dev"] if s.get("scored") and s.get("qualified_run")]
    already.extend(
        s for s in manifest.get("heldout", []) if s.get("scored") and s.get("qualified_run")
    )
    pending = [s for s in manifest["dev"] if s.get("scored") and not s.get("qualified_run")]
    pending.extend(
        s for s in manifest.get("heldout", []) if s.get("scored") and not s.get("qualified_run")
    )
    passed = list(already)
    rejected = list(manifest.get("rejected_after_static", []))
    for slot in pending:
        cache = REAL / "cache" / slot["repo"].replace("/", "__") / slot["path"]
        try:
            _stage(slot, cache, urllib.request, hashlib)
            code, detail = _execute(cache, slot["path"])
        except Exception as exc:
            code, detail = 1, repr(exc)[:300]
        if code == 0:
            slot["qualified_run"] = True
            passed.append(slot)
            print(f"ran {slot['repo']} {slot['path']}")
        else:
            slot["qualified_run"] = False
            slot["scored"] = False
            rejected.append(slot)
            _skip(slot, "does_not_run", detail)
            print(f"fail {slot['repo']} {slot['path']}: {detail[:120]}")
    manifest["dev"] = telco
    manifest["heldout"] = []
    for slot in passed:
        if len([s for s in manifest["dev"] if s.get("scored")]) < DEV_FROM_POOL:
            slot["role"] = "development"
            slot["slot"] = f"dev-{len(manifest['dev']) + 1}"
            manifest["dev"].append(slot)
        elif len(manifest["heldout"]) < HELDOUT_FROM_POOL:
            slot["role"] = "heldout"
            slot["slot"] = f"heldout-{len(manifest['heldout']) + 1}"
            manifest["heldout"].append(slot)
    manifest["rejected_after_static"] = rejected
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "dev": len(manifest["dev"]),
        "heldout": len(manifest["heldout"]),
        "rejected": len(rejected),
    }))


def _stage(slot: dict, cache: Path, urllib_request, hashlib) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    script_path = cache / Path(slot["path"]).name
    script = _raw(slot["repo"], slot["commit"], slot["path"], urllib_request)
    dataset = slot.get("dataset") or {}
    locator = dataset.get("locator") or ""
    csv_path = None
    if dataset.get("kind") == "repo_csv" and locator:
        csv_path = cache / Path(locator).name
        blob = _raw(slot["repo"], slot["commit"], locator, urllib_request)
        csv_path.write_bytes(blob)
        dataset["sha256"] = hashlib.sha256(blob).hexdigest()
        dataset["bytes"] = len(blob)
    adapted, adapter = _apply_adapter(script.decode("utf-8", errors="replace"), csv_path)
    script_path.write_text(adapted, encoding="utf-8")
    slot["adapter"] = adapter
    slot["staged_script"] = script_path.name


def _raw(repo: str, commit: str, path: str, urllib_request) -> bytes:
    import urllib.parse
    quoted = urllib.parse.quote(path, safe="/")
    url = f"https://raw.githubusercontent.com/{repo}/{commit}/{quoted}"
    with urllib_request.urlopen(url, timeout=60) as response:
        return response.read()


def _apply_adapter(source: str, csv_path: Path):
    """Blank colab lines and retarget read_csv. Other lines stay put."""
    adapter = []
    lines = source.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if any(token in line for token in ("google.colab", "drive.mount", "files.upload")):
            lines[index] = "\n"
            adapter.append({"op": "blank_colab_line", "line": index + 1})
    source = "".join(lines)
    if csv_path is None:
        return source, adapter
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, adapter
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        name = func.attr if isinstance(func, ast.Attribute) else (func.id if isinstance(func, ast.Name) else "")
        if name != "read_csv":
            continue
        arg = node.args[0]
        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
            continue
        if Path(arg.value).name == csv_path.name and not arg.value.startswith(("/", "\\")) and ":" not in arg.value:
            continue
        edited = _retarget(source, arg, csv_path.name)
        if edited != source:
            adapter.append({"op": "retarget_read_csv", "line": arg.lineno, "to": csv_path.name})
            source = edited
            break
    return source, adapter


def _retarget(source: str, arg: ast.Constant, name: str) -> str:
    lines = source.splitlines(keepends=True)
    raw = lines[arg.lineno - 1]
    nl = ""
    body = raw
    if body.endswith("\n"):
        body, nl = body[:-1], "\n"
    lines[arg.lineno - 1] = body[:arg.col_offset] + repr(name) + body[arg.end_col_offset:] + nl
    return "".join(lines)


def _execute(cache: Path, script_rel: str):
    """Run one unmutated script. A timeout kills the process tree.

    ``subprocess.run`` on Windows kills the child and then waits on pipes
    the grandchildren still hold, so the wait never returns. Stdout and
    stderr go to files, and ``taskkill /T`` closes the tree.
    """
    import tempfile
    script = cache / Path(script_rel).name
    env = dict(os.environ)
    env["MPLBACKEND"] = "Agg"
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    with tempfile.TemporaryDirectory(prefix="al-qual-") as tmp:
        err_path = Path(tmp) / "err.txt"
        with err_path.open("w", encoding="utf-8", errors="replace") as err_file:
            proc = subprocess.Popen(
                [sys.executable, script.name],
                cwd=str(cache), env=env,
                stdout=subprocess.DEVNULL, stderr=err_file,
            )
            try:
                code = proc.wait(timeout=300)
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True, check=False,
                    )
                else:
                    proc.kill()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    pass
                return 1, "timeout"
        if code == 0:
            return 0, ""
        err = err_path.read_text(encoding="utf-8", errors="replace")[-400:]
        return code, err


def _study2_static(pool_path: Path, index_key: str) -> None:
    """Judge one Study 2 pool. Does not touch the locked dev or held-out slots."""
    pool = json.loads(pool_path.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    study = manifest.setdefault("study2", {
        "dev": [], "heldout": [], "pending": [], "rejected": [], "next_index": 0,
    })
    known = _known_hits()
    followups = tuple(path for path, _query, _key in POOL4_FOLLOWUPS)
    for earlier in (POOL3, POOL4, POOL4B, POOL4C, *followups):
        if earlier.exists() and earlier != pool_path:
            for hit in json.loads(earlier.read_text(encoding="utf-8")):
                known.add((hit["repo"], hit["path"]))
    start = int(study.get(index_key) or 0)
    for index in range(start, len(pool)):
        hit = pool[index]
        study[index_key] = index + 1
        if (hit["repo"], hit["path"]) in known:
            _skip(hit, "already_in_earlier_pool", "study2")
            print(_ascii(f"skip {hit['repo']} {hit['path']}: already_in_earlier_pool"))
        else:
            reason = _classify(hit)
            if reason is None:
                count, names = _applicable(hit.get("_source", ""))
                if count < 2:
                    _skip(hit, "too_few_fault_sites", ",".join(names))
                    print(_ascii(f"skip {hit['repo']} {hit['path']}: too_few_fault_sites"))
                else:
                    hit.pop("_source", None)
                    hit["applicable"] = names
                    hit["qualified_run"] = False
                    study["pending"].append(hit)
                    print(_ascii(f"keep {hit['repo']} {hit['path']} faults={count}"))
            else:
                _skip(hit, reason[0], reason[1])
                print(_ascii(f"skip {hit['repo']} {hit['path']}: {reason[0]}"))
        known.add((hit["repo"], hit["path"]))
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        index_key: study.get(index_key),
        "pending": len(study.get("pending", [])),
    }))


def _applicable(source: str):
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from benchmarks.real.mutate import FAULTS, mutate
    names = [fault for fault in FAULTS if mutate(source, fault) is not None]
    return len(names), names


def _study2_run() -> None:
    """Qualify Study 2 pending hits. Does not plant faults or rewrite study 1."""
    import hashlib
    import urllib.request

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    study = manifest.setdefault("study2", {
        "dev": [], "heldout": [], "pending": [], "rejected": [], "next_index": 0,
    })
    pending = list(study.get("pending", []))
    rejected = list(study.get("rejected", []))
    done = {(s.get("repo"), s.get("path")) for s in rejected}
    done.update((s.get("repo"), s.get("path")) for s in study.get("dev", []))
    done.update((s.get("repo"), s.get("path")) for s in study.get("heldout", []))
    still = []
    for slot in pending:
        if slot.get("qualified_run"):
            continue
        if (slot.get("repo"), slot.get("path")) in done:
            continue
        if len(study["dev"]) >= STUDY2_DEV and len(study["heldout"]) >= STUDY2_HELDOUT:
            still.append(slot)
            continue
        cache = REAL / "cache" / slot["repo"].replace("/", "__") / slot["path"]
        try:
            _stage(slot, cache, urllib.request, hashlib)
        except Exception as exc:
            rejected.append(slot)
            _skip(slot, "does_not_run", repr(exc)[:300])
            print(_ascii(f"fail {slot['repo']} {slot['path']}: stage"))
            continue
        staged = (cache / Path(slot["path"]).name).read_text(encoding="utf-8", errors="replace")
        if "streamlit" in staged or "import flask" in staged or "from flask" in staged:
            rejected.append(slot)
            _skip(slot, "server_does_not_exit", "")
            print(_ascii(f"skip {slot['repo']} {slot['path']}: server_does_not_exit"))
            study["rejected"] = rejected
            MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            continue
        try:
            code, detail = _execute(cache, slot["path"])
        except Exception as exc:
            code, detail = 1, repr(exc)[:300]
        if code == 0 and len(study["dev"]) < STUDY2_DEV or code == 0 and len(study["heldout"]) < STUDY2_HELDOUT:
            slot["qualified_run"] = True
            _place_study2(study, slot)
            print(_ascii(f"ran {slot['repo']} {slot['path']} -> {slot['slot']}"))
        elif code == 0:
            slot["qualified_run"] = True
            still.append(slot)
            print(_ascii(f"spare {slot['repo']} {slot['path']}"))
        else:
            slot["qualified_run"] = False
            rejected.append(slot)
            _skip(slot, "does_not_run", detail)
            print(_ascii(f"fail {slot['repo']} {slot['path']}: {detail[:120]}"))
        study["rejected"] = rejected
        study["pending"] = still + [s for s in pending if s is not slot and not s.get("qualified_run") and s not in rejected]
        MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    study["pending"] = still
    study["rejected"] = rejected
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "dev": len(study["dev"]),
        "heldout": len(study["heldout"]),
        "rejected": len(rejected),
        "pending": len(study["pending"]),
    }))


def _place_study2(study: dict, slot: dict) -> None:
    if len(study["dev"]) < STUDY2_DEV:
        slot["role"] = "development"
        slot["slot"] = f"s2-dev-{len(study['dev']) + 1}"
        study["dev"].append(slot)
    elif len(study["heldout"]) < STUDY2_HELDOUT:
        slot["role"] = "heldout"
        slot["slot"] = f"s2-heldout-{len(study['heldout']) + 1}"
        study["heldout"].append(slot)
    else:
        slot["role"] = "unused"
        slot["slot"] = ""


if __name__ == "__main__":
    sys.exit(main())
