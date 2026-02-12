# Banking Copilot (Local LLM RAG)

A privacy-first **Banking Operations Copilot** that answers internal SOP/FAQ/policy questions using **Retrieval-Augmented Generation (RAG)** with a **fully local LLM (Ollama)**.

This portfolio project demonstrates “bank-grade” design principles:
- local inference (no cloud LLM by default)
- strict document grounding + citations
- OTP/PIN/password refusal guardrail
- safe fallback for out-of-scope questions

---

## What this project does

Given a user question (e.g., *"What is the SOP for transaction disputes?"*), the system:
1) retrieves relevant SOP/FAQ/policy chunks from a local vector database (Chroma),
2) builds a strict prompt containing only retrieved context,
3) calls a local LLM (Ollama) to produce a procedural answer,
4) returns the answer with citations to the exact source files used.

---

## Key Features

- **Local LLM RAG**: FastAPI + Chroma + local Ollama model
- **Citations**: answers include source document paths
- **Relevance gating**: if retrieval is weak, the system returns  
  **"Insufficient information in the provided documents."**
- **Security guardrails**:
  - blocks OTP/PIN/password/verification code requests
  - basic masking for long digit sequences (demo)

---

## Tech Stack

- WSL2 Ubuntu (recommended)
- Python 3.12+
- FastAPI + Uvicorn
- Chroma (vector store)
- LangChain (community integrations)
- sentence-transformers embeddings
- Ollama (local LLM runtime)

---

## Project Structure

```text
banking-copilot/
├─ api/main.py                 # API (RAG + local LLM + guardrails)
├─ ingestion/build_index.py     # Build Chroma index from corpus/
├─ corpus/                     # SOP/FAQ/policy markdown docs
└─ rag_store/                  # Generated Chroma persistence folder

## Quick Start (Run Demo)

1. Setup Python venv
    cd ~/projects/banking-copilot
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -U pip

Install dependencies:

- If you have requirements.txt:
    pip install -r requirements.txt

-Otherwise (MVP):
    pip install fastapi uvicorn requests chromadb \
    langchain langchain-community langchain-text-splitters \
    sentence-transformers pydantic

2. Build index (corpus -> rag_store)
    python ingestion/build_index.py
    ls -la rag_store

3. Install & pull local LLM (Ollama)
    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull llama3.2:3b
    curl http://127.0.0.1:11434/api/tags


4. Run API
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000


## Demo Requests

A. Retrieval-only (Debug)
    curl -X POST "http://localhost:8000/ask" \
    -H "Content-Type: application/json" \
    -d '{"question":"What is the SOP for transaction disputes?", "top_k": 3}'

B. LLM RAG (answer + citations)
    curl -X POST "http://localhost:8000/ask_llm" \
    -H "Content-Type: application/json" \
    -d '{"question":"What is the SOP for transaction disputes?", "top_k": 3}'

C. Out-of-scope (must refuse safely)
    curl -X POST "http://localhost:8000/ask_llm" \
    -H "Content-Type: application/json" \
    -d '{"question":"How do I change my credit card billing cycle?", "top_k": 3}'

D. OTP guardrail (must refuse)
    curl -X POST "http://localhost:8000/ask_llm" \
    -H "Content-Type: application/json" \
    -d '{"question":"My OTP is 123456. Help me login.", "top_k": 3}'

## Safety & Privacy Notes
- This project is designed to run locally (privacy-first).
- The system refuses OTP/PIN/password/verification code requests.
- Answers are grounded in local documents; if documents do not support an answer, the system returns:
"Insufficient information in the provided documents."

## Disclaimer
This is a portfolio project using synthetic/demo documents.