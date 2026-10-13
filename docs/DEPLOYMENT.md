# Production setup & deployment

This guide is the complete runbook for taking the Vanika.AI site and waitlist to production. Do the steps in order.
Allow about half a day the first time. Design background: [ARCHITECTURE.md](ARCHITECTURE.md).

| You'll need admin access to | For |
|---|---|
| Microsoft 365 / Entra ID (vanika.ai tenant) | Sending mail from `info@vanika.ai` |
| Azure subscription | App Service `MailsBackend`, Static Web Apps, Key Vault |
| MongoDB Atlas | Waitlist database |
| GitHub repository | CI/CD secrets and variables |
| Cloudflare (optional, free) | Turnstile bot check |

> **Secrets never go in the repository.** Everything marked SECRET belongs in Azure Key Vault (or App Service
> settings) and GitHub secrets only. `.env` files are gitignored and are for local development.

---

## 1. Generate the application secrets

Run these once, on a trusted machine:

```bash
# VANIKA_ENCRYPTION_KEY: encrypts stored email addresses (AES-256-GCM)
python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"

# VANIKA_ADMIN_KEY: unlocks vanika.ai/admin
python -c "import secrets; print(secrets.token_urlsafe(32))"

# JWT_SECRET: InvestorDesk tokens (if not already set)
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

- Store all three in **Azure Key Vault** (step 5) and in the team password manager.
- **Back up `VANIKA_ENCRYPTION_KEY` in two places.** If it is lost, stored email addresses cannot be recovered;
  there is no reset. Never change it on a running system (see Operations → key rotation).

## 2. Email: `info@vanika.ai` (Microsoft 365)

vanika.ai mail is hosted on Microsoft 365 (MX `vanika-ai.mail.protection.outlook.com`). The backend sends the team
notification **and** the subscriber welcome email from `info@vanika.ai`. Notifications arrive in that same inbox, and
subscribers' replies go there too.

> **First, change the mailbox password.** It was shared in plain text while setting this up. Use a long random
> password and keep it only in the password manager and Key Vault.

### Option A: Microsoft Graph (recommended, long-term)

Microsoft is retiring password-based SMTP (see Option B), so this is the durable setup.

1. **Entra admin center → App registrations → New registration**
   - Name: `Vanika Mailer`.
   - Single tenant.
   - Note the **Application (client) ID** and **Directory (tenant) ID**.
2. **Certificates & secrets → New client secret.** Use 12–24 months, copy the value, and set a calendar reminder to
   renew it.
3. **Limit the app to the `info@vanika.ai` mailbox only.** Do not give it tenant-wide `Mail.Send`. Use Exchange Online
   *RBAC for Applications* in Exchange Online PowerShell:
   ```powershell
   Connect-ExchangeOnline
   New-ServicePrincipal -AppId <client-id> -ObjectId <enterprise-app-object-id> -DisplayName "Vanika Mailer"
   New-ManagementScope -Name "Vanika info mailbox" -RecipientRestrictionFilter "PrimarySmtpAddress -eq 'info@vanika.ai'"
   New-ManagementRoleAssignment -App <client-id> -Role "Application Mail.Send" -CustomResourceScope "Vanika info mailbox"
   ```
   The `<enterprise-app-object-id>` is on **Enterprise applications → Vanika Mailer**, not on the app registration.
   Check Microsoft's current "RBAC for Applications in Exchange Online" documentation if a cmdlet has changed.
4. Backend settings:
   - `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`: plain values.
   - `GRAPH_CLIENT_SECRET`: SECRET.
   - Leave `VANIKA_MAIL_TRANSPORT=auto`; it picks Graph automatically.

### Option B: SMTP with the mailbox password (bridge only)

This works today, but Microsoft disables SMTP basic authentication **by default for existing tenants at the end of
December 2026**. Use it only until Option A is in place.

1. **M365 admin center → Users → `info@vanika.ai` → Mail → Manage email apps** → enable **Authenticated SMTP**.
2. The tenant must allow SMTP AUTH. In Exchange PowerShell:
   `Set-CASMailbox -Identity info@vanika.ai -SmtpClientAuthenticationDisabled $false`.
3. If **Security defaults** is on in Entra ID, password-based SMTP is blocked. In that case use Option A.
4. Backend settings:
   - `SMTP_USERNAME=info@vanika.ai`
   - `SMTP_PASSWORD`: SECRET.
   - Defaults: `SMTP_HOST=smtp.office365.com`, `SMTP_PORT=587`, `SMTP_SECURITY=starttls`.

The backend logs the active transport at startup: `[Vanika] Mail transport: graph|smtp`.

## 3. Bot protection: Cloudflare Turnstile (recommended)

Free, privacy-friendly and usually invisible to visitors.

1. Go to **Cloudflare dashboard → Turnstile → Add widget**.
   - Hostnames: `vanika.ai`, `www.vanika.ai` (and `localhost` for testing).
   - Mode: **Managed**.
2. Copy the **site key**. It is public and goes in the frontend build variable `VITE_TURNSTILE_SITE_KEY`.
3. Copy the **secret key**. It is SECRET and goes in the backend setting `TURNSTILE_SECRET_KEY`.

**Set both or neither:** with only the secret set, every sign-up is rejected.

The other spam controls are always on and need no setup:
- disposable-domain blocklist
- typo catch
- MX check
- no-reply mailbox check
- honeypot
- per-IP rate limit

## 4. MongoDB Atlas

1. Reuse the existing cluster, or create one. Use M10+ for production backups. The connection string must be
   `mongodb+srv://…`, which is TLS-encrypted in transit by default.
2. **Database Access:** create a user with `readWrite` on the database. That's `investor_db`, or a new one if you set
   `VANIKA_DB_NAME`.
3. **Network Access:** allow the App Service **outbound IP addresses** (App Service → Networking). Avoid `0.0.0.0/0`.
4. **Backup:** enable continuous or cloud backups.
5. The `VanikaWaitlist` collection and its indexes are created automatically on first start. Any records from a
   pre-encryption build are encrypted in place at that point, and their plaintext is removed. No manual migration
   is needed.

## 5. Azure: backend (App Service `MailsBackend`)

1. **Key Vault:**
   - Create a vault, or reuse one.
   - Add the secrets: `vanika-encryption-key`, `vanika-admin-key`, `graph-client-secret` (or `smtp-password`),
     `turnstile-secret`, `mongodb-uri`, `jwt-secret`.
   - Enable the App Service's **system-assigned managed identity**.
   - Grant that identity the *Key Vault Secrets User* role.
2. **Settings → Configuration → Application settings.** Reference secrets as
   `@Microsoft.KeyVault(SecretUri=https://<vault>.vault.azure.net/secrets/<name>/)`:

   | Setting | Value |
   |---|---|
   | `MONGODB_URI` | Key Vault reference |
   | `MONGODB_DB_NAME` | `investor_db` (existing) |
   | `VANIKA_ENCRYPTION_KEY` | Key Vault reference |
   | `VANIKA_ADMIN_KEY` | Key Vault reference |
   | `VANIKA_EMAIL_POLICY` | `standard` (or `work_or_school` to refuse Gmail/Outlook etc.) |
   | `GRAPH_TENANT_ID` / `GRAPH_CLIENT_ID` / `GRAPH_CLIENT_SECRET` | Option A (secret via Key Vault) |
   | `SMTP_PASSWORD` | Option B only, Key Vault reference |
   | `TURNSTILE_SECRET_KEY` | Key Vault reference (optional) |
   | `CORS_ORIGINS` | existing Anvi origins **plus** `https://vanika.ai,https://www.vanika.ai` |
   | `JWT_SECRET` | Key Vault reference |
   | `SCM_DO_BUILD_DURING_DEPLOYMENT` | `true` (already set) |

   Keep the existing Anvi / InvestorDesk settings (`AZURE_COMMUNICATION_CONNECTION_STRING`, `EMAIL_PRIMARY_ANVI`, …)
   unchanged. **This backend also serves those sites.**
3. **General settings:**
   - Stack Python **3.10**.
   - **HTTPS Only: On**.
   - **Minimum TLS: 1.2**.
   - FTP/FTPS: Disabled.
   - Keep the existing startup command. If there is none, use
     `python -m uvicorn main:app --host 0.0.0.0 --port 8000`.
4. **Monitoring:** enable Application Insights and create log alerts on `[MAIL ERROR]` and
   `Could not store sign-up`.

## 6. Azure: frontend (Static Web Apps)

1. **Custom domains:** `vanika.ai` and `www.vanika.ai`. TLS certificates are free and automatic.
2. **Overview → Manage deployment token:** copy it for GitHub (step 7).
3. HTTPS, HSTS and the security headers are set by `public/staticwebapp.config.json`. Nothing to configure here.

## 7. GitHub (the repository that deploys)

Choose **one** repository as the deployment source. The code lives in both
`adityapuppala1/Vanika_Ai_Website` and `PraviDasAnvi/Vanika-Main-Website`. If both deploy to the same Azure
resources, they will overwrite each other. Configure the following only in the chosen one, and disable any old
workflows (e.g. in `AvanikaGyanaji/Anvi_Mail_backend_main`) that deploy `MailsBackend`.

| Type | Name | Value |
|---|---|---|
| Secret | `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` | Federated (OIDC) credential for backend deploys; subject `repo:<owner>/<repo>:ref:refs/heads/main` |
| Secret | `AZURE_STATIC_WEB_APPS_API_TOKEN` | SWA deployment token |
| Variable | `VITE_API_BASE_URL` | `https://<mailsbackend-host>` (no trailing slash) |
| Variable | `VITE_TURNSTILE_SITE_KEY` | Turnstile site key (optional) |
| Secret | `VITE_MAIL_ACCESS_KEY` | Only if the backend's `VANIKA_ROUTES_KEY` is set |

Also protect `main` (Settings → Branches): require a pull request and the **CI** check to pass.

## 8. Release

1. Open a pull request `V2 → main`. Wait for CI (backend tests on Python 3.10, frontend build) to pass, then review
   and merge.
2. `backend-deploy.yml` and `frontend-deploy.yml` run automatically. Watch them in the **Actions** tab.
   The order doesn't matter: the API is backward compatible both ways.

## 9. Verify in production (≈15 minutes)

- [ ] `https://<backend>/vanika/ping` returns 200, and the response has a `Strict-Transport-Security` header.
- [ ] The backend log stream shows:
  - `Mail transport: graph` (or `smtp`)
  - `Waitlist indexes ensured`
  - **no** `storage disabled` warning
- [ ] On vanika.ai, `test@mailinator.com` is rejected ("Temporary or disposable…").
- [ ] `you@gmial.com` offers "Use you@gmail.com".
- [ ] A real address of yours shows "You're on the list".
  - The welcome email arrives from `info@vanika.ai`.
  - The team notification arrives in `info@vanika.ai`.
  - Replying to the welcome email lands in `info@vanika.ai`.
- [ ] The same address again shows "You're already on the list", and no new emails are sent.
- [ ] `vanika.ai/admin` → sign in. The record shows ✓ Team · ✓ Welcome and its email type.
  - Export CSV works.
  - Remove the test record.
- [ ] In Atlas, the document shows `email_enc` (ciphertext) and no plaintext address.
- [ ] Other sites still work: one Anvi contact form and one InvestorDesk OTP login.

## 10. Rollback

- **Backend:** Azure → MailsBackend → Deployment Center → redeploy the previous successful deployment. Data in
  MongoDB is unaffected; keep `VANIKA_ENCRYPTION_KEY` unchanged.
- **Frontend:** Static Web Apps → Environments → reactivate the previous build, or revert the merge commit.
- The `V1` branch holds the original pre-V2 code.

---

## Operations

| Task | How |
|---|---|
| See / export the waitlist | `vanika.ai/admin` → Export CSV |
| Rotate the admin key | Generate a new one, update it in Key Vault, restart the App Service |
| Rotate the Graph client secret | Add a new secret in Entra, update Key Vault, restart, then delete the old secret |
| Refresh the disposable-domain list (monthly) | `cd Backend_Website && python -m Vanika_Mailing.update_disposable_domains`, run tests, then open a PR |
| Rotate the encryption key | Not supported in place. Export CSV, set the new key on a **new** collection (`VANIKA_WAITLIST_COLLECTION`), re-import. Plan it as a maintenance task. |
| Allow only work/school emails | Set `VANIKA_EMAIL_POLICY=work_or_school`, then restart |
| Email delivery problems | The dashboard "Emails sent" column shows ✕; hover for the reason. Check the log for `[MAIL ERROR]`. |
