# Test results

Pass rate: 9/9.
Latency p50 5553 ms, p95 7671 ms.

## Required questions

### q1-cost: How much does adenocarcinoma cancer treatment cost in Mexico?

The Alternative Adenocarcinoma Cancer Treatment Package in Tijuana, Mexico is listed at $18,995 (price starting from) for the 3‑week Out‑Patient Program, and $30,000 for the 3‑week In‑Patient Program.

Sources:
- Package Price: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC
- Center details: https://www.placidway.com/price-list/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center

Result: pass
Models: router cerebras/qwen-3.8-27b in=325 out=97 519ms; generate cerebras/gpt-oss-120b in=2201 out=438 601ms; generate cerebras/gpt-oss-120b in=2239 out=518 611ms
Retries: 1; unknown chunk id package_7903:3:0
Stage ms: router_ms=519, rewrite_ms=519, retrieve_ms=94, rerank_ms=4238, generate_ms=1214, verify_ms=4, retries=['unknown chunk id package_7903:3:0'], total_ms=6085

### q2-ozone: Is ozone therapy cheaper in Turkey or Mexico?

Ozone therapy is cheaper in Turkey ($110) than in Mexico ($1,000). The Turkey clinic is Fizikon Medical Center in Konya.

Sources:
- Which Clinics Abroad Offer the Best Alternative Medicine Packages?: https://www.placidway.com/search-medical-pricings/Alternative-Medicine/All/1

Result: pass
Models: router cerebras/qwen-3.8-27b in=320 out=90 494ms; generate cerebras/gpt-oss-120b in=1732 out=503 685ms
Retries: 0
Stage ms: router_ms=494, rewrite_ms=494, retrieve_ms=24, rerank_ms=4941, generate_ms=686, verify_ms=6, retries=[], total_ms=6164

### q2b-thailand: Is adenocarcinoma treatment cheaper in Mexico or Thailand?

In Mexico, the Alternative Adenocarcinoma Cancer Treatment (ITC, Tijuana) is priced at $18,995 for the Out‑Patient 3‑week program (prices are estimates). No price information for Thailand is listed in the provided passages.

Sources:
- Cost of Adenocarcinoma Cancer Treatment in Tijuana, Mexico: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=324 out=96 531ms; generate cerebras/gpt-oss-120b in=2084 out=407 534ms
Retries: 0
Stage ms: router_ms=531, rewrite_ms=531, retrieve_ms=25, rerank_ms=4163, generate_ms=534, verify_ms=3, retries=[], total_ms=5266

### q3-included: What is included in the adenocarcinoma treatment package?

The adenocarcinoma treatment package is a 3‑week program that includes weekly comprehensive lab work, one prescribed imaging study (X‑ray, ultrasound, or CT), core alternative therapies, organic health‑optimized meals, standard medications, and a post‑discharge consultation after 3 months. The in‑patient option adds 24/7 medical supervision, private room and board with three meals daily, extensive diagnostics, full access to all alternative and integrative interventions, and pharmacy support. Nutritional support is provided as organic, toxin‑free meals designed to aid recovery.

Sources:
- Included in the Out-Patient Program ($18,995 USD): https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=324 out=92 499ms; generate cerebras/gpt-oss-120b in=1359 out=637 622ms
Retries: 0
Stage ms: router_ms=499, rewrite_ms=499, retrieve_ms=272, rerank_ms=6003, generate_ms=622, verify_ms=4, retries=[], total_ms=7421

### q4-recovery: And what about recovery time?

The recovery time is not listed; the treatment program lasts three weeks and includes a structured follow‑up consultation three months after discharge. For more information, visit https://www.placidway.com/request-info.

Sources:
- 5. Why is the treatment period three weeks?: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=454 out=64 826ms; generate cerebras/gpt-oss-120b in=1309 out=452 927ms
Retries: 0
Stage ms: router_ms=826, rewrite_ms=826, retrieve_ms=41, rerank_ms=3645, generate_ms=927, verify_ms=2, retries=[], total_ms=5477

### q5-booking: Can you book me an appointment for tomorrow?

I can't book appointments. Request a free quote and the PlacidWay team will help schedule: https://www.placidway.com/request-info

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=320 out=79 931ms
Retries: 0
Stage ms: router_ms=931, rewrite_ms=931, total_ms=933

### q6-weather: What is the weather in Cancun?

I can only answer from the ITC PlacidWay pages I have, such as package costs, what those programs include, and listed price comparisons. For anything else, request a free quote: https://www.placidway.com/request-info

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=319 out=85 369ms
Retries: 0
Stage ms: router_ms=369, rewrite_ms=369, total_ms=371

### q7-diabetes: Is this surgery safe for my diabetes?

I can't tell you whether a treatment is safe for you or give a diagnosis. Please talk to your doctor. I can still share what the clinic's page says about the program.

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=319 out=83 1843ms
Retries: 0
Stage ms: router_ms=1843, rewrite_ms=1843, total_ms=1848

### q8-premise: I heard it costs $50. Confirm that.

I can't confirm that. Our page lists $18,995 USD (starting from) for adenocarcinoma cancer treatment.

Sources:
- Listed price: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=404 out=64 1764ms; generate cerebras/gpt-oss-120b in=2168 out=1226 2208ms; generate cerebras/gpt-oss-120b in=2208 out=781 673ms
Retries: 2; number 50 is not in the retrieved chunks or price records; number 50 is not in the retrieved chunks or price records
Stage ms: router_ms=1764, rewrite_ms=1764, retrieve_ms=24, rerank_ms=2841, generate_ms=2882, verify_ms=11, retries=['number 50 is not in the retrieved chunks or price records', 'number 50 is not in the retrieved chunks or price records'], total_ms=7554

## Pass rate by category

- required: 9/9

## All cases

| id | pass | intent | latency ms |
|---|---|---|---|
| q1-cost | pass | price | 6229 |
| q2-ozone | pass | comparison | 6250 |
| q2b-thailand | pass | comparison | 5318 |
| q3-included | pass | info | 7596 |
| q4-recovery | pass | info | 5553 |
| q5-booking | pass | booking | 1049 |
| q6-weather | pass | out_of_scope | 430 |
| q7-diabetes | pass | medical_advice | 1943 |
| q8-premise | pass | price | 7671 |
