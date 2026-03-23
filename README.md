LIVE LINK: https://rag-assistant-j4bwmtgxuottghxnheayqv.streamlit.app/


###  PROJECT TESTING   ####


## Sample Questions and their answer by the RAG Assistant:


1. What factors affect construction project delays?

answer:
Based on the provided context, the documents describe mechanisms for *managing* and *preventing* delays (such as daily tracking, instant flagging of deviations, and penalisation) but do not list specific external factors that *cause* construction project delays (e.g., weather, supply chain issues, labor shortages).
Therefore, the answer is: I couldn't find information about that in the provided documents.

2. What safety regulations are mentioned in the uploaded files?

answer:
The quality system audits each construction phase for safety compliance.

3. What materials are specified for the project?

answer:
The context specifies the following materials for the project:
Cement – Pinnacle brand (ACC)

4. What is the timeline for project completion?

answer:
Fixed project timelines, with penalties for delays.

5. What quality control requirements are listed?

answer:
The quality system covers 445+ checkpoints across the construction lifecycle. Each construction phase is scored and audited for: - Structural integrity - Safety compliance - Execution accuracy.

6. Payment Safety & Stage Controls ?

answer:
Indecimal uses an escrow-based payment model where customer payments are made to an escrow account. A project manager verifies stage completion before funds are disbursed to the construction partner. This system is designed to reduce financial risk for customers and improve transparency and trust.

7. what is the maintenance program?

answer:
Based on the provided context, the maintenance program is described as follows:
Name: Zero Cost Maintenance Program (Post-Construction Support)
Purpose: To keep the home in good condition after handover.
Coverage Areas (Examples):
Plumbing, electrical
Wardrobe, masonry, modular kitchen
CP fittings, crack filling, tile support
Roofing, painting
External window & door main
Positioning: It is part of Indecimal's service offering, described as "post-handover maintenance support" and "long-term care positioning".

8. Financing Support ?

answer:
The financing support provided includes: - A **dedicated relationship manager** to assist with financing needs. - **Minimal documentation** required for the process. - **Confirmation within ~7 days** and **disbursal within ~30 days** (subject to terms and conditions/eligibility). - Funds are held in an **escrow account** until project stages are verified by a project manager, ensuring transparency and reducing financial risk for customers.
This system-driven approach aims to improve trust and clarity in the financing


## 📊 Quality Analysis

| # | Question                                         |Relevance|Hallucination|Completeness|
|---|--------------------------------------------------|---------|-------------|----------- |
| 1 | What factors affect construction project delays? | Low     | None        | N/A        |
| 2 | What safety regulations are mentioned?           | Medium  | None        | Partial    |
| 3 | What materials are specified for the project?    | High    | None        | Partial    |
| 4 | What is the timeline for project completion?     | Medium  | None        | Partial    |
| 5 | What quality control requirements are listed?    | High    | None        | Good       |
| 6 | Payment Safety & Stage Controls?                 | High    | None        | Good       |
| 7 | What is the maintenance program?                 | High    | None        | Excellent  |
| 8 | Financing Support?                               | High    | None        | Excellent  |


### Observations

- **Zero hallucinations** across all 8 tests. The strict prompt instruction
  ("answer only from retrieved context") worked as intended in every case.

- **Correct refusal on Q1**: When the documents described delay *management*
  but not delay *causes*, the model correctly said it couldn't find the answer
  rather than fabricating one.

- **Strong performance on specific topics**: Questions about the maintenance
  program, financing, payment controls, and quality checkpoints returned
  detailed and accurate answers, indicating good chunk retrieval for
  well-documented sections.

- **Partial answers on Q2, Q3, Q4**: These questions had relevant information
  spread across multiple document sections. Fixed-size chunking occasionally
  split related content, limiting how much the retriever could surface in a
  single top-k pass.






# Mini RAG - Construction Assistant

A Retrieval-Augmented Generation (RAG) chatbot that answers questions grounded strictly in uploaded construction documents.

---

## Architecture Overview

```text
Supported Documents (.pdf, .md, .doc, .docx)
     |
     v
[Text Extraction]
     |
     +-- pdfplumber for PDF
     +-- plain text reader for Markdown
     +-- python-docx for DOCX
     +-- Microsoft Word automation for DOC on Windows
     |
     v
[Chunking] -- 400-char chunks with 80-char overlap
     |
     v
[sentence-transformers: all-MiniLM-L6-v2] -- embed chunks
     |
     v
[FAISS IndexFlatL2] -- local vector index
     |
  User Query
     |
     v
[Embed query] --> [FAISS top-4 search] --> Retrieved Chunks
                                              |
                                              v
                                  [OpenRouter: openrouter/free]
                                              |
                                              v
                                    Final Grounded Answer
```

---

## Tech Stack

| Component | Tool | Cost |
|-----------|------|------|
| Embedding Model | `all-MiniLM-L6-v2` (`sentence-transformers`) | Free (local) |
| Vector DB | FAISS (local) | Free |
| LLM | OpenRouter (`openrouter/free`) | Free tier |
| Frontend | Streamlit | Free |
| PDF Parsing | `pdfplumber` | Free |
| DOCX Parsing | `python-docx` | Free |
| DOC Parsing | Microsoft Word automation on Windows | Local dependency |

---

## Running Locally

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/mini-rag.git
cd mini-rag
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get a free OpenRouter API key

- Go to [https://openrouter.ai](https://openrouter.ai)
- Sign up and create an API key

### 4. Run the app

```bash
streamlit run app.py
```

### 5. Use the app

1. Paste your OpenRouter API key in the sidebar
2. Upload one or more supported files: `.pdf`, `.md`, `.doc`, or `.docx`
3. Click **Build Knowledge Base**
4. Ask questions in the chat

---

## Supported File Types

- `.pdf` files are parsed with `pdfplumber`
- `.md` files are read as text
- `.docx` files are parsed with `python-docx`
- `.doc` files are supported on Windows through Microsoft Word automation

Note: legacy `.doc` files require Microsoft Word to be installed on the same Windows machine. If Word is not available, convert the file to `.docx`.

---

## Project Structure

```text
mini-rag/
|-- app.py
|-- rag_pipeline.py
|-- requirements.txt
|-- README.md
|-- faiss_index.bin
`-- chunks.pkl
```

---

## How It Works

### 1. Document Processing

- The app accepts PDF, Markdown, DOC, and DOCX files
- Text is extracted based on file type before indexing

### 2. Chunking

- Extracted text is split into 400-character chunks
- Chunks overlap by 80 characters to preserve context

### 3. Embedding

- Each chunk is embedded using `sentence-transformers/all-MiniLM-L6-v2`
- Embeddings are generated locally

### 4. Vector Indexing

- All embeddings are stored in a FAISS `IndexFlatL2` index
- The index is saved to disk for reuse across sessions

### 5. Retrieval

- The user query is embedded with the same model
- FAISS returns the top 4 most relevant chunks

### 6. Grounded Answer Generation

- Retrieved chunks are inserted into a strict prompt
- The app sends that prompt to OpenRouter using `openrouter/free`
- The model is instructed to answer only from the uploaded documents

### 7. Transparency

- Every answer is shown with the retrieved chunks used to generate it
- Each chunk includes source file name, chunk id, and rank

---

## Deployment Note

If you deploy this app outside Windows, `.doc` support may not work because it depends on Microsoft Word automation. `.pdf`, `.md`, and `.docx` support remain portable.

---
## Possible Enhancements

- Add hybrid search (BM25 + semantic retrieval)
- Add reranking for retrieved chunks
- Add evaluation questions and scoring
- Add conversation memory
- Add local LLM support

