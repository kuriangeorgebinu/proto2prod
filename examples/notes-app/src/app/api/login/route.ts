import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { createSession } from "@/lib/auth";

export async function POST(req: Request) {
  const { email, password } = await req.json();

  const db = getDb();
  const user = await db.user.findUnique({ where: { email } });
  if (!user || user.password !== password) {
    return NextResponse.json({ error: "Invalid login" }, { status: 401 });
  }

  const res = NextResponse.json({ userId: user.id });
  res.cookies.set("sid", createSession(user.id));
  return res;
}
