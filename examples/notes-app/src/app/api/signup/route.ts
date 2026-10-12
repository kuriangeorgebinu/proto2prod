import { NextResponse } from "next/server";
import { getDb } from "@/lib/db";
import { createSession } from "@/lib/auth";

export async function POST(req: Request) {
  const { email, password } = await req.json();
  console.log("signup", email, password);

  const db = getDb();
  const user = await db.user.create({ data: { email, password } });

  const res = NextResponse.json({ userId: user.id });
  res.cookies.set("sid", createSession(user.id));
  return res;
}
