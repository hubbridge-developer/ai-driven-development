# Model Comparison Notes

## Embedding Models: all-MiniLM-L6-v2 vs bge-base-en-v1.5

Key differences for spec search use case:

| Aspect | all-MiniLM-L6-v2 | bge-base-en-v1.5 |
|---|---|---|
| **Architecture** | 6-layer MiniLM | 12-layer BERT base variant |
| **Parameters** | ~22M | ~110M |
| **Dimensions** | 384 | 768 |
| **Model Size** | ~80 MB | ~440 MB |

- **Retrieval quality:** On MTEB-style tasks, BGE-base-v1.5 typically scores ~3-8 points higher (absolute) in nDCG/Recall than MiniLM-L6. Fewer false positives and better recall on nuanced queries.
- **Vector size:** MiniLM 384d vs BGE 768d. Qdrant collection must be recreated with the new dimension, and storage/ANN memory roughly doubles.
- **Latency/throughput:** BGE is slower per embedding (about 1.5-2x) and uses more RAM; MiniLM is faster and cheaper. For POC scale, BGE is usually still fine on CPU; for higher throughput, use GPU or batch embeddings.
- **Token handling:** Both are English-focused; BGE tends to capture longer-range semantics better, which helps with multi-section spec queries.

### Switching to BGE

Set in `qdrant_client/service.py`:
```python
EMBEDDING_MODEL_NAME = "BAAI/bge-base-en-v1.5"
VECTOR_DIMENSIONS = 768
```
Then reset the Qdrant collection and reindex all specs.

> **Lighter alternative:** `bge-small-en-v1.5` (384d) — closer to MiniLM speed but better quality.

---

## LLM Models: codellama:13b vs codellama:7b

| Aspect | codellama:13b | codellama:7b |
|---|---|---|
| **Parameters** | ~13B | ~7B |
| **RAM** | ~8 GB | ~4 GB |
| **Speed** | Slower | ~2x faster |

- **Quality:** 13B is noticeably better at code reasoning, following structured prompts, and generating longer coherent outputs. 7B is fine for short/simple tasks but degrades on complex specs or multi-file reasoning.
- **Latency/cost:** 7B responds faster and cheaper; 13B costs more compute. On CPU, 13B may feel sluggish; on GPU it's fine if memory allows.
- **Practical split:** Use 13B for high-fidelity generation (`spec_generation`), keep 7B for quick tasks (discovery, publisher, validator) if you want a speed/quality mix.

---

## mistral:7b vs codellama:7b

| Aspect | mistral:7b | codellama:7b |
|---|---|---|
| **Natural language understanding** | Strong | Weak |
| **Instruction following** | Strong | Moderate |
| **Structured XML output** | Good | Good |
| **Code generation** | Good | Excellent |
| **Reasoning / nuance** | Better | Weaker |
| **RAM usage** | ~4.1 GB | ~3.8 GB |

- **For spec generation (POC 1):** `mistral:7b` wins — specs are mostly natural language wrapped in XML.
- **For code generation (POC 2):** `codellama:7b` wins — purpose-built for code output.

### Current Configuration

All agents use `mistral:7b` via `config/llm_routing_ollama.yaml`. When POC 2 starts, code generation agents should switch to `codellama:7b`.
