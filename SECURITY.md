# Security policy

## Scope

This repository is an independent portfolio project and local MVP. It is not approved for production customer data, production CRM activation, or public multi-user operation.

## Supported versions

Security fixes are currently considered for the latest code on the `main` branch. No formal service-level agreement or supported production release is offered.

## Reporting a vulnerability

Please do not publish exploit details, credentials, personal data or sensitive logs in a public issue.

Report suspected vulnerabilities privately through the contact route on the [maintainer's LinkedIn profile](https://www.linkedin.com/in/sangram-g-2369705b). Include:
- affected commit or version;
- concise reproduction steps;
- impact and prerequisites;
- a safe proof of concept using synthetic data.

Allow reasonable time for triage and remediation before public disclosure. Do not test against systems or data you do not own or have explicit permission to assess.

## Safe-use requirements

- Use synthetic or sanitized data only.
- Never commit API keys, access tokens, passwords, customer exports or production identifiers.
- Keep credentials in environment variables or an approved local secret store; do not place them in source, logs or screenshots.
- Keep CRM, email, SFTP, deployment and other external actions disabled unless a separate security, privacy and change-control review authorizes them.
- Human approval in this prototype is not a substitute for enterprise identity, authorization or segregation-of-duties controls.
