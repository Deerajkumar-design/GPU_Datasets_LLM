# Dataset Summary: preproduction_llama32_3b_500f_6ctx_v1

- Families: 500
- Instances: 3000
- Prompt: llama_chat_v4 / 5d2869822989e19b
- Model/tokenizer: meta-llama/Llama-3.2-3B-Instruct / hf:meta-llama/Llama-3.2-3B-Instruct
- Context ladder: 4K, 8K, 16K, 32K, 64K, 82K

## Family Counts

- Domain: {'SEC': 125, 'FDA': 125, 'CLINICAL_TRIALS': 125, 'FRED': 125}
- Question type: {'DIRECT_RETRIEVAL': 100, 'ENTITY_UNIT_BINDING': 95, 'RETRIEVAL_CALCULATION': 150, 'TEMPORAL_VERSION': 55, 'UNANSWERABLE': 100}
- Answerability: {'true': 400, 'false': 100}

## Rendered Input Tokens

| Context | N | Min | Mean | Median | P5 | P95 | Max |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4K | 500 | 4202 | 4273.3 | 4276.0 | 4218.9 | 4331.0 | 4359 |
| 8K | 500 | 8257 | 8330.5 | 8329.0 | 8273.0 | 8393.0 | 8459 |
| 16K | 500 | 16351 | 16442.3 | 16440.5 | 16380.9 | 16514.0 | 16558 |
| 32K | 500 | 32534 | 32671.4 | 32663.0 | 32577.9 | 32787.0 | 32836 |
| 64K | 500 | 64894 | 65126.1 | 65115.5 | 64953.9 | 65326.0 | 65367 |
| 82K | 500 | 81622 | 81745.1 | 81748.0 | 81678.9 | 81795.0 | 81800 |
