"""LLM-as-a-Judge: score the quality of the assistant's answers with a rubric.

run_eval.py checks whether the numbers are right. Every configuration already scores 100% there,
so it cannot tell them apart. This script reads the saved answers and asks a second model (the judge)
to score how good each answer is, using the rubric below. No new assistant calls are made.

Usage:
    python -m eval.judge eval/results_test_claude-haiku-5-5_v2.csv   # judge one file
    python -m eval.judge eval/results_*.csv                          # judge several
    python -m eval.judge --summary                                   # table of all judged files

Output: eval/judged/<same name>.csv with one score per criterion and the judge's reason.
The judge model defaults to Claude Sonnet, a different model from the Haiku answers it grades.
Set JUDGE_MODEL to change it.
"""
import csv
import glob
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "judged"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "claude-sonnet-5-5")

# Each criterion is scored 0, 1 or 2. Keep the descriptions concrete so scores are repeatable.
RUBRIC = {
    "faithful": "Every number in the answer is supported by the query results shown, or follows by simple arithmetic from them, or comes from the background rules. "
                "2 = all supported; 1 = small rounding or wording issue; 0 = a number is invented or wrong.",
    "direct": "The first line answers the question directly. "
              "2 = yes; 1 = the answer is there but buried; 0 = the question is not answered.",
    "definition": "The answer states how the number was calculated (measure, period, filters), e.g. a "
                  "'Definition:' or '口径：' line. 2 = clear and correct; 1 = partial or vague; 0 = missing.",
    "concise": "No filler, no repetition, at most about three supporting points. "
               "2 = tight; 1 = some padding; 0 = long or rambling.",
    "scope": "For questions the data cannot answer: says so, explains why, and offers the closest question "
             "it can answer. For answerable questions: does not wrongly refuse and does not overclaim "
             "(e.g. causes, forecasts). 2 = handled well; 1 = partly; 0 = guesses or wrongly refuses.",
}
MAX_SCORE = 2 * len(RUBRIC)

from assistant.prompts import BUSINESS_RULES, SCHEMA  # noqa: E402
BACKGROUND = SCHEMA + "\n\n" + BUSINESS_RULES

PROMPT = """You are grading an AI data assistant that answers questions about Australian PBS prescription
data by writing SQL. Grade ONLY the final answer text, using the query result as the ground truth.

Question:
{question}

Every query the assistant ran, with up to 50 result rows each (JSON):
{queries}

Background the assistant was given and may state without a query (not a hallucination):
{rules}

Assistant's final answer:
{answer}

Score each criterion 0, 1 or 2:
{rubric}

Call the submit_scores tool with your scores. Do not write anything else."""


SCORE_TOOL = {
    "name": "submit_scores",
    "description": "Submit the rubric scores for this answer.",
    "input_schema": {
        "type": "object",
        "properties": {**{k: {"type": "integer", "minimum": 0, "maximum": 2, "description": v}
                          for k, v in RUBRIC.items()},
                       "reason": {"type": "string",
                                  "description": "One short sentence on the main weakness, or 'none'."}},
        "required": list(RUBRIC) + ["reason"],
    },
}


def _json_from_text(text):
    """Fallback: take the last {...} block in a text reply that parses as JSON."""
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", text, re.S))):
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            continue
    return None


def judge_one(client, row, retries=2):
    """Ask the judge for scores through a tool call (structured output).

    Notes from building this:
    - v1 asked for JSON in plain text: replies were cut off (token limit too low) or started with
      reasoning before the JSON, so most failed to parse.
    - v2 forced the tool with tool_choice, but this model rejects forced tool choice (HTTP 400).
    - v3 (this one): the tool is offered and the prompt asks for it; if the judge still replies in
      text, the last JSON object in the text is used. Failures are retried, then recorded.
    """
    rubric = "\n".join(f"- {k}: {v}" for k, v in RUBRIC.items())
    queries = row.get("model_queries") or json.dumps(
        [{"sql": row.get("model_sql") or "(no query)", "rows (first 5 only)": row.get("model_rows") or "[]"}])
    prompt = PROMPT.format(question=row["question"], queries=queries, rules=BACKGROUND,
                           answer=row.get("answer") or "", rubric=rubric)
    last = None
    for _ in range(retries + 1):
        resp = client.messages.create(model=JUDGE_MODEL, max_tokens=2000, tools=[SCORE_TOOL],
                                      messages=[{"role": "user", "content": prompt}])
        calls = [b for b in resp.content if b.type == "tool_use"]
        if calls:
            data = calls[0].input
        else:
            text = "".join(getattr(b, "text", "") for b in resp.content if b.type == "text")
            data = _json_from_text(text)
        if not data:
            last = "no scores returned"
            continue
        try:
            scores = {k: max(0, min(2, int(data[k]))) for k in RUBRIC}
            return scores, str(data.get("reason", ""))
        except (KeyError, TypeError, ValueError) as e:
            last = f"bad scores {data}: {e}"
    raise ValueError(last)


def judge_file(path):
    import anthropic

    client = anthropic.Anthropic()
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    out_rows = []
    for row in rows:
        try:
            scores, reason = judge_one(client, row)
        except Exception as e:  # keep going; a failed judgement is recorded, not hidden
            scores, reason = {k: "" for k in RUBRIC}, f"JUDGE ERROR: {e}"
        total = sum(scores.values()) if all(v != "" for v in scores.values()) else ""
        print(f"Q{row['id']:>3} {str(total):>2}/{MAX_SCORE}  {reason}")
        out_rows.append({"id": row["id"], "type": row["type"], "question": row["question"],
                         "correct": row["correct"], **scores, "total": total,
                         "reason": reason, "answer": row["answer"]})
    OUT.mkdir(exist_ok=True)
    out = OUT / Path(path).name
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_rows[0].keys())
        w.writeheader()
        w.writerows(out_rows)
    print(f"-> {out}\n")


def summary():
    files = sorted(glob.glob(str(OUT / "*.csv")))
    if not files:
        print("No judged files yet. Run: python -m eval.judge eval/results_*.csv")
        return
    head = f"{'file':<42}" + "".join(f"{k:>11}" for k in RUBRIC) + f"{'avg total':>11}"
    print(head)
    print("-" * len(head))
    for f in files:
        all_rows = list(csv.DictReader(open(f, encoding="utf-8")))
        rows = [r for r in all_rows if r["total"] != ""]
        if len(rows) < len(all_rows):
            print(f"  ({len(all_rows) - len(rows)} judge errors skipped in {Path(f).stem})")
        if not rows:
            continue
        avg = {k: sum(int(r[k]) for r in rows if r[k] != "") / len(rows) for k in RUBRIC}
        tot = sum(int(r["total"]) for r in rows) / len(rows)
        print(f"{Path(f).stem:<42}" + "".join(f"{avg[k]:>11.2f}" for k in RUBRIC)
              + f"{tot:>8.1f}/{MAX_SCORE}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args == ["--summary"]:
        summary()
    else:
        for p in args:
            judge_file(p)
        summary()
