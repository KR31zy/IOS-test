# V2.1 — Google and Sign in with Apple

Both sign-in and registration display side-by-side provider buttons under the main credential action. Username/email login, password recovery, invitations, farm permissions and existing mobile features are preserved. The Apple button uses an Apple Account, including supported iCloud accounts. Browser authorization works on either mobile platform; it is not the native iOS AuthenticationServices sheet. Return to the app manually after the provider's confirmation page. If the operating system kills the app during sign-in, start a new attempt. A new social account confirms its name and farm name, creating a separate private farm. Existing accounts with the same verified email require their current password to link. Returning users are identified by provider + immutable subject, not by email. Apple's private relay email may differ from an existing account; in that case choose the matching email if available or use the existing password account. No automatic cross-email linking is offered.

## Production provisioning (administrator, not the app user)

The implementation and migration are already part of `mobile/server/`. To use the same records as the web app, deploy this compatible backend against the existing shared database after backup and migration assessment; do not run a second database expecting it to synchronize automatically. Apply the bundled Alembic head `m20261119_social` using the deployment's normal migration pipeline. The isolated test server deliberately disables social providers.

Set the following **server process environment variables** through deployment secrets/configuration. The server does not automatically load `.env.example`. Never place private keys, client secrets or Apple credentials in the Flutter app or Git.

- `SOCIAL_PUBLIC_ORIGIN`: publicly reachable HTTPS origin, e.g. `https://api.your-domain.tld`, matching the app's server. No path.
- Google Cloud console: configure OAuth consent and create a **Web application** OAuth client. Register the exact URI `${SOCIAL_PUBLIC_ORIGIN}/api/auth/social/callback/google`. Set `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`. Publish/verify the consent screen as required for your audience.
- Apple Developer: enable Sign in with Apple on a primary App ID, associate a Services ID, register the HTTPS domain and return URL `${SOCIAL_PUBLIC_ORIGIN}/api/auth/social/callback/apple`. Create a Sign in with Apple signing key. Set `APPLE_OAUTH_CLIENT_ID` (Services ID), `APPLE_OAUTH_TEAM_ID`, `APPLE_OAUTH_KEY_ID`, `APPLE_OAUTH_PRIVATE_KEY_FILE` (absolute path to protected .p8). The backend generates short-lived client-secret JWTs. Configure Apple's private email relay for recovery email delivery if applicable.
- Both providers require HTTPS for the mobile flow. No local HTTP provider testing, fake tokens or embedded secrets are enabled. The existing password login can still be used on the development server.

Server verifies ID-token signature using official JWKS hosts, issuer, audience, expiry, nonce and subject; Google uses PKCE. The Apple callback accepts its specific browser origin for form POST, not other writes. App-only proof is separate from browser state, and the flow is single-use and expires in ten minutes. Finished flows clear personal details; expired rows are deleted on subsequent starts. Provider access/refresh tokens are not stored or returned. Configure proxy rate limits, periodic expired-flow cleanup and redaction of callback query strings (Google authorization code/state), proof and password request bodies in logs; keep the site under HTTPS. Account deletion, social identity unlinking, provider token revocation and native iOS button/presentation review remain release obligations, not implemented by this patch. Do not claim store approval. Review provider branding for the final build.

Official provider references:
- https://developers.google.com/identity/openid-connect/openid-connect
- https://developer.apple.com/documentation/signinwithapple/configuring-your-environment-for-sign-in-with-apple
- https://developer.apple.com/documentation/signinwithapplerestapi/generate-and-validate-tokens

## Verification

Backend tests simulate provider callback claims and exercise actual signed JWT decoding with a locally generated RSA key and stubbed token exchange/JWKS. They are not Google or Apple production sign-in tests. Flutter native build and physical-device testing remain blocked by the absent native SDK. No APK or IPA is claimed. Existing V2.0 documentation is retained as historical material; this file supersedes its authentication/version details.
