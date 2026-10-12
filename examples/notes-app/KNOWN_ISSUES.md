# notes-app – known issues (scoring key)

This is a deliberately "vibe-coded" prototype. It works on a laptop, but it is not safe or scalable in production. These are the issues proto2prod's agents are expected to find (analyzer / security reviewer) and fix (refactor agent). The end-to-end tests score each run against this list.

**Do not fix these by hand.** They are the test.

| ID | Severity | Where | Issue | Expected fix |
|---|---|---|---|---|
| P2P-01 | critical | `src/app/api/notes/route.ts` | `GET` returns **every user's notes** when `userId` is missing, and trusts any `userId` passed in (IDOR). | Derive the user from the session server-side; ignore client-supplied `userId`. |
| P2P-02 | critical | `src/app/api/notes/route.ts` | `POST` trusts the `userId` in the body, so anyone can write notes as anyone. | Use the session user. |
| P2P-03 | critical | `src/app/notes/page.tsx` | "Auth" is a `localStorage` check in the browser only. | Server-side session check; redirect from the server. |
| P2P-04 | critical | `src/app/api/signup`, `login` | Passwords stored and compared in **plain text**. | Hash with bcrypt/argon2. |
| P2P-05 | high | `src/app/api/signup/route.ts` | Logs the user's password with `console.log`. | Remove; structured logging without secrets. |
| P2P-06 | critical | `src/lib/auth.ts` | Session secret hard-coded in source. | Read from env var backed by Secrets Manager. |
| P2P-07 | critical | `src/lib/db.ts` | Database URL with password hard-coded as a fallback. | Require `DATABASE_URL`; fail fast if missing. |
| P2P-08 | high | `src/lib/auth.ts` | Sessions kept in an in-memory `Map`: lost on restart, and broken as soon as there is more than one container. | Signed stateless cookies (or a shared store). |
| P2P-09 | high | `src/lib/db.ts` | New `PrismaClient` on every request: exhausts database connections under load. | Single shared client; connection limit / pooling. |
| P2P-10 | medium | app | Session cookie set without `httpOnly`, `secure`, `sameSite`. | Set secure cookie flags. |
| P2P-11 | medium | `package.json` | `start` runs `prisma db push`, which can drop data and races across instances. | Versioned migrations (`prisma migrate deploy`) run once per deploy. |
| P2P-12 | medium | app | No health-check endpoint for the load balancer. | `GET /api/health` (and DB readiness check). |
| P2P-13 | medium | app | No input validation on any endpoint. | Validate request bodies (e.g. zod). |
| P2P-14 | low | repo | No Dockerfile. | Multi-stage Dockerfile, non-root user, `next` standalone output. |
| P2P-15 | low | `docker-compose.yml` | Database password committed in compose file. | Acceptable for local dev only; must not reach production config. |
| P2P-16 | high | `package.json` | `next@15.3.1` has a published security advisory (CVE-2025-66478). | Upgrade to a patched version; dependency audit in CI. |
