# Security policy

## Supported version

Security fixes target the current tagged release and the current release-candidate branch.

## Report a vulnerability

After the repository is public, submit suspected token leaks, unsafe URL launches, scope escalations, keyring failures, or private event disclosures through [GitHub's private vulnerability reporting](https://github.com/joryeugene/omarchy-calendar/security/advisories/new). Do not open a public issue.

Include the affected version, exact local steps, expected behavior, observed behavior, and whether real account data may have been exposed. Remove tokens, authorization codes, client credentials, account identities, and event content from reports and screenshots.

## Security invariants

- Provider access stays read-only.
- OAuth uses PKCE S256 and verifies state.
- Tokens stay in Secret Service, never dotfiles.
- Event and meeting actions allow safe HTTPS URLs only and never invoke a shell.
- Logs and user-visible errors redact token-shaped values.
- The Omarchy plugin is unsandboxed, so users should install only reviewed revisions.
