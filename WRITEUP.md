# PlacidWay Website Knowledge Chatbot: Write-up

**Live demo:** https://137-184-131-54.sslip.io
**Repository:** https://github.com/saimqureshi656/placidway-bot
**Author:** Muhammad Saim Qureshi

## How it was built

A Python/FastAPI retrieval-augmented chatbot grounded only in the seven PlacidWay pages provided. The pages are scraped once (respecting robots.txt, a named User-Agent and one request per second), cleaned of site navigation and other clinics' listings, split into sections, and indexed. Every answer is checked in code against that content before it is shown.

## Stack

- **Backend:** Python, FastAPI, SQLite (logs, leads, unanswered questions, answer cache)
- **Ingestion:** httpx + BeautifulSoup, per-page-type extractors, structured `prices.json`
- **Retrieval:** BM25 + FAISS (BAAI/bge-small-en-v1.5), fused with Reciprocal Rank Fusion, reranked with MiniLM cross-encoder
- **LLMs:** Cerebras `gpt-oss-120b` (answers), `qwen-3.8-27b` (routing and query rewriting), Groq as fallback
- **Frontend:** single-page chat UI with source chips, lead form and feedback
- **Hosting:** DigitalOcean droplet, systemd, Caddy (HTTPS)

## How it works

1. The question is classified (price, info, comparison, booking, medical, out of scope) and rewritten into a standalone English search query, so follow-ups and Spanish or Arabic questions work.
2. Hybrid search finds the most relevant passages and price records. Weak matches below a score threshold are dropped.
3. The model drafts an answer only from those passages, citing them.
4. A verifier checks the draft; failures are retried once, then replaced with an honest fallback.
5. The reply is shown in the user's language with links to the source pages.

## How it avoids inventing answers

- Every price in an answer must exist in the retrieved content **and belong to the item it is attached to** (e.g. the appendix package is mentioned but has no price, so the bot says it is not listed).
- Prices keep their qualifier ("starting from", "approximately") in English, Spanish and Arabic.
- Comparisons only include sides that appear in the content; a missing side is named as not listed.
- Recovery time, success rates and survival figures are never inferred from program length or reviews.
- Clinical claims are attributed to the clinic's page; medical-advice questions get no diagnosis and a referral to a doctor.
- Wrong prices stated by the user ("I heard it costs $50") are corrected, never confirmed.
- When the answer is not in the content, the bot says so and links the free quote form.

**Results:** all 8 required test questions pass, plus 44/44 cases in the internal eval set, with a typical response time of about 2 seconds.

## Known limitations

- The comparison page only shows its first "Load More" batch of clinics, so comparisons are limited to that batch.
- No page states a recovery time; the bot reports it as not listed.
- The video page contains titles only, no transcripts.
- Comparison-page prices are center estimates, not ITC quotes.
- The knowledge base is small (seven pages), and the price list contains one row with a blank procedure name, which is excluded from answers.
- When something is not listed, the bot sometimes adds related facts that are only loosely relevant.

## Future work

- Load all comparison-page clinics and store each with its city.
- Separate program length from recovery information in the index.
- Add video transcripts, or exclude that page until they exist.
- Filter "related facts" by relevance to the question.
- Refresh the index automatically when a page's content changes.
- Run the eval set automatically on every change so a prompt edit cannot break a required answer.