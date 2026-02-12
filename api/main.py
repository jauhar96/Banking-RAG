import re
import requests
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

# ====== Vector store config ======
PERSIST_DIR = "rag_store"

# IMPORTANT: must match EXACTLY what you used in ingestion/build_index.py
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# ====== Ollama config ======
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b"

# ====== Retrieval gating ======
MIN_RELEVANCE = 0.35  # lower to ~0.30 if too strict

# ====== Guardrail citations (must exist in your corpus) ======
POLICY_PII = "corpus/policy_pii_handling.md"
SOP_ATO = "corpus/sop/sop_account_takeover.md"

app = FastAPI(title="Banking Copilot (Local LLM RAG)")

class AskRequest(BaseModel):
    question: str
    top_k: int = 4

# ---------------------------
# Utilities
# ---------------------------
def load_db():
    emb = HuggingFaceEmbeddings(model_name=EMB_MODEL)
    return Chroma(persist_directory=PERSIST_DIR, embedding_function=emb)

def mask_sensitive(text: str) -> str:
    """
    Mask long digit sequences so we don't echo potentially sensitive numbers.
    Example: 123456789012 -> ****9012
    """
    def repl(m):
        s = m.group(0)
        return "****" + s[-4:]
    # account-like / card-like sequences (simple demo)
    text = re.sub(r"\b\d{8,16}\b", repl, text)
    return text

def is_credential_request(q: str) -> bool:
    """
    Detect OTP/PIN/password intent (EN + ID).
    We also match common variants like "kode otp", "kata sandi", etc.
    """
    ql = q.lower()
    keywords = [
        # English
        "otp", "one time password", "verification code", "2fa",
        "pin", "password", "passcode",
        # Indonesian
        "kode verifikasi", "kode otp", "kata sandi", "sandi", "pin atm",
        "kode sms", "kode 2fa", "kode autentikasi",
    ]
    return any(k in ql for k in keywords)

def build_prompt(question: str, docs) -> str:
    blocks = []
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get("source", "unknown")
        txt = mask_sensitive(d.page_content[:1500])
        blocks.append(f"[Doc {i}] SOURCE: {src}\n{txt}")

    context = "\n\n---\n\n".join(blocks)

    return f"""
You are a Banking Operations Copilot for a digital bank.

STRICT RULES (must follow):
1) Answer ONLY using the provided CONTEXT. Do not use outside knowledge.
2) If the answer is not in CONTEXT, reply exactly: "Insufficient information in the provided documents."
3) NEVER ask for or store OTP, PIN, password, or verification codes.
4) If the user requests OTP/PIN/password, refuse and remind them never to share it.
5) Keep the answer concise, procedural, and safe for customer operations.
6) At the end, output "Citations:" listing the SOURCE paths you used (from the CONTEXT).
7) Do not cite anything outside the provided SOURCE list.

QUESTION:
{question}

CONTEXT:
{context}

OUTPUT FORMAT:
Answer:
- <your final answer in bullet steps>

Citations:
- <SOURCE path 1>
- <SOURCE path 2>
""".strip()

def call_ollama(prompt: str) -> str:
    r = requests.post(
        OLLAMA_URL,
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=180,
    )
    r.raise_for_status()
    return r.json().get("response", "").strip()

def parse_citations(text: str) -> List[str]:
    lines = text.splitlines()
    out = []
    in_cite = False

    for ln in lines:
        if ln.strip().lower() == "citations:":
            in_cite = True
            continue
        if in_cite:
            if not ln.strip():
                continue
            if ln.lstrip().startswith("-"):
                out.append(ln.split("-", 1)[1].strip())
            else:
                break

    # unique preserve order
    seen = set()
    uniq = []
    for c in out:
        if c not in seen:
            seen.add(c)
            uniq.append(c)
    return uniq

def enforce_citation_subset(citations: List[str], docs) -> List[str]:
    allowed = {d.metadata.get("source", "unknown") for d in docs}
    return [c for c in citations if c in allowed]

def retrieve_with_scores(db, question: str, k: int):
    """
    Returns list of (doc, score) where score is usually 0..1 (higher better).
    If the vectorstore doesn't support scores, returns (doc, None).
    """
    try:
        return db.similarity_search_with_relevance_scores(question, k=k)
    except Exception:
        docs = db.similarity_search(question, k=k)
        return [(d, None) for d in docs]

def should_answer(pairs, min_score: float = MIN_RELEVANCE) -> bool:
    if not pairs:
        return False
    if pairs[0][1] is None:
        return True  # no scores available
    best = max(score for _, score in pairs if score is not None)
    return best >= min_score

# ---------------------------
# Endpoints
# ---------------------------
@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
def ask(req: AskRequest):
    """
    Retrieval-only endpoint (debug).
    """
    db = load_db()
    q = mask_sensitive(req.question)  # UPGRADE: mask user question too
    pairs = retrieve_with_scores(db, q, req.top_k)

    retrieved = []
    for d, score in pairs:
        retrieved.append({
            "source": d.metadata.get("source", "unknown"),
            "score": score,
            "content": d.page_content[:600]
        })

    return {
        "question": q,
        "retrieved": retrieved
    }

@app.post("/ask_llm")
def ask_llm(req: AskRequest):
    """
    Full RAG: retrieve -> gate -> call local LLM -> enforce citations -> return.
    """
    # UPGRADE: mask user question first to avoid echoing sensitive numbers anywhere
    q = mask_sensitive(req.question)

    # Hard guardrail BEFORE retrieval/LLM
    if is_credential_request(q):
        return {
            "question": q,
            "answer": (
                "I can’t help with OTP/PIN/password or verification codes. "
                "Never share them with anyone. If you suspect account compromise, "
                "follow the suspected account takeover (ATO) SOP and escalate to the risk/fraud team."
            ),
            "citations": [POLICY_PII, SOP_ATO],  # UPGRADE: better citations
            "retrieved": []
        }

    db = load_db()
    pairs = retrieve_with_scores(db, q, req.top_k)

    # Gate weak retrieval: do NOT call the LLM
    if not should_answer(pairs, min_score=MIN_RELEVANCE):
        return {
            "question": q,
            "answer": "Insufficient information in the provided documents.",
            "citations": [],
            "retrieved": []
        }

    docs = [d for d, _ in pairs]

    prompt = build_prompt(q, docs)
    answer_raw = call_ollama(prompt)

    citations = parse_citations(answer_raw)
    citations = enforce_citation_subset(citations, docs)

    retrieved = [
        {"source": d.metadata.get("source", "unknown"), "content": d.page_content[:600]}
        for d in docs
    ]

    # If model didn't produce valid citations, force safe fallback
    if not citations:
        return {
            "question": q,
            "answer": "Insufficient information in the provided documents.",
            "citations": [],
            "retrieved": retrieved
        }

    return {
        "question": q,
        "answer": answer_raw,
        "citations": citations,
        "retrieved": retrieved
    }