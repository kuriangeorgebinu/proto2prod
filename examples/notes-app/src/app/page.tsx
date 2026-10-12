"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(path: "login" | "signup") {
    setError("");
    const res = await fetch(`/api/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();
    if (!res.ok) return setError(data.error ?? "Something went wrong");
    localStorage.setItem("userId", data.userId);
    router.push("/notes");
  }

  return (
    <main>
      <h1>Notes</h1>
      <input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
      <input placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
      <button onClick={() => submit("login")}>Log in</button>
      <button onClick={() => submit("signup")}>Sign up</button>
      {error && <p style={{ color: "crimson" }}>{error}</p>}
    </main>
  );
}
