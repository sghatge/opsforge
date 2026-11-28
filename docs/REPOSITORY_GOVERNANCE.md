# OPSFORGE repository governance baseline

**Status:** initial baseline, applied to the OPSFORGE repository first.

## Required repository controls

| Control | Baseline |
|---|---|
| Project scope | README states purpose, setup, limitations and demo-data boundaries |
| Rights | LICENSE or explicit rights statement is present |
| Security reporting | SECURITY.md explains private reporting and safe testing |
| Contributions | CONTRIBUTING.md defines test and review expectations |
| Tests | Deterministic tests cover critical behaviour |
| CI | GitHub Actions runs with read-only repository permissions where possible |
| Secrets | No real credentials or customer data are committed |
| External actions | Production-impacting actions remain disabled unless separately reviewed and approved |
| Auditability | Approval, rejection and override outcomes are traceable |

## Enforcement model

The first CI check is intentionally narrow: required documentation files must exist and no real `.env` file may be tracked. The workflow does not assume that every portfolio repository has the same application stack or file layout.

Roll out in stages:
1. Observe and remediate missing documentation.
2. Enable blocking checks on flagship repositories after they comply.
3. Add project-specific tests for policy invariants and golden cases.
4. Extend the shared baseline to other repositories only after checking their architecture and existing workflows.

## Explicit exclusions

- A passing workflow is not a production-readiness certification.
- No automated check can establish consent, legal basis, or business approval from synthetic data.
- This baseline does not enable external CRM, email, SFTP, deployment, payment or customer-data actions.
- The repository remains independently maintained; no monorepo migration is required.
