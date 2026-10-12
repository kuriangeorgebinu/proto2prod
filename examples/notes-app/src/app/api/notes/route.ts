import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";

// The notes page only calls this once the user is logged in,
// and it passes the logged-in user's id.
export async function GET(req: Request) {
  const userId = new URL(req.url).searchParams.get("userId");
  const db = getDb();
  const notes = await db.note.findMany({
    where: userId ? { userId } : {},
    orderBy: { createdAt: "desc" },
  });
  return NextResponse.json(notes);
}

export async function POST(req: Request) {
  const { userId, title, body } = await req.json();
  const db = getDb();
  const note = await db.note.create({ data: { userId, title, body } });
  return NextResponse.json(note);
}
