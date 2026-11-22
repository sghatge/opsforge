# OPSFORGE Research Agent v0.1

## Current implementation boundary
The Research Agent is a fixed-plan OPSFORGE agent. It retrieves only from an explicit `sources` array supplied in the run payload, ranks by deterministic lexical overlap, and asks the configured provider to produce a cited synthesis. Citations must use run-local IDs such as `[S1]`; every source is also returned as metadata for auditability.

NotebookLM notebooks and Gemini Gems are separate Google product surfaces. This implementation does not call either surface or infer an export API. Populate the run's sources from a reviewed export or approved application-managed corpus when available.

## Run shape
```json
{
  "question": "What should we prioritize for retrieval quality?",
  "sources": [
    {"title": "Reviewed source title", "url": "https://example.org/reference", "text": "Reviewed source text ..."}
  ],
  "top_k": 5
}
```

Set `OPSFORGE_LLM_PROVIDER=gemini` and `GEMINI_API_KEY` in the server environment for Gemini. Optional `GEMINI_MODEL` selects the model; default is `gemini-3.6-flash`. The `run-gemini.ps1` helper accepts the key through a hidden prompt and clears it when the server stops. If no Gemini key is configured, keep the deterministic provider for safe local demonstrations. Never put keys in the repository or task payloads.

## Limits
- Retrieval is lexical, not embeddings or semantic reranking.
- Source freshness, rights, and quality must be reviewed before ingestion.
- Model citations are not proof of entailment. Validate quoted claims against source text.
- The 128 reported NotebookLM records still need a reconciled export (title, canonical URL, text/content reference, type, date, availability, duplicate cluster, review status).
- No external production actions are available to this agent.
