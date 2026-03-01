from pathlib import Path
import shutil

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

ROOT_DIR = Path(__file__).resolve().parents[1]
CORPUS_DIR = ROOT_DIR / "corpus"
PERSIST_DIR = ROOT_DIR / "rag_store"

COLLECTION_NAME = "banking-copilot"
EMB_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

def load_markdown(root: Path):
    docs = []
    md_files = list(root.rglob("*.md"))
    print(f"[build_index] Found md files: {len(md_files)} under {root}")

    for p in md_files:
        loaded = TextLoader(str(p), encoding="utf-8").load()
        rel_source = p.relative_to(ROOT_DIR).as_posix()
        for d in loaded:
            d.metadata["source"] = rel_source
        docs.extend(loaded)
    return docs

def main():
    if not CORPUS_DIR.exists():
        raise SystemExit(f"Corpus directory not found: {CORPUS_DIR}")

    raw_docs = load_markdown(CORPUS_DIR)
    if not raw_docs:
        raise SystemExit("No markdown files found under corpus/")

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(raw_docs)

    if PERSIST_DIR.exists():
        shutil.rmtree(PERSIST_DIR)  # clear old index

    embeddings = HuggingFaceEmbeddings(model_name=EMB_MODEL)

    db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(PERSIST_DIR),
        collection_name=COLLECTION_NAME,
    )
    db.persist()

    db_check = Chroma(
        persist_directory=str(PERSIST_DIR),
        embedding_function=embeddings,
        collection_name=COLLECTION_NAME,
    )

    print(
        f"[build_index] docs={len(raw_docs)} chunks={len(chunks)} "
        f"stored_vectors={db_check._collection.count()} saved={PERSIST_DIR}"
    )

if __name__ == "__main__":
    main()