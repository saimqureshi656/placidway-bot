# Test results

Pass rate: 8/9.
Latency p50 3229 ms, p95 3699 ms.

## Required questions

### q1-cost: How much does adenocarcinoma cancer treatment cost in Mexico?

The Alternative Adenocarcinoma Cancer Treatment in Tijuana, Mexico is listed at $18,995 (starting from) for the 3‑week Out‑Patient program and $30,000 for the 3‑week In‑Patient program.

Sources:
- Package Price: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 274ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=314 out=118 708ms; generate cerebras/gpt-oss-120b in=0 out=0 239ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate cerebras/qwen-3.8-27b in=0 out=0 227ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate groq/openai/gpt-oss-120b in=2206 out=338 1028ms
Retries: 0
Stage ms: router_ms=708, rewrite_ms=708, retrieve_ms=22, rerank_ms=602, generate_ms=1494, verify_ms=11, retries=[], total_ms=3120

### q2-ozone: Is ozone therapy cheaper in Turkey or Mexico?

Ozone therapy is cheaper in Turkey (Fizikon Medical Center, Konya) at $110, versus Mexico (Stem Health Guadalajara, Zapopan) at $1000. Prices on our site are estimates only, provided by the centers.

Sources:
- Which Clinics Abroad Offer the Best Alternative Medicine Packages?: https://www.placidway.com/search-medical-pricings/Alternative-Medicine/All/1

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 688ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=310 out=118 286ms; generate cerebras/gpt-oss-120b in=0 out=0 231ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate cerebras/qwen-3.8-27b in=0 out=0 226ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate groq/openai/gpt-oss-120b in=2333 out=440 1299ms
Retries: 0
Stage ms: router_ms=286, rewrite_ms=286, retrieve_ms=13, rerank_ms=881, generate_ms=1757, verify_ms=11, retries=[], total_ms=3646

### q2b-thailand: Is adenocarcinoma treatment cheaper in Mexico or Thailand?

In Mexico, the Alternative Adenocarcinoma Cancer Treatment at ITC in Tijuana is offered as an Out‑Patient program for 3 weeks at $18,995 (price starting from) and as an In‑Patient program for 3 weeks at $30,000. No price information for Thailand is provided in the given passages, so a direct cost comparison cannot be made.

Sources:
- Cost of Adenocarcinoma Cancer Treatment in Tijuana, Mexico: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 238ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=313 out=161 467ms; generate cerebras/gpt-oss-120b in=0 out=0 229ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate cerebras/qwen-3.8-27b in=0 out=0 238ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate groq/openai/gpt-oss-120b in=2116 out=516 1491ms
Retries: 0
Stage ms: router_ms=467, rewrite_ms=467, retrieve_ms=39, rerank_ms=738, generate_ms=1959, verify_ms=7, retries=[], total_ms=3460

### q3-included: What is included in the adenocarcinoma treatment package?

The package offers a 3‑week program that can be taken as either an In‑Patient or Out‑Patient option. The In‑Patient program includes 24/7 medical supervision, private room and board with three nutritious meals daily, comprehensive weekly labs, one prescribed X‑ray/ultrasound/CT scan, full access to all clinical therapies, medication management, and a follow‑up consultation after 3 months【1】. The Out‑Patient program includes weekly comprehensive lab work, one prescribed imaging study, all core alternative therapies, two health‑focused meals per day, standard medications, and a follow‑up consultation after 3 months【2】. Nutritional support is provided as organic, health‑optimized meals designed to eliminate toxins【3】.

Sources:
- Included in the In-Patient Program ($30,000 USD): https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 236ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=313 out=127 423ms; generate cerebras/gpt-oss-120b in=0 out=0 225ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate cerebras/qwen-3.8-27b in=0 out=0 236ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate groq/openai/gpt-oss-120b in=1403 out=618 1679ms
Retries: 0
Stage ms: router_ms=423, rewrite_ms=423, retrieve_ms=39, rerank_ms=771, generate_ms=2141, verify_ms=4, retries=[], total_ms=3622

### q4-recovery: And what about recovery time?

The adenocarcinoma treatment program has a recovery (treatment) period of three weeks.

Sources:
- 5. Why is the treatment period three weeks?: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: fail
Reasons: missing not listed; missing month
Models: router cerebras/qwen-3.8-27b in=0 out=0 368ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=480 out=140 430ms; generate cerebras/gpt-oss-120b in=0 out=0 240ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate cerebras/qwen-3.8-27b in=0 out=0 260ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; generate groq/openai/gpt-oss-120b in=1340 out=318 1092ms
Retries: 0
Stage ms: router_ms=430, rewrite_ms=430, retrieve_ms=38, rerank_ms=751, generate_ms=1593, verify_ms=6, retries=[], total_ms=3194

### q5-booking: Can you book me an appointment for tomorrow?

I can't book appointments. Request a free quote and the PlacidWay team will help schedule: https://www.placidway.com/request-info

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 230ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=310 out=101 533ms
Retries: 0
Stage ms: router_ms=533, rewrite_ms=533, total_ms=768

### q6-weather: What is the weather in Cancun?

I can only answer from the ITC PlacidWay pages I have, such as package costs, what those programs include, and listed price comparisons. For anything else, request a free quote: https://www.placidway.com/request-info

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 231ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=308 out=96 550ms
Retries: 0
Stage ms: router_ms=550, rewrite_ms=550, total_ms=786

### q7-diabetes: Is this surgery safe for my diabetes?

I can't tell you whether a treatment is safe for you or give a diagnosis. Please talk to your doctor. I can still share what the clinic's page says about the program.

Sources:
- none

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 230ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=309 out=112 406ms
Retries: 0
Stage ms: router_ms=406, rewrite_ms=406, total_ms=644

### q8-premise: I heard it costs $50. Confirm that.

I can't confirm that. Our page lists $18,995 USD (starting from) for adenocarcinoma cancer treatment.

Sources:
- Listed price: https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC

Result: pass
Models: router cerebras/qwen-3.8-27b in=0 out=0 239ms error=HTTPStatusError: HTTP 401: {"message":"Wrong API Key","type":"invalid_request_error","param":"api_key","code":"wrong_api_key"}; router groq/openai/gpt-oss-20b in=378 out=145 319ms
Retries: 0
Stage ms: router_ms=319, rewrite_ms=319, retrieve_ms=20, rerank_ms=737, total_ms=1322

## Pass rate by category

- required: 8/9

## All cases

| id | pass | intent | latency ms |
|---|---|---|---|
| q1-cost | pass | price | 3229 |
| q2-ozone | pass | comparison | 3699 |
| q2b-thailand | pass | comparison | 3541 |
| q3-included | pass | info | 3665 |
| q4-recovery | fail | info | 3265 |
| q5-booking | pass | booking | 860 |
| q6-weather | pass | out_of_scope | 863 |
| q7-diabetes | pass | medical_advice | 692 |
| q8-premise | pass | price | 1358 |
