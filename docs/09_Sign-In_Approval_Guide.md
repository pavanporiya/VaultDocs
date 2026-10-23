# VaultDocs Sign-In Device Approval — Setup & Security Guide

Version: 1.0 · Applies to: device-approval login flow (`login_challenges`,
`trusted_devices`, `push_subscriptions`)

## 1. What the feature does

* **New/untrusted device signs in** → credentials are validated first. If the
  device is not trusted, the server returns **HTTP 202** and the UI shows
  **"Check your phone to approve this sign-in."** No JWT is issued yet.
* The server sends a **Web Push** notification to every registered trusted
  phone/PWA: **"Are you trying to sign in to VaultDocs?"** with
  **"Yes, it's me"** / **"No, deny"** actions.
* **No trusted phone registered?** The existing secure email OTP channel is
  used instead: a single-use 6-digit approval code is emailed. Approval is
  **never silently bypassed**.
* Approval requires an **authenticated trusted-device session** (JWT + valid
  trusted-device cookie) for the *same* user. A session can never approve
  itself, and push delivery alone never authorizes anything.
* On success the waiting browser completes the challenge (single-use,
  atomic) and receives its JWT.
* **"Remember this device for 30 days"** (unchecked by default) — only when
  checked *and* the sign-in was approved does the server mint a trusted
  device: a random 256-bit secret stored **only as a SHA-256 hash**, handed
  to the browser as an **HttpOnly / SameSite=Lax cookie** (`Secure` on
  HTTPS). Trust expires server-side after exactly 30 days.

## 2. Environment variables

Add to `.env` (see `.env.example`):

| Variable | Required | Purpose |
| --- | --- | --- |
| `VAPID_PUBLIC_KEY` | For Web Push | Base64url P-256 public key (65-byte uncompressed point). Public — safe for client code. |
| `VAPID_PRIVATE_KEY` | For Web Push | Base64url P-256 private key (32-byte raw or 27/28-byte DER). **Secret. Never commit or log.** |
| `VAPID_CLAIMS_EMAIL` | No | `mailto:` subject for VAPID claims (default `admin@vaultdocs.local`). |

Optional tuning (defaults are safe):

| Variable | Default | Purpose |
| --- | --- | --- |
| `LOGIN_CHALLENGE_EXPIRE_SECONDS` | `300` | Pending challenge lifetime |
| `TRUSTED_DEVICE_EXPIRE_DAYS` | `30` | Trust window for remembered devices |
| `PUSH_SUBSCRIPTION_EXPIRE_DAYS` | `60` | Forced subscription rotation |
| `LOGIN_APPROVAL_CODE_EXPIRE_MINUTES` | `10` | Email code lifetime |
| `LOGIN_APPROVAL_CODE_MAX_FAILED_ATTEMPTS` | `5` | Code brute-force lockout |
| `LOGIN_APPROVAL_CODE_COOLDOWN_SECONDS` | `60` | Resend cooldown |
| `RATE_LIMIT_ENABLED` | `true` | In-process auth rate limiting |
| `RATE_LIMIT_LOGIN_ATTEMPTS` / `RATE_LIMIT_LOGIN_WINDOW_SECONDS` | `10` / `300` | Login throttling |

**Startup validation:** if exactly one VAPID key is set, or either key is
malformed, the backend **fails safely at startup** with a critical log entry.
If both are unset, Web Push is disabled and the email approval fallback is
used — nothing is bypassed.

### Generating a VAPID key pair

```bash
.venv/Scripts/python -c "import base64; from py_vapid import Vapid02; from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat; v = Vapid02(); v.generate_keys(); print('VAPID_PUBLIC_KEY=' + base64.urlsafe_b64encode(v.public_key.public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)).decode().rstrip('=')); print('VAPID_PRIVATE_KEY=' + base64.urlsafe_b64encode(v.private_key.private_numbers().private_value.to_bytes(32, 'big')).decode().rstrip('='))"
```

Or with the CLI: `py_vapid generate --applicationServerKey` (convert output to
base64url as needed).

## 3. HTTPS / browser requirements

* **Web Push requires a secure context**: the PWA must be served over
  **HTTPS** (or `http://localhost` for development). Push is disabled by
  browsers on plain-HTTP LAN addresses.
* Supported: Chrome/Edge 80+, Firefox 72+, Safari 16.4+ (macOS/iOS), and any
  Chromium-based Android browser. iOS requires **Add to Home Screen** (PWA)
  for Web Push to work.
* Notification permission is requested **only** from the explicit
  **"Enable Notifications"** button in *Settings → Sign-In Approval
  Notifications* — never automatically.
* If permission is denied, the account simply keeps using the email code
  fallback.

## 4. Installing the PWA on a phone

1. Open VaultDocs in the phone browser over HTTPS.
2. **Android/Chrome:** menu (⋮) → *Add to Home screen* → *Install*.
   **iOS/Safari:** Share → *Add to Home Screen*.
3. Open the installed app, sign in, go to **Settings**.
4. Under *Sign-In Approval Notifications*, tap **Enable Notifications** and
   allow the prompt.
5. The device now appears under *Registered Devices* and receives
   sign-in approval pushes.

## 5. Security model (what the server enforces)

* Challenges are **256-bit random**, **short-lived**, **single-use**,
  bound to the user, and resolved **atomically** (`UPDATE … WHERE
  status='pending'`) so concurrent approvals have exactly one winner.
* **No JWT/session is issued before a valid approval** — the polling and
  completion endpoints never authenticate anyone by themselves.
* Approve/deny endpoints require a Bearer JWT **and** a valid trusted-device
  cookie of the same user (cross-site requests cannot set the Authorization
  header → CSRF-safe; foreign challenge ids are indistinguishable from
  unknown ones → no IDOR/enumeration).
* The device that initiated the sign-in can **never** approve its own
  challenge.
* Rate limits on: login (per identity and IP), challenge creation, status
  polling, resend, code verification and approval actions (HTTP 429 +
  `Retry-After`).
* Generic login errors (`Invalid email or password.`) prevent account
  enumeration; challenge polling returns sanitized statuses only.
* Push payloads contain the title/body prompt and the opaque, single-use
  challenge id — **never** passwords, JWTs, device credentials or reusable
  secrets. The phone still needs its own trusted session to approve.
* Only **hashes** are stored for device credentials, challenge ids and
  approval codes.
* **Password reset revokes every trusted device and push subscription.**
* Successful/denied approvals are audit-logged (user id, challenge id,
  device id, IP — never secrets).

## 6. Management endpoints (security settings UI)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/v1/devices` | List trusted devices (`is_current` marks this browser) |
| `DELETE` | `/v1/devices/{id}` | Revoke one device (forces approval next sign-in) |
| `POST` | `/v1/devices/push-subscriptions` | Register/rotate a Web Push subscription |
| `GET` | `/v1/devices/push-subscriptions` | List subscriptions (keys never returned) |
| `DELETE` | `/v1/devices/push-subscriptions/{id}` | Remove one subscription |
| `GET` | `/v1/devices/vapid-public-key` | Public key discovery (`enabled: false` when unset) |

Challenge endpoints: `POST /v1/auth/login` (202 = approval required),
`GET /v1/auth/login/challenges/{id}`, `…/approve`, `…/deny`, `…/complete`,
`…/resend`, `…/cancel`.

## 7. Database migration

Revision `9c1f7a2b5e31` (`alembic upgrade head`) **adds** the
`login_challenges`, `trusted_devices` and `push_subscriptions` tables.
It is additive-only: existing users, documents, folders, permissions and
sessions are untouched, and `downgrade -1` drops only the three new tables
(covered by automated tests in `backend/tests/test_login_security_migration.py`).

## 8. Known limitations

* The rate limiter is in-process (single-uvicorn deployment). Multi-worker
  deployments should back it with Redis or similar.
* Push delivery depends on the browser/OS push service; expired subscriptions
  are auto-removed on 404/410 and the email fallback always covers failures.
* End-to-end phone push was validated with an automated mock transport; a
  final manual check on a real phone (HTTPS + installed PWA + granted
  permission) is recommended per environment.
