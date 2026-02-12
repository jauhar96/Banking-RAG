from pathlib import Path
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

CORPUS_DIR = Path("corpus")
PERSIST_DIR = "rag_store"

def load_markdown(root: Path):
    docs = []
    for p in root.rglob("*.md"):
        loaded = TextLoader(str(p), encoding="utf-8").load()
        for d in loaded:
            d.metadata["souce"] = str(p)
        docs.extend(loaded)
    return docs

def main():
    raw_docs = load_markdown(CORPUS_DIR)
    if not raw_docs:
        raise SystemExit("No markdown files found under corpus/")
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    chunks = splitter.split_documents(raw_docs)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    db = Chroma.from_documents(chunks, embeddings, persist_directory=PERSIST_DIR)
    db.persist()
    print(f"docs={len(raw_docs)} chunks={len(chunks)} saved={PERSIST_DIR}")
if __name__ == "__main__":
    main()
