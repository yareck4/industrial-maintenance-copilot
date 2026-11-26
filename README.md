# industrial-maintenance-copilot

# ⚙️ Industrial Maintenance Copilot (RAG)

A technical assistant powered by **Retrieval-Augmented Generation (RAG)** designed to query industrial machinery, robotic arm, and PLC manuals in natural language. The system retrieves verified technical data and delivers structured step-by-step diagnostics while citing exact source files and page numbers to prevent operational hallucinations.

---

## 🏗️ System Architecture

1. **Ingestion & Chunking (`ingestor.py`):** Parses PDF documents from `manuales_pdf/`, splits text into overlapping chunks, and preserves source metadata (filename and page number).
2. **Local Vectorization:** Uses `sentence-transformers` (`all-MiniLM-L6-v2`) to generate embeddings locally at zero API cost and stores them persistently in `ChromaDB`.
3. **Retrieval & High Availability (`app.py`):** Retrieves the most relevant chunks via semantic similarity and queries the Google Gemini API (`google-genai`). Built with a fault-tolerant architecture featuring **exponential backoff retries**, **automatic model fallback**, and a **local contingency mode** if cloud servers experience high demand.

---

## 📂 Project Structure

```text
industrial-maintenance-copilot/
├── manuales_pdf/       # Directory for technical manuals (.pdf)
├── chroma_db/          # Locally generated vector database (ignored in Git)
├── ingestor.py         # PDF parsing, chunking, and ChromaDB ingestion script
├── app.py              # Streamlit web interface with RAG & resilience logic
├── requirements.txt    # Project dependencies
├── .gitignore          # Excludes virtual environments, cache, and local DBs
└── README.md           # Technical documentation and troubleshooting guide
```

---

## 🚀 Installation & Usage

### 1. Set up the virtual environment
Open a terminal inside the project root directory (`industrial-maintenance-copilot/`) and run:

```bash
python -m venv venv
venv\Scripts\activate
pip install --default-timeout=1000 -r requirements.txt
```

### 2. Ingest technical manuals
Place one or more `.pdf` manuals inside the `manuales_pdf/` folder and run the ingestion script:

```bash
python ingestor.py
```
*Verify in the terminal output that a positive number of chunks was saved before moving to the next step.*

### 3. Launch the Copilot
Get a free API Key from [Google AI Studio](https://google.com) and start the web app:

```bash
streamlit run app.py
```
Enter your API Key in the left sidebar and submit your technical query.

---

## 🛠️ Troubleshooting & Lessons Learned

During local development and deployment (Windows 11 + VS Code), the following common RAG engineering issues were identified and resolved:

### 1. `Python was not found` or `.msix` installer blocked on Windows 11
* **Cause:** Windows 11 group policies may block modern `.msix` packages (*App Installer / Sideloading policy*) or fail to register Python in the system `PATH`.
* **Solution:** Install Python directly from the official **Microsoft Store** or download the classic **`Windows installer (64-bit) .exe`** and make sure to check **`Add python.exe to PATH`**. Restart VS Code completely after installation.

### 2. Network timeouts (`ReadTimeoutError` / `SSLError`) on heavy dependencies
* **Cause:** `sentence-transformers` pulls large packages (such as PyTorch > 2 GB), causing `pip` to abort on brief connection drops.
* **Solution:** Increase the timeout flag using `--default-timeout=1000` and install heavy packages individually (`pip install --default-timeout=1000 sentence-transformers`). Re-running the command resumes from `pip`'s local cache.

### 3. VS Code unresolved import warnings (`Import "chromadb" could not be resolved`)
* **Cause:** VS Code defaults to the global Python interpreter or a parent directory's `.venv` instead of the project's virtual environment.
* **Solution:** Press `Ctrl + Shift + P` -> `Python: Select Interpreter` -> `Enter Interpreter Path...` and manually point to `.\industrial-maintenance-copilot\venv\Scripts\python.exe`.

### 4. Empty vector database (`0 chunks`) or duplicate directories
* **Cause:** Both `ingestor.py` and `app.py` rely on relative paths (`./chroma_db` and `manuales_pdf`). Running scripts from a parent folder (e.g., `git/` instead of `git/industrial-maintenance-copilot/`) creates an empty database in the wrong directory.
* **Solution:** Always `cd industrial-maintenance-copilot` before running scripts. If an empty database was generated, delete it in PowerShell via `Remove-Item -Recurse -Force chroma_db` and re-run `python ingestor.py`.

### 5. API `503 UNAVAILABLE` (High Demand) or `404 NOT_FOUND` errors
* **Cause:** Free-tier cloud models experience temporary traffic spikes (`503`) or model version deprecations (`404`).
* **Solution:** Implemented a 3-layer resilience handler in `app.py`:
  1. Automatic retries with exponential backoff (`time.sleep(2 ** attempt)`).
  2. Automatic model cascade across multiple endpoints (`gemini-3.5-flash-lite`, `gemini-3.6-flash`, `gemini-3.8-flash`).
  3. **Local Contingency Mode** that displays raw retrieved chunks along with source filenames and page numbers if all cloud models are unreachable.

### 6. Prompt size vs. latency and reliability
* **Cause:** Overly verbose system prompts increase input token count, latency, and rejection rates under high server load.
* **Solution:** Keep the system prompt concise, direct, and strictly grounded in the retrieved context, prioritizing speed and factual accuracy over conversational filler.

### 7. Accidentally tracking virtual environments or vector DBs in Git
* **Cause:** Initializing a repository without a `.gitignore` causes Git to stage thousands of files from `venv/` and binary files from `chroma_db/`.
* **Solution:** Add a `.gitignore` excluding `venv/`, `.venv/`, `chroma_db/`, `__pycache__/`, and `.env`. If already staged, clear the index with `git rm -r --cached .` before committing.

## 💡 Quick Technical Tips & Architecture Insights

* **Chunking & Overlap (`tamano=800, solapamiento=150`):** Splitting text with a 150-character overlap ensures that critical specs or error codes sitting right at the edge of a cut aren't broken in half, preserving full context across segments.
* **Why Local Embeddings (`all-MiniLM-L6-v2`)?** Running the embedding model locally means indexing hundreds of manual pages costs **$0 in API tokens** and keeps sensitive technical documents private during vectorization.
* **Semantic Search vs. Keyword Search:** Unlike `Ctrl + F`, ChromaDB compares vector meanings. Searching for *"arm won't move"* will still retrieve sections titled *"Servo Drive Fault"* or *"Axis Locked"*.
* **Streamlit Caching (`@st.cache_resource`):** The embedding model (~80 MB) and ChromaDB connection are cached in memory so they load only once at startup, preventing UI freezes on every new question.
* **Strict Grounding Prompt:** Forcing the LLM to answer *only* from retrieved chunks prevents dangerous industrial hallucinations (like inventing torque values or voltage tolerances).
* **Updating Manuals Safely:** If you add or replace PDFs inside `manuales_pdf/`, delete the `chroma_db/` folder before re-running `ingestor.py` so old or duplicate vectors don't mix with new ones.
* **API Key Security:** Never hardcode your Gemini API Key inside `app.py` or push it to GitHub. Keep it as a runtime UI input or load it via environment variables (`.env`).
