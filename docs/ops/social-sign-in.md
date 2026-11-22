# Sign in with Google and Apple — setup

Added 2026-11-21. The code is in place; the buttons on `/anmelden` appear only
once a provider's settings are complete (`GET /account/oauth/providers`).

## How it works

- `GET /account/oauth/{google|apple}/start?redirect=/konto` sets a signed,
  httpOnly flow cookie (state, nonce, PKCE verifier, 10 min) and redirects to
  the provider.
- The provider returns to `ACCOUNT_API_PUBLIC_ORIGIN/account/oauth/<provider>/callback`
  (Google: GET, Apple: form POST). The API checks the state against the
  cookie, exchanges the code, verifies the ID token against the provider's
  published keys (issuer, audience, expiry, nonce), then finds, links or
  creates the account (`service.sign_in_with_identity`), sets the session and
  redirects to `ACCOUNT_PUBLIC_ORIGIN<redirect>`; on failure to
  `/anmelden?oauth_error=<reason>`.
- Linking: a provider-confirmed email that matches an existing account links to
  it. If that account was never confirmed, its password is discarded first.
- New accounts are confirmed, carry the terms acceptance (the page says so next
  to the buttons) and get a display name from the provider or the address.
  They have no usable password until set via "Passwort vergessen".

Requires migration `0100_app_user_identities` (apply manually on Neon, see the
prod-migration notes) and `PyJWT[crypto]` (requirements.txt).

## Common settings

| Variable | Value |
|---|---|
| `ACCOUNT_PUBLIC_ORIGIN` | the public site, e.g. `https://surfwinddata.com` (already used for mail links) |
| `ACCOUNT_API_PUBLIC_ORIGIN` | where the browser reaches the API, e.g. `https://api.surfwinddata.com` |
| `COOKIE_SECURE=true` | required in production: Apple's form POST is cross-site and only carries a `SameSite=None; Secure` cookie |

## Google (free)

1. Google Cloud Console → APIs & Services → OAuth consent screen: app name
   "surfwind data", support email, scopes `openid`, `email`, `profile`;
   publish the app.
2. Credentials → Create credentials → OAuth client ID → *Web application*.
   Authorised redirect URI: `https://<api-origin>/account/oauth/google/callback`.
3. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`.

## Apple (Apple Developer Program, ~99 €/year)

1. Certificates, Identifiers & Profiles → Identifiers → an **App ID** with
   "Sign in with Apple" enabled (primary).
2. Identifiers → **Services ID** (e.g. `com.surfwinddata.web`), enable "Sign in
   with Apple", configure: primary App ID from step 1, domain of the site, return
   URL `https://<api-origin>/account/oauth/apple/callback` (Apple accepts
   HTTPS only — no localhost).
3. Keys → new key with "Sign in with Apple" → download the `.p8` (once!) and
   note its Key ID.
4. Set `APPLE_OAUTH_CLIENT_ID` (the Services ID), `APPLE_OAUTH_TEAM_ID`,
   `APPLE_OAUTH_KEY_ID`, `APPLE_OAUTH_PRIVATE_KEY` (the .p8 contents; newlines
   may be written as `\n`).

Apple sends the person's name only on the very first sign-in, and may give a
private relay address (`…@privaterelay.appleid.com`) instead of the real one.

## Check

`curl https://<api-origin>/account/oauth/providers` → `{"google": true, "apple": true}`.
