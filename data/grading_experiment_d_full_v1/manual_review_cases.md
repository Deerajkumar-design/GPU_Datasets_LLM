# Experiment D Manual Review Cases

## FDA_0099_32K

- family: `FDA_0099`
- context/domain/type: `32K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`
- matched context value: `EQ 2.5MG BASE/BOT`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## SEC_0086_32K

- family: `SEC_0086`
- context/domain/type: `32K` / `SEC` / `TEMPORAL_VERSION`
- answerable: `True`
- question: Using only the SEC XBRL company-facts records supplied in the context, what value did COCA COLA CO (CIK 0000021344) report for us-gaap:CashAndCashEquivalentsAtCarryingValue for the period ending 2017-12-31 in the MOST RECENTLY FILED version of that fact — accession 0000021344-20-000006, form 10-K, filed 2020-02-24 — in USD? Report the exact value from that version.
- gold: `6,102,000,000`
- model answer: `12859000000.0`
- matched context value: `12859000000.0`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0102_64K

- family: `FRED_0102`
- context/domain/type: `64K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series NYUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for New York on the observation dated 2023-11-01. Report the value for series NYUR exactly.
- gold: `4.200`
- model answer: `4.0`
- matched context value: `4.0`
- matched distractor type: `NEAR_MATCH_VALUE`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0100_32K

- family: `FRED_0100`
- context/domain/type: `32K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Illinois on the observation dated 2018-01-01. Report the value for series ILUR exactly.
- gold: `4.500`
- model answer: `4.1`
- matched context value: `4.1`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0019_64K

- family: `FDA_0019`
- context/domain/type: `64K` / `FDA` / `TEMPORAL_VERSION`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA064139 (sponsor: CHARTWELL RX)? Answer in YYYY-MM-DD form.
- gold: `1996-01-29`
- model answer: `1997-11-05`
- matched context value: `1997-11-05`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0103_32K

- family: `FRED_0103`
- context/domain/type: `32K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series PAUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Pennsylvania on the observation dated 2017-06-01. Report the value for series PAUR exactly.
- gold: `4.900`
- model answer: `4.8`
- matched context value: `4.8`
- matched distractor type: `NEAR_MATCH_VALUE`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0099_64K

- family: `FDA_0099`
- context/domain/type: `64K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`
- matched context value: `EQ 2.5MG BASE/BOT`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0099_4K

- family: `FDA_0099`
- context/domain/type: `4K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`
- matched context value: `EQ 2.5MG BASE/BOT`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0038_4K

- family: `FRED_0038`
- context/domain/type: `4K` / `FRED` / `DIRECT_RETRIEVAL`
- answerable: `True`
- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2022-09-01 (the month beginning 2022-09-01)? Report the currently published figure exactly.
- gold: `3.500`
- model answer: `3.9`
- matched context value: `3.9`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0093_64K

- family: `FRED_0093`
- context/domain/type: `64K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series FLUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Florida on the observation dated 2018-08-01. Report the value for series FLUR exactly.
- gold: `3.500`
- model answer: `3.6`
- matched context value: `3.6`
- matched distractor type: `NEAR_MATCH_VALUE`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0100_82K

- family: `FRED_0100`
- context/domain/type: `82K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Illinois on the observation dated 2018-01-01. Report the value for series ILUR exactly.
- gold: `4.500`
- model answer: `4.1`
- matched context value: `4.1`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0020_82K

- family: `FDA_0020`
- context/domain/type: `82K` / `FDA` / `TEMPORAL_VERSION`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the submission status date of the ORIGINAL submission (submission type ORIG) for FDA application ANDA091431 (sponsor: HERITAGE)? Answer in YYYY-MM-DD form.
- gold: `2013-12-30`
- model answer: `2024-05-01`
- matched context value: `2024-05-01`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0100_64K

- family: `FRED_0100`
- context/domain/type: `64K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series ILUR ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for Illinois on the observation dated 2018-01-01. Report the value for series ILUR exactly.
- gold: `4.500`
- model answer: `4.0`
- matched context value: `4.0`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0099_16K

- family: `FDA_0099`
- context/domain/type: `16K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`
- matched context value: `EQ 2.5MG BASE/BOT`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0104_82K

- family: `FRED_0104`
- context/domain/type: `82K` / `FRED` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the FRED records supplied in the context, report the value of FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency for United States on the observation dated 2021-07-01. Report the value for series UNRATE exactly.
- gold: `5.400`
- model answer: `6.2`
- matched context value: `6.2`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FRED_0038_8K

- family: `FRED_0038`
- context/domain/type: `8K` / `FRED` / `DIRECT_RETRIEVAL`
- answerable: `True`
- question: Using only the FRED records supplied in the context, what value does the most recent vintage report for FRED series UNRATE ("Unemployment Rate"), measured in Percent, seasonally adjusted, monthly frequency, for the observation dated 2022-09-01 (the month beginning 2022-09-01)? Report the currently published figure exactly.
- gold: `3.500`
- model answer: `3.9`
- matched context value: `3.9`
- matched distractor type: `OTHER_SAME_DOMAIN`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0105_4K

- family: `FDA_0105`
- context/domain/type: `4K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of ATORVASTATIN CALCIUM in product number 002 under FDA application NDA200153 (dosage form TABLET, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 20MG BASE`
- model answer: `EQ 20MG BASE`
- matched context value: `EQ 20MG BASE`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0099_82K

- family: `FDA_0099`
- context/domain/type: `82K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`
- matched context value: `EQ 2.5MG BASE/BOT`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable

## FDA_0099_8K

- family: `FDA_0099`
- context/domain/type: `8K` / `FDA` / `ENTITY_UNIT_BINDING`
- answerable: `True`
- question: Using only the Drugs@FDA records supplied in the context, what is the listed strength of AMLODIPINE BESYLATE in product number 001 under FDA application NDA219531 (dosage form FOR SOLUTION, route ORAL)? Report the strength string exactly as recorded.
- gold: `EQ 2.5MG BASE/BOT`
- model answer: `EQ 2.5MG BASE/BOT`
- matched context value: `EQ 2.5MG BASE/BOT`
- matched distractor type: `None`
- review reason: answer value appears in context but deterministic distractor type is unavailable
