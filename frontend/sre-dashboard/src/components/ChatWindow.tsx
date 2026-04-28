import { useEffect, useRef } from "react";
import ChatMessage from "./ChatMessage";
import type { ChatMessage as Msg } from "../types";

export default function ChatWindow({ messages }: { messages: Msg[] }) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div className="chat-window">
      {messages.length === 0 && (
        <div className="empty-state">
          <p>Ask DevOps AI things like:</p>
          <ul>
            <li>any issues?</li>
            <li>get pods</li>
            <li>why is my pod crashing?</li>
          </ul>
        </div>
      )}

      {messages.map((m) => (
        <ChatMessage key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}