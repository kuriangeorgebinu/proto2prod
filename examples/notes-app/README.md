# notes-app (sample prototype)

A tiny notes app (sign up, log in, write notes) built with Next.js 15 and Postgres via Prisma, written the way AI app builders typically write a first version.

It is the test subject for proto2prod. See [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for the planted production problems the agents should find and fix.

## Run locally

```bash
docker compose up -d   # starts Postgres
npm install
npm run build
npm start              # http://localhost:3000
```
