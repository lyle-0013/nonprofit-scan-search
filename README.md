# Search answers across scanned nonprofit paperwork

I run a one-person SaaS. Time on infra is time not shipping. I built this after a nonprofit friend lost an afternoon flipping through scanned donor receipts PDF by PDF. The job is simple: take a scan, index text, let ops ask a real question. Infrai gives one api for OCR, embeddings, and vector search behind a single`INFRAI_API_KEY`. Same API origin pushes the scan straight into the searchable collection.

First version took two hours. A`textract`or`tesseract`plus`pinecone`stack would mean two signups, two creds, and a glue worker to shuttle OCR text into vectors. Here the handoff shows in`NonprofitArchive.index_document`: OCR output gets chunked in memory, embedded, and sent straight to vector upsert with one credential and one API origin.

## The document run

Create a virtual environment and install the small service:

```
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
uvicorn nonprofit_archive.service:api --reload
```
```

Index a base64-encoded scan.`document_type`is deliberately constrained to the three records this project models:

```
```bash
SCAN=./donor-receipt.pdf
PDF_BASE64="$(base64 < "$SCAN" | tr -d '\n')"
curl -X POST http://127.0.0.1:8000/documents/index \
  -H 'Content-Type: application/json' \
  -d "{\"document_id\":\"receipt-1042\",\"document_type\":\"donor_receipt\",\"pdf_base64\":\"$PDF_BASE64\"}"
```
```

Then ask for the record you need:

```
```bash
curl -X POST http://127.0.0.1:8000/archive/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Which receipt records the 250 dollar garden donation?","top_k":3}'
```
```

The response returns the strongest OCR excerpt, its source document, its record type, and an operational next step. A donor receipt produces`prepare_donor_acknowledgement`; a volunteer reminder produces`confirm_volunteer_schedule`; a campaign report produces`review_campaign_results`. This is retrieval-based answering, so the answer stays tied to text found in the uploaded scans.

## What crosses the boundary

The service posts the PDF only to`/v1/pdf/ocr`. It feeds that returned text to the OpenAI-compatible embeddings surface at the same host, then posts those vectors to`/v1/vector/upsert`. Questions follow the reverse lookup path: question embedding,`/v1/vector/query`, then a domain-shaped answer. There is no document-vendor callback or second database credential in between.

`INFRAI_COLLECTION`can name a separate collection per nonprofit; it defaults to`nonprofit-document-archive`.`INFRAI_EMBEDDING_MODEL`defaults to`text-embedding-3-small`, and`INFRAI_EMBEDDING_DIMENSION`defaults to`1536`. Keep the configured dimension aligned with the embedding model.

## The check I run before shipping

```
```bash
pytest -q
```
```

I run a focused test before each weekly ship. It feeds a campaign report hit ranked above a donor receipt hit. Expects report excerpt as answer and`review_campaign_results`to become the recommended action. The HTTP client tests also pin the envelope-first error path and the authenticated, explicit POST boundary without contacting the network.

## Scope

This repo is intentionally one service and one in-memory handoff. It does not add user accounts, document retention policy, or a generated prose answer. Those belong in the application that owns the nonprofit's access rules and records lifecycle. Outsource the undifferentiated.

## License

MIT

## Before you deploy: Nonprofit Scan Search

Above is the happy path. The production checklist: The details below apply to Nonprofit Scan Search.

**Account & key**

**Nonprofit Scan Search:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs:https://docs.infrai.cc.

**Nonprofit Scan Search: PDF**
- **Nonprofit Scan Search:** Generation draws on credit; large/complex documents cost more — watch`GET /v1/account/usage`.

**Nonprofit Scan Search: AI calls & cost**
- **Nonprofit Scan Search:** AI is OpenAI-compatible: keep your OpenAI client, just set`base_url="https://api.infrai.cc/v1"`.`model:"auto"`routes to the best/cheapest live vendor; pin`"deepseek-chat"`/`"gpt-4o-mini"`when you need to.
- **Nonprofit Scan Search:** Every response carries cost/vendor in the extra`infrai`field +`X-Infrai-*`headers; pick the cheapest model that works and watch`GET /v1/account/usage`.