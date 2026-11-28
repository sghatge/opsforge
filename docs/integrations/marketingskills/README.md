# MarketingSkills integration contract — OPSFORGE

Status: proposed additive integration; upstream source remains authoritative for its own skill text.

## Upstream
- Repository: https://github.com/coreyhaines31/marketingskills
- Licence: MIT (retain upstream LICENSE and attribution when redistributing skill files)
- Install model: Agent Skills under `.agents/skills/`; pin an audited commit before vendoring.
- Do not install or execute the upstream collection wholesale.

## OPSFORGE control boundary
OPSFORGE Policy, ACC Agent Gate, and the existing human-approval workflow remain authoritative. MarketingSkills provide task guidance only; they do not grant tools, credentials, network access, data access, or execution permissions.

All outputs must preserve FACT / HYPOTHESIS / ASSUMPTION / UNKNOWN distinctions and cite evidence. No fabricated campaign IDs, counts, owners, approvals, customer facts, or performance results. Synthetic data by default; redact personal data.

Production sends, audience activation, CRM writes, workflow starts, budget changes, consent changes, and external publication are prohibited without existing policy checks and named human approval. Fail closed on missing policy, evidence, tests, or approver.

## Curated skill mapping
- CRM/lifecycle: email-sequence, churn-prevention, customer-research
- Measurement: analytics-tracking, ab-test-setup
- Growth: content-strategy, marketing-ideas, launch-strategy
- Web conversion: page-cro, signup-flow-cro, form-cro
- Discovery: seo-audit, ai-seo, site-architecture
- Revenue process: revops, sales-enablement

Names are a routing allowlist, not proof that every upstream skill is present in every upstream revision. Confirm exact directories and content at the pinned commit before import.

## Integration gates
1. Record upstream commit SHA, licence, file manifest, and checksums.
2. Review each selected SKILL.md and referenced scripts/assets for unsafe instructions, secrets, network calls, data collection, and conflicting policies.
3. Store imported skills in a separate namespace; never overwrite OPSFORGE policy or existing skills.
4. Add deterministic validation and regression tests before enabling routing.
5. Keep all external actions disabled by default; require human approval through existing gates.
6. Document provenance and upgrade diffs for every upstream update.

## Free-tier implementation
Use GitHub branches/PRs and existing local Python test tooling. No paid API, hosted vector database, or new infrastructure is required.

## Rollback
Disable the marketing skill router or revert this additive integration commit. Existing OPSFORGE agents, policy, data, and deployments must remain unchanged.
