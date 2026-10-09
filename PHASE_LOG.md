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
