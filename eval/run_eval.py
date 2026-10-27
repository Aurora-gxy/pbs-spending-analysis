"""Evaluate the assistant against questions with known correct answers.

Usage:  python -m eval.run_eval            # runs prompt v1 and v2
        python -m eval.run_eval v2         # one version only

For each question we run the reference (gold) SQL and the assistant, then check whether
every value in the gold result appears in the assistant's result. Numbers match within 1%,
also after common unit changes (e.g. A$24.23B vs 24229568191, 15.4% vs 0.154).
Results go to eval/results_<version>.csv; review the failures and fill in error_type.
"""
import csv
import re
import json
import sys
from pathlib import Path

from assistant.agent import ask, MODEL
from assistant.db import run_sql

HERE = Path(__file__).parent
SCALES = (1, 100, 0.01, 1e3, 1e-3, 1e6, 1e-6, 1e9, 1e-9)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def value_match(gold, cand):
    g, c = _num(gold), _num(cand)
    if g is not None and c is not None:
        if g == 0:
            return abs(c) < 1e-9
        return any(abs(c * s - g) / abs(g) <= 0.01 for s in SCALES)
    return str(gold).strip().upper() == str(cand).strip().upper()


NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def answer_numbers(text):
    """Numbers written in the answer, with their decimal places (e.g. 'A$24.23B' -> (24.23, 2))."""
    out = []
    for m in NUM_RE.findall(text or ""):
        s = m.replace(",", "")
        d = len(s.split(".")[1]) if "." in s else 0
        out.append((float(s), d))
    return out


def text_value_match(gold, text, nums):
    g = _num(gold)
    if g is None:
        return str(gold).strip().upper() in (text or "").upper()
    for c, d in nums:
        for k in SCALES:
            gv = g * k
            if abs(gv) > 0 and (abs(c - gv) / abs(gv) <= 0.01 or abs(round(gv, d) - c) < 0.51 * 10 ** -d):
                return True
    return False


def rows_match(gold_rows, cand_rows, answer=""):
    """Every gold row must be found either in one result row of any query the model ran,
    or (for derived numbers such as growth %) stated in the answer text."""
    nums = answer_numbers(answer)
    for g in gold_rows:
        in_rows = any(all(any(value_match(gv, cv) for cv in c) for gv in g) for c in cand_rows)
        in_text = all(text_value_match(gv, answer, nums) for gv in g)
        if not (in_rows or in_text):
            return False
    return True


REFUSAL_MARKERS = ("does not contain", "doesn't contain", "does not include", "doesn't include",
                   "not available", "no data", "not in the data", "cannot", "can't", "unable",
                   "does not have", "doesn't have", "not possible", "doesn't say", "does not say",
                   "can't say", "can't tell", "isn't in the data", "is not in the data", "无法", "不包含", "没有")


def refused(res):
    """An out-of-scope question passes if the answer says the data cannot answer it."""
    text = (res.get("answer") or "").lower()
    return any(m in text for m in REFUSAL_MARKERS)


def auto_tag(res, correct):
    if correct:
        return ""
    if res["sql"] is None:
        return "no_query"
    if res["error"]:
        return "sql_error"
    if not res["rows"]:
        return "empty_result"
    return "wrong_result"


SETS = {"dev": "questions.json", "test": "questions_test.json"}


def gold_options(item):
    """Gold results for a question. Ambiguous questions list several accepted readings in sql_any."""
    sqls = item.get("sql_any") or [item["sql"]]
    opts = []
    for sql in sqls:
        _, rows, err = run_sql(sql)
        assert not err, (item["id"], err)
        opts.append(rows)
    return opts


def run(version, qset="dev"):
    questions = json.loads((HERE / SETS[qset]).read_text())
    out_rows, n_ok = [], 0
    for item in questions:
        options = [] if item.get("expect") == "refuse" else gold_options(item)
        gold_rows = options[0] if options else []
        try:
            res = ask(item["q"], version)
        except Exception as e:
            res = {"answer": "", "sql": None, "rows": [], "all_rows": [], "error": str(e), "steps": 0}
        if item.get("expect") == "refuse":
            ok = refused(res)
        else:
            cand = res.get("all_rows") or res["rows"]
            ok = any(rows_match(g, cand, res.get("answer", "")) for g in options)
        n_ok += ok
        print(f"[{qset}/{version}] Q{item['id']:>3} {'PASS' if ok else 'FAIL'}  {item['q']}")
        out_rows.append({
            "id": item["id"], "type": item["type"], "question": item["q"], "correct": int(ok),
            "auto_tag": ("answered_out_of_scope" if item.get("expect") == "refuse" and not ok
                         else auto_tag(res, ok)), "error_type": "", "steps": res["steps"],
            "model_sql": res["sql"], "gold_sql": " || ".join(item.get("sql_any") or [item.get("sql", "(should refuse)")]),
            "model_rows": json.dumps(res["rows"][:5], default=str, ensure_ascii=False),
            "gold_rows": json.dumps(gold_rows[:5], default=str, ensure_ascii=False),
            "answer": res["answer"],
        })
    path = HERE / f"results_{qset}_{MODEL}_{version}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_rows[0].keys())
        w.writeheader()
        w.writerows(out_rows)
    by_type = {}
    for r in out_rows:
        t = by_type.setdefault(r["type"], [0, 0])
        t[0] += r["correct"]; t[1] += 1
    print(f"[{version}] by type: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in by_type.items()))
    acc = 100 * n_ok / len(questions)
    print(f"\n[{version}] accuracy: {n_ok}/{len(questions)} = {acc:.0f}%   -> {path}\n")
    return acc


if __name__ == "__main__":
    args = sys.argv[1:]
    qset = "test" if "--test" in args else "dev"
    versions = [a for a in args if a in ("v1", "v2")] or ["v1", "v2"]
    summary = {v: run(v, qset) for v in versions}
    print(f"Summary [{qset} set] ({MODEL}):", ", ".join(f"{v} {a:.0f}%" for v, a in summary.items()))
