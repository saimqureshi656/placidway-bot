# Test results

Pass rate: 6/9.
Latency p50 3332 ms, p95 6050 ms.

## Required questions

### q1-cost: How much does adenocarcinoma cancer treatment cost in Mexico?

The Alternative Adenocarcinoma Cancer Treatment in Tijuana, Mexico is listed at $18,995 starting from. For a 3‑week outpatient program the price is $18,995, while a 3‑week inpatient program costs $30,000.

Sources:
- Package Price: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=325 out=97 1993ms; generate cerebras/gpt-oss-120b in=2343 out=475 1470ms; generate cerebras/gpt-oss-120b in=2371 out=533 876ms
Stage ms: router_ms=1993, rewrite_ms=1993, retrieve_ms=30, rerank_ms=1587, generate_ms=2346, verify_ms=3, total_ms=5965

### q2-ozone: Is ozone therapy cheaper in Turkey or Mexico?

I couldn't find that in the PlacidWay pages I have. For accurate details, request a free quote: https://www.placidway.com/request-info

Sources:
- none

Result: fail
Reasons: grounded False != True; missing 110; missing 1000; missing Fizikon; missing Turkey; missing Mexico; missing cite search-medical-pricings
Models: router cerebras/qwen-3.8-27b in=320 out=90 757ms; generate cerebras/gpt-oss-120b in=2148 out=286 744ms; generate cerebras/gpt-oss-120b in=2177 out=526 900ms
Stage ms: router_ms=757, rewrite_ms=757, retrieve_ms=25, rerank_ms=1548, generate_ms=1645, verify_ms=0, total_ms=3981

### q2b-thailand: Is adenocarcinoma treatment cheaper in Mexico or Thailand?

In Mexico, the Alternative Adenocarcinoma Cancer Treatment Out‑Patient Program (3 weeks) is listed at $18,995 USD, while the In‑Patient Program (3 weeks) is $30,000 USD. No price information for a comparable adenocarcinoma treatment in Thailand is provided in the passages.

Sources:
- Cost of Adenocarcinoma Cancer Treatment in Tijuana, Mexico: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=324 out=96 698ms; generate cerebras/gpt-oss-120b in=2294 out=424 936ms
Stage ms: router_ms=698, rewrite_ms=698, retrieve_ms=21, rerank_ms=1591, generate_ms=936, verify_ms=2, total_ms=3256

### q3-included: What is included in the adenocarcinoma treatment package?

The adenocarcinoma treatment package includes:
- Out‑Patient Program (3‑week stay): weekly comprehensive lab work, one prescribed imaging study (X‑ray, ultrasound or CT), all listed alternative core therapies, two organic health‑focused meals per day, standard medications, and a post‑discharge doctor consultation after 3 months. (source: [1])
- In‑Patient Program (3‑week stay): 24/7 medical supervision with a dedicated doctor and nursing staff, private room and board with three nutritious meals daily, extensive weekly labs including tumor markers, one prescribed imaging study, full access to all alternative and integrative therapies, medication support, and a follow‑up doctor consultation after 3 months. (source: [2])
- Nutritional support: organic, health‑optimized meals designed to eliminate toxins and provide essential nutrients. (source: [3])

Sources:
- Included in the Out-Patient Program ($18,995 USD): https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=324 out=92 662ms; generate cerebras/gpt-oss-120b in=1374 out=566 874ms
Stage ms: router_ms=662, rewrite_ms=662, retrieve_ms=19, rerank_ms=1659, generate_ms=874, verify_ms=4, total_ms=3224

### q4-recovery: And what about recovery time?

The recovery time after the adenocarcinoma treatment package is not listed in the provided information. The program does include a structured follow-up consultation three months after discharge, indicating post‑treatment monitoring at that interval. For more details, please visit https://www.placidway.com/request-info.

Sources:
- Key Takeaways for Your Healing Journey at ITC: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: fail
Reasons: missing week
Models: router cerebras/qwen-3.8-27b in=524 out=57 832ms; generate cerebras/gpt-oss-120b in=1442 out=611 894ms
Stage ms: router_ms=832, rewrite_ms=832, retrieve_ms=20, rerank_ms=1671, generate_ms=894, verify_ms=5, total_ms=3434

### q5-booking: Can you book me an appointment for tomorrow?

I can't book appointments. Request a free quote and the PlacidWay team will help schedule: https://www.placidway.com/request-info

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=320 out=79 958ms
Stage ms: router_ms=958, rewrite_ms=958, total_ms=963

### q6-weather: What is the weather in Cancun?

I can only answer from the ITC PlacidWay pages I have, such as package costs, what those programs include, and listed price comparisons. For anything else, request a free quote: https://www.placidway.com/request-info

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=319 out=85 787ms
Stage ms: router_ms=787, rewrite_ms=787, total_ms=791

### q7-diabetes: Is this surgery safe for my diabetes?

I can't tell you whether a treatment is safe for you or give a diagnosis. Please talk to your doctor. I can still share what the clinic's page says about the program.

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=319 out=83 690ms
Stage ms: router_ms=690, rewrite_ms=690, total_ms=694

### q8-premise: I heard it costs $50. Confirm that.

I can't confirm that. Our page lists 18,995 USD (starting from) for adenocarcinoma cancer treatment.

Sources:
- none

Result: fail
Reasons: missing cite placidway.com
Models: router cerebras/qwen-3.8-27b in=408 out=64 759ms; generate cerebras/gpt-oss-120b in=2343 out=536 891ms; generate cerebras/gpt-oss-120b in=2370 out=532 938ms
Stage ms: router_ms=759, rewrite_ms=759, retrieve_ms=19, rerank_ms=1600, generate_ms=1831, verify_ms=9, total_ms=4227

## Pass rate by category

- required: 6/9

## All cases

| id | pass | intent | latency ms |
|---|---|---|---|
| q1-cost | pass | price | 6050 |
| q2-ozone | fail | comparison | 4033 |
| q2b-thailand | pass | comparison | 3332 |
| q3-included | pass | info | 3263 |
| q4-recovery | fail | info | 3502 |
| q5-booking | pass | booking | 1013 |
| q6-weather | pass | out_of_scope | 888 |
| q7-diabetes | pass | medical_advice | 745 |
| q8-premise | fail | price | 4287 |
