# Incidents

What broke, the evidence, the cause, the fix, and how a repeat is detected.
Newest last. Incidents of the store monitor F1, whose fixes this project reuses,
are in [its incident log](https://github.com/siddharthkumarx/ecommerce-price-monitor/blob/main/docs/incidents.md).

## INC-001 - Commits showed as "Unverified" on GitHub (2026-11-20)

- **What happened:** the first commits were signed with an SSH key from the
  development environment that the owner's GitHub account does not hold. GitHub
  showed them as "Unverified" (API verification reason `unknown_key`), unlike the
  owner's other public repositories, whose commits are unsigned and carry no badge.
- **Fix:** signing switched off for this repository (`commit.gpgsign false`,
  `tag.gpgsign false`). The history was rewritten once with `git filter-repo`, which
  drops signatures and keeps authors, committers, dates and messages, and `main` was
  force-pushed while no live check was running. The two recon results that record
  the commit they ran on keep both SHAs (`git_sha`, `git_sha_before_rewrite`).
- **Verified:** the GitHub API reported verification reason `unsigned` for all 16
  commits on `main` after the push.
- **Detection:** the reason is visible per commit in the API
  (`commit.verification.reason`); a signed commit would show again as `unknown_key`.
