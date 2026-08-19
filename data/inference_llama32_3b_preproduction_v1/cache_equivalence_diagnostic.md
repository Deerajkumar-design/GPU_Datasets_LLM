# Cache Equivalence Diagnostic

The required DynamicCache vs OffloadedCache sanity test failed. The full 600-instance inference run was not launched.

- model: `meta-llama/Llama-3.2-3B-Instruct`
- revision: `0cb88a4f764b7a12671c53f0838cd831a0843b95`
- tokenizer: `hf:meta-llama/Llama-3.2-3B-Instruct`
- prompt: `llama_chat_v2` / `14cc206955296997`
- frozen date: `09 Aug 2026`

| instance | length | input tokens | token IDs equal | decoded text equal | dynamic hash | offloaded hash |
|---|---|---:|---|---|---|---|
| `CT_0007_4K` | 4K | 4298 | False | False | `37a5e0769124cecbb72177dfb8d62b041391ad1544e19a872836b06b92010081` | `52af706f6aeea9466c727e9ece22f94d3f53c220093dc52d3bab7935ff969b86` |
| `CT_0007_8K` | 8K | 8383 | True | True | `d07d5080bc821548d99b5469ff09c98eef8b6bcb5934c75cb3c87ec3b9c916f0` | `d07d5080bc821548d99b5469ff09c98eef8b6bcb5934c75cb3c87ec3b9c916f0` |

## Required Decision

Because at least one prompt produced different generated token IDs between DynamicCache and OffloadedCache, the experiment gate requires stopping before the 600-instance run. No scoring or hallucination analysis was performed.
