import IncidentCard from "./IncidentCard";
import type { ChatMessage as Msg } from "../types";

export default function ChatMessage({ message }: { message: Msg }) {
  return (
    <div className={`chat-message ${message.role}`}>
      <div className="bubble">
        {message.role === "assistant" && (
          <div className="assistant-label">DevOps AI</div>
        )}

        <div className="message-text">{message.content}</div>

        {message.incident && (
          <IncidentCard incident={message.incident} />
        )}

        <div className="timestamp">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}