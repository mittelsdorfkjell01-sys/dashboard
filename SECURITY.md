# Security policy

## Reporting a vulnerability

Do not open a public issue and do not include credentials, personal data, or
production details in a pull request. Use the repository's private security
advisory flow instead:

1. Open the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Describe the affected version, impact, reproduction steps, and a proposed
   mitigation if known.

If private advisories are unavailable, contact the repository owner through a
previously established private channel. Never send secrets in plain text.

## Scope

Security reports are welcome for the public and admin web applications, API,
authentication and authorization, uploaded media, scheduled workers, and
deployment configuration. Reports about third-party services should be sent to
the respective provider unless the issue is caused by this application's use of
that service.

## Maintainer process

- Reproduce without writing to production data.
- Revoke or rotate exposed credentials before publishing details.
- Add regression coverage and run dependency and secret scans.
- Publish details only after the fix is deployed.
