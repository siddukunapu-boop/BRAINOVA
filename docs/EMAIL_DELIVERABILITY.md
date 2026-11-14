# BRAINOVA Email Deliverability & Transport Guide

## 1. Delivery Status Lifecycle

BRAINOVA distinguishes between provider submission and confirmed inbox delivery:

| Status | Meaning |
| --- | --- |
| `queued` | Delivery attempt initialized with `correlation_id`. |
| `accepted_by_provider` | SMTP server (`250 OK`) or HTTPS API (`200/202` with `provider_message_id`) accepted the message for relay. **Does not guarantee inbox placement.** |
| `delivered` | Confirmed via authenticated provider webhook (`POST /api/email/webhook`). |
| `bounced` | Provider webhook reported a bounce or spam complaint; address hash is added to `email_suppressions`. |
| `rejected` | Provider or SMTP server rejected the recipient/payload synchronously (`400`/`422`/`550`). |
| `failed` | Connection error, timeout, authentication failure, or provider rate limit. |

Observability logs (`email_delivery_logs` and `brainova.email`) record only `correlation_id`, `provider_message_id`, `recipient_domain`, `provider`, `connect_duration_ms`, `submit_duration_ms`, `total_duration_ms`, `smtp_code`, `status`, `error_category`, and `timestamp`. Full email addresses, OTP codes, and credentials are never logged.

---

## 2. Local Development vs. Production Provider Selection

1. **No Custom Domain Options (Development / Free Tier)**:
   - **Gmail SMTP (already supported, no new account needed)**:
     `EMAIL_PROVIDER=smtp`, `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_USE_TLS=true`, `SMTP_USERNAME=<gmail>`, `SMTP_PASSWORD=<16-char-app-password>`, `SMTP_FROM_EMAIL=<gmail>`.
     - Free quota: ~500 emails/day. Passes Gmail's own SPF/DKIM, but lacks delivery webhooks and consumer `@gmail.com` senders may face spam filtering or burst throttling at Outlook/Yahoo/corporate gateways.
   - **Brevo Free SMTP Relay (no custom domain required)**:
     `EMAIL_PROVIDER=smtp`, `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`, `SMTP_USE_TLS=true`, `SMTP_USERNAME=<brevo-smtp-login>`, `SMTP_PASSWORD=<brevo-smtp-key>`, `SMTP_FROM_EMAIL=<single-verified-gmail-sender>`.
     - Free quota: 300 emails/day. Supports single-sender verification (e.g., your Gmail address; avoid `@yahoo.com` as sender due to Yahoo's `p=reject` DMARC policy) and provides delivery/bounce tracking in Brevo's dashboard/webhooks. Without a custom domain, some corporate/Outlook filters may still place mail in Spam/Junk.
   - **Providers NOT usable without a custom domain**: Resend (`onboarding@resend.dev` only sends to your own account email), Amazon SES (Sandbox restricts recipients), Postmark (blocks free webmail sender domains).
2. **Production Transactional Email (`EMAIL_PROVIDER=resend`, requires custom domain)**:
   - Set `EMAIL_PROVIDER=resend`, `EMAIL_API_KEY=<resend-api-key>`, `EMAIL_SENDER_DOMAIN=<verified-domain>`, `SMTP_FROM_EMAIL=noreply@<verified-domain>`, `SMTP_FROM_NAME=BRAINOVA`, and `EMAIL_WEBHOOK_SECRET=<random-secret>`.

---

## 3. Sender-Domain Verification & DNS Authentication (Production)

To achieve reliable inbox delivery across Gmail, Outlook/Hotmail, Yahoo, iCloud, university, and corporate recipients:

1. **Verify Your Sending Domain** (e.g., `mail.yourdomain.com`) in your transactional email provider dashboard.
2. **SPF (`TXT`)**: Publish the provider's `TXT` SPF record on your sending subdomain so receiving MX servers authorize the provider's IPs.
3. **DKIM (`CNAME` / `TXT`)**: Publish the provider's DKIM public key records so every OTP email is cryptographically signed (`d=mail.yourdomain.com`).
4. **DMARC (`TXT _dmarc.yourdomain.com`)**: Publish a DMARC policy aligned with your SPF/DKIM domain (e.g., `v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com`).
5. **Webhooks & Suppression**:
   - Point your provider's webhook endpoint to `POST /api/email/webhook` with header `X-Email-Webhook-Secret: <EMAIL_WEBHOOK_SECRET>`.
   - Duplicate webhook deliveries are ignored idempotently via `email_webhook_events`.
   - Hard bounces and rejected addresses are stored as SHA-256 hashes in `email_suppressions`.
6. **Provider Sending Limits**: `SMTP_TIMEOUT_SECONDS` defaults to `8`s (clamped `2..15`s) so provider submission or failure completes within the 5–6s target under normal network conditions.
