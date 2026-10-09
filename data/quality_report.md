# Data quality report

Findings from the seven allowlisted pages after extract, prices, and chunking.

## Blank price-list row

The price list has a row with an empty procedure name. It is stored with `treatment: null`, `answerable: false`, and `flag: blank_procedure`. It is not an answerable price.

- `Procedure: | Details: | Price in USD: $18995`

## Colorectal details cell

The colorectal row's Details cell is the text "18995 USD". The price cell is $18995.

- `Procedure: Colorectal Cancer | Details: 18995 USD | Price in USD: $18995`

## Unrendered priceRange tag

The price-list About HTML contains the unrendered PHP tag `<?=$priceRange?>`. The extract removes that token, so the sentence has no numeric range. The price-list table still shows $18995.

```
This range shows the clinic's promise to offer
```

## Load More truncation

The comparison clinic table is the first batch only. The page includes a Load More control, so later clinics are not in the saved HTML.

Comparison clinic records: 5.

## VISANI Puebla vs Mexico City

The clinic link text says Puebla and the location cell says Mexico City.

- clinic `VISANI® Stem Cells in Puebla, Mexico`, location `Mexico City, Mexico`, price $5500

## Appendix package referenced but not in sources

Center cards name Alternative Appendix Cancer Treatment Package. That package is not one of the seven allowlisted URLs and was not fetched.

Mentioned on: clinic_profile, clinic_videos, price_list

## Pages with no price

Answerable price records are missing for: clinic_videos

The video page has titles and a center card. It has no answerable treatment price. A sidebar line `Price Range: $18995 - $18995` is not turned into an ITC price record, because the price-list rows already state $18995.

## Missing recovery time

The three package pages list a 3-week program and a follow-up consult after 3 months. They do not list a recovery duration. Phrases such as "partner in your own recovery" are not a time.

## No video transcripts

The video page stores titles in one section, one title per line. There are no transcripts. Those chunks are indexed and flagged.

## Section counts

- clinic_profile: 31
- package_7903: 23
- package_7902: 23
- package_7901: 23
- clinic_videos: 8
- price_list: 8
- price_comparison: 11

## Chunk counts

- clinic_profile: 32
- package_7903: 23
- package_7902: 23
- package_7901: 23
- clinic_videos: 11
- price_list: 8
- price_comparison: 11
- total: 131
