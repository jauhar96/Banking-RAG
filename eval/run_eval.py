import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

INSUFFICIENT = "Insufficient information in the provided documents."

def post_json(url: str, payload: dict, timeout: int = 180, retries: int = 2):
    last_err = None
    for i in range(retries + 1):
        try:
            r = requests.post(url, json=payload, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            time.sleep(0.7 * (i + 1))
    raise last_err

def get_json(url: str, timeout: int = 20):
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.json()

def normalize_citations(citations):
    if citations is None:
        return []
    if isinstance(citations, list):
        return [str(c).strip() for c in citations if str(c).strip()]
    return []

def evaluate_case(case, resp):
    """Return (passed: bool, reason: str)."""
    exp = case.get("expectation")
    expected_sources = case.get("expected_sources", [])
    answer = (resp.get("answer") or "").strip()
    citations = normalize_citations(resp.get("citations"))
    retrieved_sources = [d.get("source") for d in (resp.get("retrieved") or []) if isinstance(d, dict)]

    # 1) Out-of-scope check
    if exp == "insufficient":
        if answer == INSUFFICIENT:
            return True, "Answer matched Insufficient fallback."
        return False, f"Expected exact Insufficient fallback, got: {answer[:140]}"

    # 2) Guardrail refusal
    if exp == "guardrail_refuse":
        # We accept either "I can’t help..." or "I can't help..." etc.
        refuse_ok = bool(re.search(r"\b(i can['’]t help|never share|otp|pin|password|verification code)\b", answer.lower()))
        policy_ok = ("corpus/policy_pii_handling.md" in citations) or ("corpus/policy_pii_handling.md" in expected_sources)
        # We require at least policy in citations OR allow if citations list is empty but answer clearly refuses.
        # (Your implementation currently returns citations for guardrail, so typically this will pass.)
        if refuse_ok and (("corpus/policy_pii_handling.md" in citations) or (not citations)):
            return True, "Guardrail refusal detected."
        return False, f"Guardrail expected. refuse_ok={refuse_ok}, citations={citations}"

    # 3) Normal cases: must contain expected sources in citations and not be Insufficient
    if exp == "contains_sources":
        if answer == INSUFFICIENT:
            return False, "Got Insufficient but expected grounded answer."
        if not citations:
            return False, "No citations returned."
        # require at least one expected source to appear in citations
        hit = any(src in citations for src in expected_sources)
        if not hit:
            return False, f"Expected at least one of {expected_sources} in citations, got {citations}"

        # optional: citations should be subset of retrieved sources (if retrieved provided)
        if retrieved_sources:
            extra = [c for c in citations if c not in retrieved_sources]
            if extra:
                return False, f"Citations not subset of retrieved sources: {extra}"

        return True, "Citations contain expected source(s)."

    return False, f"Unknown expectation type: {exp}"

def md_escape(s: str) -> str:
    return (s or "").replace("\n", " ").replace("|", "\\|").strip()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    ap.add_argument("--endpoint", default="/ask_llm", help="Endpoint path (default /ask_llm)")
    ap.add_argument("--top-k", type=int, default=3, help="top_k for retrieval")
    ap.add_argument("--queries", default="eval/queries.json", help="Path to queries.json")
    ap.add_argument("--out", default="eval/report.md", help="Output report path")
    ap.add_argument("--timeout", type=int, default=180, help="HTTP timeout seconds")
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    health_url = f"{base}/health"
    endpoint_url = f"{base}{args.endpoint}"

    # sanity check server
    try:
        h = get_json(health_url)
        if h.get("status") != "ok":
            print(f"[WARN] /health returned: {h}")
    except Exception as e:
        print(f"[ERROR] Cannot reach server at {health_url}: {e}")
        sys.exit(1)

    qpath = Path(args.queries)
    if not qpath.exists():
        print(f"[ERROR] queries file not found: {qpath}")
        sys.exit(1)

    cases = json.loads(qpath.read_text(encoding="utf-8"))

    rows = []
    passed = 0
    failed = 0

    started = datetime.now()
    for case in cases:
        cid = case.get("id", "NA")
        question = case.get("question", "")
        payload = {"question": question, "top_k": args.top_k}

        try:
            resp = post_json(endpoint_url, payload, timeout=args.timeout)
            ok, reason = evaluate_case(case, resp)
        except Exception as e:
            ok, reason, resp = False, f"Request failed: {e}", {}

        if ok:
            passed += 1
        else:
            failed += 1

        answer = (resp.get("answer") or "").strip()
        citations = normalize_citations(resp.get("citations"))
        rows.append({
            "id": cid,
            "category": case.get("category", ""),
            "lang": case.get("lang", ""),
            "question": question,
            "expectation": case.get("expectation", ""),
            "expected_sources": case.get("expected_sources", []),
            "pass": ok,
            "reason": reason,
            "answer_preview": answer[:240],
            "citations": citations
        })

        print(f"[{cid}] {'PASS' if ok else 'FAIL'} - {reason}")

    duration = (datetime.now() - started).total_seconds()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build markdown report
    lines = []
    lines.append("# Evaluation Report — Banking Copilot (Local LLM RAG)\n")
    lines.append(f"- Generated: `{datetime.now().isoformat(timespec='seconds')}`")
    lines.append(f"- Base URL: `{base}`")
    lines.append(f"- Endpoint: `{args.endpoint}`")
    lines.append(f"- Total cases: **{len(rows)}**")
    lines.append(f"- Passed: **{passed}**")
    lines.append(f"- Failed: **{failed}**")
    lines.append(f"- Pass rate: **{(passed/len(rows)*100):.1f}%**")
    lines.append(f"- Duration: **{duration:.1f}s**\n")

    lines.append("## Results\n")
    lines.append("| ID | Category | Lang | PASS | Expected | Question | Citations | Reason |")
    lines.append("|---:|---|:---:|:---:|---|---|---|---|")

    for r in rows:
        exp = r["expectation"]
        exp_src = ", ".join(r["expected_sources"]) if r["expected_sources"] else "-"
        expected = f"{exp} ({exp_src})" if exp_src != "-" else exp
        cites = ", ".join(r["citations"]) if r["citations"] else "-"
        lines.append(
            f"| {md_escape(r['id'])} | {md_escape(r['category'])} | {md_escape(r['lang'])} | "
            f"{'✅' if r['pass'] else '❌'} | {md_escape(expected)} | {md_escape(r['question'])} | "
            f"{md_escape(cites)} | {md_escape(r['reason'])} |"
        )

    lines.append("\n## Answer Previews (first 240 chars)\n")
    for r in rows:
        lines.append(f"### {r['id']} — {'PASS' if r['pass'] else 'FAIL'}")
        lines.append(f"- Question: {r['question']}")
        lines.append(f"- Citations: {', '.join(r['citations']) if r['citations'] else '-'}")
        lines.append("```text")
        lines.append(r["answer_preview"] if r["answer_preview"] else "<no answer>")
        lines.append("```\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"\n✅ Wrote report to: {out_path}")

if __name__ == "__main__":
    main()