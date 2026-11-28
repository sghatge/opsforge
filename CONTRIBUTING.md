# Contributing

Thanks for helping improve OPSFORGE.

## Before opening a change

1. Read the [README](README.md), [Security Policy](SECURITY.md) and repository licence.
2. Keep the project local-first and preserve independent module boundaries.
3. Use synthetic or sanitized fixtures only. Never include customer data, credentials or confidential client material.
4. Keep external CRM, email, SFTP, payment and deployment actions disabled in demonstrations.
5. Explain user-visible behaviour, risk implications and any changes to approval or audit semantics.

## Development checks

Run the repository's documented tests:

```bash
python -m unittest discover -s tests -t .
```

If changing the Streamlit showcase or resilience modules, also follow the relevant workflow and test instructions in the README and `.github/workflows/`.

## Pull request expectations

- Describe the problem, proposed change and affected modules.
- Include or update deterministic tests for changed policy, approval, override or audit behaviour.
- Include negative-path tests for blocked, failed and invalid inputs where applicable.
- Update documentation and limitations when behaviour changes.
- Do not claim production readiness based only on passing tests.
