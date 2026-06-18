# Security Policy

## Reporting a vulnerability

Please report security issues privately by opening a GitHub security advisory for this
repository.

Do not include sensitive exploit details in a public issue.

## Benchmark safety model

The default hibench capture path is designed to avoid real upstream model calls:

- agents run in Docker against an empty generated workspace
- API keys are dummy benchmark values
- model API base URLs point at a local recorder
- the recorder returns synthetic successful completions

If you find a path that can leak credentials, call an upstream provider unexpectedly, or
capture unintended local files, please report it as a security issue.
