# Phase log

## Phase 3: retrieval

Files changed: `ingest/build_index.py`, `app/retrieve.py`, `tests/test_retrieve.py`, `requirements.txt`, rebuilt `data/index/v20261009171334`.

Decisions:
- Embeddings are `BAAI/bge-small-en-v1.5` (fastembed). Passages have no prefix. Queries use `Represent this sentence for searching relevant passages: `.
- fastembed 0.9.0 does not ship `intfloat/multilingual-e5-small`, so the earlier MiniLM index was replaced.
- Reranker is `BAAI/bge-reranker-base`. Logits are passed through a sigmoid before ranking.
- Treatment and country terms in the query add a fixed boost before the top-20 rerank pool. `testimonial` and `video_list` chunks stay in the index and are multiplied by 0.25 after the sigmoid.
- `.env` still names `intfloat/multilingual-e5-small`. The index build uses the BGE model in code so the file with secrets is not edited.

Tests: `pytest tests/test_retrieve.py` — 6 passed.

Gate:
- Adenocarcinoma, adrenal, and anal cost queries rank that package first.
- "ozone therapy Turkey" top hit is the comparison clinic table (Fizikon / Turkey), score 0.7641.
- Lowest best scores: weather in Cancun 0.0001, dental implants Mexico 0.0007.

Top 3 (sigmoid rerank score):

1. adenocarcinoma cost — 0.9921 package_7903 cost; 0.9862 exclusions; 0.9592 optional procedures
2. in-patient program includes — 0.9993 package_7901 included in-patient; 0.9992 package_7902; 0.9991 package_7903
3. ozone therapy Turkey — 0.7641 comparison clinic table; 0.0775 video titles (flagged); 0.0238 comparison procedure table
4. recovery time — 0.0088 profile treatment approach; 0.0060 7903 three-week FAQ; 0.0029 7903 recovery CTA
5. How much does adenocarcinoma cancer treatment cost in Mexico? — 0.9977 7903 cost; 0.9953 optional; 0.9894 exclusions
6. What is included in the adenocarcinoma treatment package? — 0.9907 7903 out-patient included; 0.9902 in-patient included; 0.9531 key takeaways
7. weather in Cancun — 0.0001 international patient services; 0.0001 getting to Tijuana; 0.0000 3-week itinerary
8. dental implants Mexico — 0.0007 video titles; 0.0003 anal package intro; 0.0003 adrenal package intro

Open questions:
- Raw "recovery time" scores about 0.009, far below on-topic prices. Phase 8 may need the rewrite step, or a threshold under that score, so the 3-week FAQ is still retrieved.

## Phase 4: LLM client, router, templates, rewrite

Files changed: `app/config.py`, `app/llm.py`, `app/router.py`, `app/templates.py`, `app/rewrite.py`, `tests/test_router.py`.

Decisions:
- Groq is called with `GROQ_MODEL` from `.env`, temperature 0, 10 second timeout, one retry, then Cerebras if that key and model are set.
- Router rules cover greeting, booking, medical advice, weather/dental, lead, comparison, and price. Unmatched text goes to the LLM JSON classifier, then `info` if that call fails.
- Money mentions such as `$50` are stored on the route as `user_numbers` for the premise check.

Tests: `pytest tests/test_router.py` — 5 passed (booking, weather, diabetes, $50 premise, ozone comparison).

Open questions:
- Cerebras is wired but `.env` has no Cerebras model, so fallback will not run until those values are set.

## Phase 5: generation, verifier, premise check

Files changed: `app/normalize.py`, `app/verify.py`, `app/generate.py`, `tests/test_normalize.py`, `tests/test_verify.py`, `tests/test_extract.py`, `tests/fixtures/boilerplate.html`.

Decisions:
- `18.995` and `18,995` are thousands-separators and become 18995. `30k` becomes 30000. Arabic-Indic and Persian digits are folded before parsing.
- Every number in a grounded answer must occur in a cited chunk or a used price record. A URL must be on the seven-page allowlist or be the quote form. A clinic phrase ending in Clinic/Center/Hospital must match a known clinic name.
- The quote form URL is allowed in addition to the seven pages, because the prescribed fallback includes it.
- If the user states a price that matches none of the topic's answerable records, the answer has to start with "I can't confirm that."
- Generation retries once with the verifier or premise failure text, then returns the fallback.

Tests: `pytest tests/test_normalize.py tests/test_verify.py tests/test_extract.py` — 10 passed.

Open questions:
- Small structural numbers such as "3 weeks" fail the verifier if that digit is not also in the cited chunk.

## Phase 6: FastAPI and SQLite

Files changed: `app/main.py`, `app/db.py`, `app/security.py`, `app/retrieve.py`, `requirements.txt`.

Decisions:
- Chat validates a 1000-character message, rate-limits at 20 requests per minute per IP, and writes a log row without API keys.
- Price lookup requires a treatment term when the question names one. Matching only on "Mexico" was attaching dozens of unrelated price records and the model then set grounded=false.
- `/health` reports the current index pointer. Admin routes require `X-Admin-Token`.

Tests and gate: server started. `/health` returned status ok, index `v20261009171334`, 131 chunks. `/api/chat` for the adenocarcinoma cost question returned a grounded answer with the 7903 source and verifier status `pass`.

Open questions:
- The first chat request spends most of its time loading the embedding and reranker models.

## Phase 7: chat UI

Files changed: `web/index.html`.

Decisions:
- One HTML file, no build step. The page posts the last 6 turns to `/api/chat`, renders source chips that open the URL and show the snippet, and shows the disclaimer and lead form when the API asks for them.
- Example chips cover cost, package contents, the ozone comparison, and a Spanish price question.

Check: `GET /` returned 200 and the HTML includes the header "PlacidWay Assistant", the subtitle "Answers from PlacidWay pages only", the chat endpoint, disclaimer handling, and source chips. No in-app browser tool was available, so the buttons were not clicked in a real browser. The page is served by the same FastAPI app that already returned sources for the cost question.

Open questions: none for this phase.
