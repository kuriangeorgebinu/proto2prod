"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

type Note = { id: string; title: string; body: string };

export default function NotesPage() {
  const router = useRouter();
  const [notes, setNotes] = useState<Note[]>([]);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    const id = localStorage.getItem("userId");
    if (!id) return router.push("/"); // "auth" check
    setUserId(id);
    fetch(`/api/notes?userId=${id}`).then((r) => r.json()).then(setNotes);
  }, [router]);

  async function add() {
    const res = await fetch("/api/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId, title, body }),
    });
    const note = await res.json();
    setNotes([note, ...notes]);
    setTitle("");
    setBody("");
  }

  return (
    <main>
      <h1>My notes</h1>
      <input placeholder="Title" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea placeholder="Write something" value={body} onChange={(e) => setBody(e.target.value)} />
      <button onClick={add}>Add note</button>
      <ul>
        {notes.map((n) => (
          <li key={n.id}><strong>{n.title}</strong> – {n.body}</li>
        ))}
      </ul>
    </main>
  );
}
