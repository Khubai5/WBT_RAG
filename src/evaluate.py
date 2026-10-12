"""Run repeatable offline retrieval and answer-guard checks for the MVP."""

import json

from .answer import answer_question
from .config import PROJECT_ROOT
from .errors import WBTError
from .retrieval import search


QUESTIONS_PATH = PROJECT_ROOT / "eval/questions.json"
REPORT_PATH = PROJECT_ROOT / "eval/report.json"


class NoModelCall:
    def invoke(self, _prompt):
        raise AssertionError("Offline evaluation attempted a Groq call.")


def check_case(case):
    kind = case["kind"]
    question = case["question"]
    region = case["region"]
    if kind == "clarify":
        def unexpected_search(*_args, **_kwargs):
            raise AssertionError("Clarification should stop before search.")
        result = answer_question(question, region, model=NoModelCall(), search_fn=unexpected_search)
        passed = "Which region" in result["answer"] and not result["model_called"]
        return {"passed": passed, "observed": result["answer"]}
    if kind == "current_price":
        result = answer_question(question, region, model=NoModelCall())
        passed = "do not establish a current price" in result["answer"] and not result["model_called"]
        return {"passed": passed, "observed": result["answer"]}
    matches = search(question, region=region, limit=3)
    observed = [item["metadata"]["source_id"] for item in matches]
    if kind == "no_evidence":
        return {"passed": not matches, "observed": observed}
    if kind == "retrieval":
        missing = sorted(set(case["expected_sources"]) - set(observed))
        return {"passed": not missing, "observed": observed, "missing_sources": missing}
    raise WBTError(f"Unknown evaluation kind: {kind}")


def main():
    cases = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        check = check_case(case)
        results.append({"id": case["id"], "kind": case["kind"], **check})
        print(f"{'PASS' if check['passed'] else 'FAIL'} {case['id']}: {check['observed']}")
    passed = sum(item["passed"] for item in results)
    report = {
        "scope": "offline PDF and allowlisted-web retrieval plus deterministic guards; no Groq calls",
        "passed": passed,
        "total": len(results),
        "results": results,
        "manual_review_pending": [
            "Compare extracted prices, currencies, testimonials, and conditions with the original PDFs.",
            "Run and review live Groq answers for citation accuracy and document-instruction resistance.",
            "Confirm regional website prices, terms, and effective dates with the WBT owner before calling them current approved policy.",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Offline checks: {passed}/{len(results)} passed. Report: eval/report.json. No Groq call was made.")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
