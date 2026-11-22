# NotebookLM source map

This records the three NotebookLM knowledge bases connected to OPSFORGE and their role in the application-managed knowledge architecture. NotebookLM is a separate research and synthesis surface; it is not treated as a directly callable Gemini API retrieval endpoint.

| Notebook | Notebook ID | Baseline source count | Intended knowledge domain | Audit trail |
|---|---|---:|---|---|
| 01 – OPSFORGE Academy | `f6006295-9623-48d6-8ce9-f95a93e0ee7d` | 48 (reported 2026-11-20) | Gemini API, MCP, RAG, agentic AI, OPSFORGE architecture and implementation | `OPSFORGE_Knowledge_Audit_v1`, `OPSFORGE_Source_Audit_v2` |
| 02 – Enterprise MarTech Library | `b7437cf2-58e6-4804-8071-4825e0f9ef9b` | 54 (reported 2026-11-20) | Adobe Campaign/AEP/AJO, Salesforce Marketing Cloud/Data Cloud, CRM, segmentation, deliverability, customer journeys | `MarTech_Source_Audit_v2` (two similarly named notes observed) |
| 03 – AI Business Intelligence | `505edcbf-5541-4a92-b683-e5a265eb58d9` | 26 (reported 2026-11-20) | Enterprise AI market, adoption, consulting, governance, pricing, ROI and commercialization | `AI_Business_Intelligence_Audit_v1`, `Business_Intelligence_Verification_v2` |

## Visible source-title sample: AI Business Intelligence

The following titles were visible in the connected notebook UI on 2026-11-22. This is a sample, not a complete 26-source export:

- “Best AI Tools for Enterprise in 2026: 14 Platforms Ranked by Fit, Governance, and Cost”
- “150+ AI statistics for 2026: spend, cost, and AI ROI” (CloudZero)
- “2026 State of SaaS report” (BetterCloud)
- “Agentic AI Adoption in Indian Enterprises” (NASSCOM)
- “AI Consulting Firms by Revenue Band 2026” (Alice Labs)
- “Best AI Consulting Firms 2026” (CloudMotiv)
- “Best AI Governance Consulting Firms 2027”
- “Gartner Predicts 40% of Enterprise Apps Will Feature Task-Specific AI Agents by 2026”
- “McKinsey technology trends outlook 2026”
- “The State of AI: Global Survey 2026” (McKinsey)
- “Salesforce Agentforce Pricing”
- “The Cloud 100 Benchmarks Report 2025” (Bessemer Venture Partners)
- “Vertical SaaS Trends: Why Niche Platforms Win”
- “What Is MCP? The Model Context Protocol Explained” (Odin AI)

## Complete source map still needed
The connected UI confirmed notebook identity, counts, audit-note titles, and a sample of source titles. It did not expose a clean complete title + canonical URL + status export for all 128 reported baseline sources. Add that export as a machine-readable CSV/JSON ledger before building production retrieval. Include one row per source and fields: `notebook_id`, `notebook_name`, `source_title`, `canonical_url`, `source_type`, `topic_tags`, `version_or_published_date`, `retrieved_at`, `availability`, `duplicate_cluster`, `claim_or_use`, and `review_status`.
