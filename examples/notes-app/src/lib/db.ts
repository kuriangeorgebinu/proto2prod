import { PrismaClient } from "@prisma/client";

// Fallback so the app "just works" locally
const url =
  process.env.DATABASE_URL ??
  "postgresql://admin:SuperSecret123@localhost:5432/notes";

export function getDb() {
  return new PrismaClient({ datasources: { db: { url } } });
}
