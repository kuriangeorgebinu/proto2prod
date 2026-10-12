import crypto from "crypto";

const SESSION_SECRET = "notes-app-session-secret-2024";

// sessionId -> userId
const sessions = new Map<string, string>();

export function createSession(userId: string) {
  const id = crypto
    .createHmac("sha256", SESSION_SECRET)
    .update(userId + Date.now())
    .digest("hex");
  sessions.set(id, userId);
  return id;
}

export function getUserId(sessionId: string | undefined) {
  if (!sessionId) return null;
  return sessions.get(sessionId) ?? null;
}
