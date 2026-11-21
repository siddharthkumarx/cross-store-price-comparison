# Security

Please report a vulnerability or a leaked secret privately to hello@steadydata.co,
not in a public issue. You will get an answer within 48 hours.

This repository holds no credentials. The workflows use only the token GitHub gives
each run. Every push is scanned with gitleaks, and the locked dependencies are
audited with pip-audit in CI.
