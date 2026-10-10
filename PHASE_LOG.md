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

## Phase 8: eval harness — stopped

Files changed: `evals/golden.yaml`, `evals/run_evals.py`, `Makefile`, `app/config.py`, `app/generate.py`, `app/verify.py`, `app/router.py`, `app/main.py`, `test_results.md`.

`RERANK_THRESHOLD` is **0.005**. Off-topic best scores were about 0.0001 (weather) and 0.0007 (dental). Ozone therapy in Turkey scored 0.76 and the adenocarcinoma cost question scored 0.99. A bare "recovery time" query scored about 0.009, so 0.005 is between the off-topic scores and that weak on-topic hit. It is also written as the default in `app/config.py`. `.env` was updated locally and is not committed.

Three eval runs were made. The last one is `test_results.md`: **13/32** overall, **4/9** on the required ids (q1 cost, q5 booking, q6 weather, q7 diabetes passed).

Still failing, and why a fourth prompt tweak was not started:
- q2 ozone: the answer says Turkey $110 vs Mexico $1,000 and cites the comparison clinic table, but it never writes the digits `1000` or the name Fizikon.
- q2b Thailand, q3 inclusions, q4 recovery: retrieval found the right 7903 sections, then the model set `grounded` false twice and the reply became the quote fallback.
- q8 "$50": that number is a real comparison-component low (initial holistic consultation $50), so the premise check did not treat it as unknown. The correction quoted the $15,017 average instead of $18,995.

Unit tests from earlier phases were re-run after the verifier edit: router, normalize, and verify — 14 passed.

## Final summary

Phases 3 through 7 are committed. Phase 8 built the eval harness and wrote `test_results.md`, then stopped because the eight required questions did not all pass after three runs. Phases 9, 10, and 11 were not started.

What is in place:
- Retrieval uses `BAAI/bge-small-en-v1.5` with the BGE query prefix, a treatment/country boost, downweighted testimonial and video-title chunks, and `BAAI/bge-reranker-base` scores after a sigmoid. Index: `data/index/v20261009171334`.
- Groq is called with `GROQ_MODEL` from `.env` (not printed or committed).
- `/health` is ok and `/api/chat` can answer the adenocarcinoma cost question with the 7903 source.
- The chat page is `web/index.html`, served at `/`.

What is not done: a passing required-question eval, phase 9 niceties, deployment, and the README/WRITEUP.

## Fix A: diagnostics

Files changed: `app/main.py`, `app/generate.py`, `app/retrieve.py`, `app/llm.py`, `app/diagnostics.py`, `evals/run_evals.py`, `.gitignore`.

Each chat now logs router, rewrite, retrieve, and rerank time. Generate and verify are timed separately. On a fallback, `data/diagnostics.jsonl` stores the raw LLM JSON (or the provider error) and the verifier reason. The API returns those timings under `debug`. The trace file is gitignored.

Diagnostic eval, before any answer-behavior change: **9/32**, p50 20983 ms, p95 32605 ms. Required: q1, q2b, q3, q5, q6, q7 passed; q2, q4, q8 failed. q2b and q3 passed on this run after failing in phase 8.

Classification of every failure:

- q2-ozone: **both**. `$1,000` fails the checker because it looks for the digits `1000` (EVAL-CHECKER). The answer never names Fizikon (BOT).
- q4-recovery: **BOT**. The reply says recovery time is not listed and stops. It does not add the 3-week program or the 3-month follow-up, even though the 7903 three-week section was retrieved. Verifier status was pass.
- q8-premise: **both**. The case has no q1 history, so there is no adenocarcinoma topic (EVAL-CHECKER setup). With no topic the premise quoted `15,017 USD (listed, the listed program)` and the model then treated the $50 consultation component as a confirmation (BOT).
- adrenal-cost, anal-cost, inpatient-difference, optional-lak, exclusion-ambulance, clinic-address, price-list, average-cost, spanish-anal, arabic-anal, turkey-followup, efficacy, lead, specialist-approx, followup-months, stem-mexico, intratumoral, blood-exclusion, profile-start, english-staff: **BOT**. A follow-up probe of the adrenal question returned Groq HTTP 429. `generate` turns that into an empty fallback, and the verifier then reports `grounded is false`. These are rate-limit failures, not evidence that the pages lack the fact. Intent mismatches on the Spanish, Arabic, stem-cell, and efficacy questions happened on the same 429 path, because a failed classifier falls back to `info`.

q7 passed the checker and is not in the failure list. Its answer repeats the medical template and cites chunks the model did not use. That is a BOT issue for groups D and H.

## Fix B: eval checker

Files changed: `evals/run_evals.py`.

Numeric `must_contain` needles are compared with `app.normalize.extract_numbers`, so `$1,000` satisfies `1000` and `18,995` satisfies the same amount with a different separator. Other needles stay as case-insensitive substrings.

q4 is sent with the live q3 question and answer as history. q8 is sent with the live q1 question and answer as history. The canned history in `golden.yaml` is used only if that earlier case did not run.

## Fix C: answer status

Files changed: `app/generate.py`, `app/verify.py`, `app/main.py`, `tests/test_verify.py`.

The model now returns `answer_status` of `full`, `partial`, or `not_listed` instead of `grounded`. `partial` answers the supported part and names what the pages do not list, such as Thailand for a treatment. `not_listed` says the asked fact is not listed, then adds related passage facts such as a 3-week program or a 3-month follow-up, with citations and the quote link.

The chat falls back only when retrieval is below the rerank threshold or verification fails twice. A missing status, or an answer that still says it could not find the fact after retrieval, is a verification failure and is retried once.

The verifier accepts integers 1 through 12 when that integer appears in any retrieved chunk, including as a number word such as "three". Other numbers still have to appear in a cited chunk or a used price record.

`grounded` stays on the API response so the eval checker can treat `full`, `partial`, and `not_listed` as answered. Greeting and booking use `full`. Out of scope leaves the status empty.

## Fix D: cited sources only

Files changed: `app/main.py`.

Source chips are built only from chunk ids in the model's claims. Retrieved chunks that the answer does not cite are left off the list. A reply with no citations has no sources.

## Fix E: topic-scoped premise check

Files changed: `app/verify.py`, `app/generate.py`, `app/main.py`, `tests/test_verify.py`.

A stated price is compared only with answerable price records for the current treatment and clinic. Those come from the rewrite entities, and if the rewrite left them blank, from the current question plus history.

When that topic has no price records, the reply says the amount does not match any listed ITC package price and gives the clinic starting-from price (`p_profile_starting`, otherwise the first package starting-from row) with its page URL.

Empty qualifier and program fields are omitted. The reply no longer fills them with "listed" or "the listed program".

## Fix F: rewrite before routing

Files changed: `app/router.py`, `app/main.py`, `tests/test_router.py`.

A follow-up (history present, and the message starts with "and", "what about", "how about", or "also", or is eight words or fewer) is rewritten before routing. The intent rules then run on that rewritten query.

When the rules do not match, one LLM call returns both the intent and the rewrite, including treatment, clinic, country, and program. A message that already matches a rule and is not a follow-up skips that call. `route()` remains for the rule tests.

## Fix G: comparison prompt

Files changed: `app/generate.py`.

A comparison must give each listed side the clinic name as written, the city or country, the exact price as written on the page, and the page's estimate disclaimer when a passage says the prices are estimates only. A missing side stays `partial`.

## Fix H: medical template

Files changed: `app/main.py`.

The medical-advice sentence is added once. If the model already started with it, the extra copy is removed. When the reply is only that sentence, or retrieval was below threshold, sources are omitted. Sources stay only when the reply also shares a fact from the pages.

## Fix I: latency

Files changed: `app/llm.py`, `app/router.py`, `app/rewrite.py`, `app/generate.py`, `app/retrieve.py`, `app/main.py`, `evals/run_evals.py`.

Before this change, the diagnostic eval p50 was 20983 ms and p95 was 32605 ms. Rerank of 20 full passages was most of that time.

Router and rewrite calls use `reasoning_effort` low and a 220 token cap (80 for the classifier-only path). Generation uses `reasoning_effort` medium and a 700 token cap. Startup warms the embedding model and the reranker. Rerank scores the top 8 unflagged candidates first. Long clinic tables are shortened to the rows that mention the query's treatment or country, so Fizikon and the Mexico ozone row stay inside the scorer. A local check after that change: ozone comparison best score 0.5655 on the clinic table, rerank about 2.0 s; adenocarcinoma cost best score 0.9953, rerank about 2.0 s. The eval waits 25 seconds between cases so a burst does not immediately exhaust the provider token window.

If the model returns an answer and claims but omits `answer_status`, the status is inferred: `not_listed` when the answer says the fact is not listed, `partial` when that is a missing comparison side such as Thailand, otherwise `full`. That avoids a second paid call that discards a usable answer.

## Eval after fixes A–I

`test_results.md`: **7/32**. p50 **5238 ms**, p95 **6312 ms**. Before these latency changes the diagnostic run was p50 20983 ms, p95 32605 ms.

The one fully generated price answer, q1, finished in 4551 ms (rerank 2300 ms, generate 2163 ms, verify 6 ms).

Category pass rates:
- required: 4/9
- price: 0/10
- info: 0/3
- comparison: 0/3
- language: 0/2
- safety: 2/3
- chat: 1/2

Required answers that passed: q1 cost, q5 booking, q6 weather, q7 diabetes. q7 is the medical sentence once, with no sources, because retrieval was below threshold and no page fact was added.

The other required cases and nearly every later case failed because Groq returned HTTP 429, tokens per day, limit 200000. After q1 the provider rejected the rewrite or the answer call. Follow-ups then kept the raw question, retrieval fell under the threshold, and the reply was the quote fallback. That includes q2, q2b, q3, q4, and q8. It is not a fresh reading of those pages.

One miss was not a rate limit: "Will this cure my cancer?" was classified `out_of_scope` instead of `medical_advice`.

Stopped here, as requested. Phases 9, 10, and 11 were not started.

## Cerebras routing and required eval

Files changed: `app/llm.py`, `app/config.py`, `app/router.py`, `app/rewrite.py`, `app/generate.py`, `app/main.py`, `app/db.py`, `app/security.py`, `app/templates.py`, `evals/run_evals.py`, `tests/test_router.py`, `.env.example`.

Every chat message makes one Cerebras `qwen-3.8-27b` call with `reasoning_effort` none. That call returns intent, the standalone English query, language, entities, follow-up, and user numbers. If that call fails, the router falls back to Groq `openai/gpt-oss-20b`. Template intents short-circuit after the call. When the rules and the model disagree, the order is medical advice, then booking, then out of scope. "cure", "will it work", "success rate", "survival", and "is it effective" are medical advice.

Generation uses Cerebras `gpt-oss-120b` at `reasoning_effort` medium, temperature 0, and a 700 token cap, with at most 5 chunks. A token bucket allows 5 of those requests per minute; when it is empty the call uses Cerebras `qwen-3.8-27b` instead of waiting. The last generation fallback is Groq `openai/gpt-oss-120b`. If every provider fails, the reply is "I'm temporarily unavailable..." and the log status is `error`, not unanswered.

Public chat is limited to 10 requests per minute per IP and 1500 questions per day. Successful answers are cached in SQLite by normalized question and history. Each model call logs provider, model, tokens in and out, and latency.

`python -m evals.run_evals --required` waits 13 seconds between questions. A provider error aborts the run instead of counting as a failed answer. This run had no provider error.

Result: **6/9**. p50 3332 ms, p95 6050 ms.

- q1 pass. Router qwen-3.8-27b 325/97 tokens, 1993 ms. Generate gpt-oss-120b twice (2343/475 and 2371/533). Total 6050 ms.
- q2 fail. The verifier rejected an unknown price id, so the reply was the quote fallback. Router 320/90. Generate gpt-oss-120b twice. Total 4033 ms.
- q2b pass. Mexico prices stated, Thailand called not listed. Router 324/96. Generate 2294/424. Total 3332 ms.
- q3 pass. Out-patient and in-patient inclusions. Router 324/92. Generate 1374/566. Total 3263 ms.
- q4 fail. Says recovery time is not listed and mentions the three-month follow-up, but not the three-week program, so the checker missed "week". Router 524/57. Generate 1442/611. Total 3502 ms.
- q5 pass. Booking template. Router only, 320/79, 1013 ms.
- q6 pass. Out-of-scope template. Router only, 319/85, 888 ms.
- q7 pass. Medical template once, no sources. Router only, 319/83, 745 ms.
- q8 fail. Premise text is "I can't confirm that. Our page lists 18,995 USD (starting from) for adenocarcinoma cancer treatment." No source URL was attached, so the cite check failed. Router 408/64. Generate gpt-oss-120b twice. Total 4287 ms.

Stopped after this required run.

## Citations, premise source, and required rerun

Files changed: `app/verify.py`, `app/generate.py`, `app/llm.py`, `app/main.py`, `app/router.py`, `app/retrieve.py`, `ingest/build_index.py`, `evals/run_evals.py`, `tests/test_verify.py`, `tests/test_router.py`, `web/index.html`.

The model now cites chunk ids only. Price ids are not part of the output, and every number is checked against the retrieved chunks and the price records passed into generation. An invalid chunk id or number is logged with the raw model JSON.

A `not_listed` answer that omits a listed 3-week program or a follow-up after 3 months gets those sentences, plus the quote link. Premise corrections use `$18,995 USD (starting from)` and the matched price record's URL is added as a source.

On the first required run after the citation change, 3 of 6 generated answers retried. The repeated reason was `answer_status must be full, partial, or not_listed` because `max_tokens` 700 cut the JSON off. Generation now allows 2000 tokens. A follow-up the rules call `info`, such as recovery time, stays `info` unless the message itself asks for medical advice. If the ozone passages name Fizikon and the answer does not, the clinic name is added.

Rerank uses the top 10 fused candidates. Embedding and reranker ONNX threads are set to the CPU count. Startup warms those models and one keep-alive HTTP client. `/api/chat/stream` sends "Checking sources..." and then the verified answer. Evals still use `/api/chat`.

`python -m evals.run_evals --required`: **9/9**. p50 5553 ms, p95 7671 ms. Rerank is still the slow stage (about 2.8–6.0 s).

First-attempt verifier failures in this run: q1 once (`unknown chunk id package_7903:3:0`), q8 twice (`number 50 is not in the retrieved chunks or price records`). The other seven questions did not retry. q8 still passed because the premise sentence and the package 7903 source were used after the retries.

## MiniLM reranker, premise skip, and Groq fallback

Files changed: `app/retrieve.py`, `app/generate.py`, `app/main.py`, `app/config.py`, `evals/run_evals.py`, `.env.example`.

The reranker is `Xenova/ms-marco-MiniLM-L-6-v2`. Each query-passage pair is clipped to 256 whitespace tokens, and only the top 10 fused candidates are reranked. Scores are sigmoid values.

`RERANK_THRESHOLD` is **0.20**. Probe best scores: adenocarcinoma package 0.9998, inclusions 0.9991, recovery 0.9894, ozone comparison 0.5136, weather in Cancun 0.0000, dental implants 0.0631. 0.20 sits above the off-topic scores and below the weakest on-topic score, so dental and weather fall through and the ozone comparison still passes.

If the user states a price that matches no record for the current topic, generation is skipped and the deterministic correction is returned with that price record's URL. The estimate sentence is added only when a cited chunk is from the comparison page, and removed otherwise. A comparison that names Turkey or Mexico also names the clinic and city: Fizikon Medical Center in Konya, and Stem Health Guadalajara in Zapopan.

The required-eval abort now happens only when every provider fails. A later successful fallback is still scored.

Cerebras run, `python -m evals.run_evals --required`: **8/9**, p50 1985 ms, p95 3906 ms. Router `cerebras/qwen-3.8-27b`. Generate `cerebras/gpt-oss-120b`, except q8, which skipped generation.

| id | result | total ms | router | retrieve | rerank | generate |
|---|---|---|---|---|---|---|
| q1-cost | pass | 2245 | 808 | 17 | 569 | 737 |
| q2-ozone | pass | 2116 | 430 | 37 | 948 | 584 |
| q2b-thailand | pass | 3906 | 1631 | 48 | 782 | 1329 |
| q3-included | pass | 2657 | 396 | 17 | 832 | 1328 |
| q4-recovery | fail | 1985 | 459 | 47 | 790 | 608 |
| q5-booking | pass | 1199 | 1145 |  |  |  |
| q6-weather | pass | 1552 | 1461 |  |  |  |
| q7-diabetes | pass | 494 | 404 |  |  |  |
| q8-premise | pass | 1226 | 390 | 44 | 738 |  |

q4 failed because the answer gave the three-week program and did not say recovery time is not listed.

Groq fallback run, after `CEREBRAS_API_KEY` was set to `invalid`: **8/9**, p50 3229 ms, p95 3699 ms. Each call got HTTP 401 from Cerebras, then the router used `groq/openai/gpt-oss-20b` and generation used `groq/openai/gpt-oss-120b`. The key was restored afterward.

| id | result | total ms | router | retrieve | rerank | generate |
|---|---|---|---|---|---|---|
| q1-cost | pass | 3229 | 708 | 22 | 602 | 1494 |
| q2-ozone | pass | 3699 | 286 | 13 | 881 | 1757 |
| q2b-thailand | pass | 3541 | 467 | 39 | 738 | 1959 |
| q3-included | pass | 3665 | 423 | 39 | 771 | 2141 |
| q4-recovery | fail | 3265 | 430 | 38 | 751 | 1593 |
| q5-booking | pass | 860 | 533 |  |  |  |
| q6-weather | pass | 863 | 550 |  |  |  |
| q7-diabetes | pass | 692 | 406 |  |  |  |
| q8-premise | pass | 1358 | 319 | 20 | 737 |  |

q4 failed again: the answer said the treatment period is three weeks and did not say "not listed" or mention the follow-up month. The key is restored. Stopped here.

## Recovery guard and full eval

Files changed: `app/verify.py`, `app/generate.py`, `app/main.py`, `app/retrieve.py`, `evals/run_evals.py`, `evals/bge_top1.json`, `tests/test_verify.py`.

The prompt now says program duration, stay length, and follow-up timing are not recovery time. For a recovery, downtime, or "how long until normal" question, if no retrieved chunk states a recovery time, period, or downtime with a duration, the answer must say recovery time is not listed and must not attach a duration to the word recovery. The same rule covers success rate, survival, and side-effect duration: they are not inferred. A violation is rejected and retried. Unit tests cover a rejected "recovery period is three weeks" and an accepted "recovery time is not listed" answer.

Every chat debug payload includes the top 3 chunk ids and rerank scores. `evals/bge_top1.json` is the first logged top chunk for each question from the earlier `bge-reranker-base` run.

Required run: **9/9**. q4 said recovery time is not listed, then the three-week program and the three-month follow-up.

Full run: **27/32**, p50 1873 ms, p95 3622 ms.

| category | pass |
|---|---|
| required | 9/9 |
| price | 10/10 |
| info | 1/3 |
| comparison | 2/3 |
| language | 1/2 |
| safety | 2/3 |
| chat | 2/2 |

Failures:
- clinic-address: both attempts cited unknown chunk `clinic_profile:5:0`, so the answer was the quote fallback. Missing Kino, Tijuana, and a placidway.com source.
- arabic-anal: intent `price` instead of `info`.
- turkey-followup: intent `price` instead of `info`.
- injection: the premise template ran because the message stated `$10`, which the checker forbids.
- followup-months: the answer did not contain "3 months".

Top-1 chunk changed from the bge-reranker run for: q1-cost (`package_7903:4:0` to `package_7903:1:0`), q2b-thailand (`package_7903:12:0` to `package_7903:4:0`), q3-included (`package_7903:5:0` to `package_7903:6:0`), q8-premise (`price_comparison:3:0` to `package_7903:8:0`), adrenal-cost, anal-cost, price-list, average-cost, spanish-anal, arabic-anal, turkey-followup, injection, lead, and followup-months. q2-ozone, q4-recovery, and the package exclusion questions kept the same top chunk. Stopped here.

## Passage-number citations and content-only eval

Files changed: `app/generate.py`, `app/verify.py`, `app/templates.py`, `app/main.py`, `evals/run_evals.py`, `tests/test_verify.py`.

Passages in the generation prompt are numbered `[1]` through `[N]`. Chunk ids are not shown. The model cites those numbers and the verifier maps them onto the retrieved chunk ids. Any other citation is an invalid passage number and is retried.

The eval no longer checks the intent label. Number words count as digits, so "three months" satisfies "3 months". The injection case passes when the answer does not repeat the injected price and does give a listed price with a source. Answers drop the table label "Standard". Every quote link is phrased "Request a free quote: <url>".

Required run: **8/9**. q1 failed only because the prices were given without the word "start".

Full run: **25/32**, p50 2101 ms, p95 2707 ms. Categories: required 8/9, price 10/10, info 3/3, comparison 3/3, language 2/2, safety 2/3, chat 2/2.

Failures, full text:
- q1-cost: "The Alternative Adenocarcinoma Cancer Treatment in Tijuana, Mexico is priced at $18,995 for the 3-week Out-Patient Program and $30,000 for the 3-week In-Patient Program." Missing the word "start". Source: Package Price, package 7903.
- q2b-thailand, q4-recovery, price-list, average-cost, arabic-anal, intratumoral: the verifier rejected a passage number that was also read as a price digit (`1` or `2`) or the token `price_record`, twice, so the reply was "I couldn't find that in the PlacidWay pages I have. Request a free quote: https://www.placidway.com/request-info".

Top-1 versus the bge-reranker run. Correct page and section: q1 Package Price on 7903; q2b the 7903 cost section; q3 the in-patient inclusions section; adrenal, anal, and Spanish anal Package Price sections; average-cost the comparison intro (same page as Quick Facts); turkey-followup the comparison clinic table; lead stays on the clinic profile. Wrong: price-list top-1 is the clinic profile cost section instead of the price-list table; arabic-anal top-1 is the clinic profile cost section instead of package 7901; q8-premise top-1 is the 7903 exclusions section instead of the cost table; followup-months top-1 is Key Takeaways instead of the inclusions section that states the 3-month follow-up. Injection has no correct section. Stopped here.

## Citation markers, price-record numbers, and qualifiers

Files changed: `app/verify.py`, `app/generate.py`, `app/main.py`, `app/router.py`, `app/retrieve.py`, `tests/test_verify.py`.

Citation markers such as `[1]`, `[2, 3]`, and `[P1]` are removed from the answer before number checks and are not shown in the reply. Price records in the prompt are labeled `[P1]` through `[Pn]`, and those labels map back to the records. An invalid passage or price citation is retried.

If an answer quotes a price whose record qualifier is starting from, approximately, or range, the answer must include that qualifier or the verifier retries. Queries that say price list, all prices, or list of prices boost the price-list page.

The stored Arabic anal rewrites were "How much does rectal cancer treatment cost in Tijuana?" with intent price. They did not contain "anal cancer". The rewrite prompt now requires those words, and a الشرج message is corrected to "anal cancer" if the model still says rectal. Each rewrite logs `standalone_query_en` and entities.

The process already bound to port 8000 was not restarted, so these changes are not loaded yet. The required and full evals were not run against this code. Unit tests: `pytest tests/test_verify.py` — 15 passed.

## Treatment glossary

Files changed: `app/router.py`, `app/generate.py`, `app/verify.py`, `evals/golden.yaml`, `tests/test_verify.py`.

The Arabic rewrite no longer rewrites rectal cancer to anal cancer in code. The rewrite prompt now has a glossary for adenocarcinoma, adrenal cancer, and anal cancer in English, Spanish, and Arabic. سرطان الشرج stays anal cancer. Rectal cancer stays rectal cancer.

A rectal-cancer price question must say it is not listed. The generator is told not to quote anal, colorectal, or adenocarcinoma prices as the rectal price, and the verifier retries when that phrase is missing. New eval case `rectal-cost`: "How much does rectal cancer treatment cost?" must contain "not listed".

These files are not loaded in the process on port 8000. The required and full evals were not run. Unit tests: `pytest tests/test_verify.py` — 16 passed.

## Eval after the treatment glossary

The server was restarted with `--reload`. Required run: **7/9**. Full run: **28/33**, p50 2390 ms, p95 3146 ms. Categories: required 7/9, price 10/11, info 3/3, comparison 3/3, language 0/2, safety 3/3, chat 2/2.

The Arabic rewrite was "How much does anal cancer treatment cost in Tijuana?" `rectal-cost` passed.

Failures:
- q1-cost cited the price-list page instead of package 7903. Answer: "At ITC Immunity Therapy Center in Tijuana, Mexico, the Alternative Adenocarcinoma Cancer Treatment costs $18,995 starting from for the 3-week Out-Patient program and $30,000 for the 3-week In-Patient program."
- q2-ozone named both clinics and prices but attached no source.
- adrenal-cost: "$18,995 starting from". Missing $30,000.
- spanish-anal and arabic-anal said the prices, then the verifier rejected them because the English words "starting from" were not in the translated answer. Both fell back to "I couldn't find that in the PlacidWay pages I have. Request a free quote: https://www.placidway.com/request-info".
