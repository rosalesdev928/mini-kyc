import { useEffect, useRef, useState } from "react";
import { askChatbot } from "../api.js";

export default function ChatWidget({ t }) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, open]);

  async function send(question) {
    const text = question.trim();
    if (!text || sending) return;
    setMessages((current) => [...current, { role: "user", text }]);
    setDraft("");
    setSending(true);
    try {
      const response = await askChatbot(text);
      setMessages((current) => [...current, { role: "bot", text: response.answer }]);
    } catch {
      setMessages((current) => [...current, { role: "bot", text: t.chatError }]);
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="chat-launcher" onClick={() => setOpen(true)}>
        {t.chatOpen}
      </button>
    );
  }

  return (
    <aside className="chat" aria-label={t.chatTitle}>
      <header className="chat-header">
        <strong>{t.chatTitle}</strong>
        <button type="button" className="chat-close" onClick={() => setOpen(false)} aria-label={t.chatClose}>
          ×
        </button>
      </header>

      <div className="chat-messages" ref={listRef}>
        <p className="bubble bubble-bot">{t.chatWelcome}</p>
        {messages.length === 0 && (
          <div className="chips">
            {t.chatSuggestions.map((suggestion) => (
              <button key={suggestion} type="button" className="chip" onClick={() => send(suggestion)}>
                {suggestion}
              </button>
            ))}
          </div>
        )}
        {messages.map((message, index) => (
          <p key={index} className={`bubble ${message.role === "user" ? "bubble-user" : "bubble-bot"}`}>
            {message.text}
          </p>
        ))}
        {sending && <p className="bubble bubble-bot">…</p>}
      </div>

      <form
        className="chat-form"
        onSubmit={(event) => {
          event.preventDefault();
          send(draft);
        }}
      >
        <input
          className="input"
          value={draft}
          maxLength={500}
          placeholder={t.chatPlaceholder}
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" className="button chat-send" disabled={sending || draft.trim().length < 2}>
          {t.chatSend}
        </button>
      </form>
    </aside>
  );
}
