// src/api.ts

const API_BASE = "http://localhost:8000";

/**
 * Send a chat message to the backend
 */
export async function sendChat(message: string) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!res.ok) {
    throw new Error("Failed to send chat message");
  }

  return res.json();
}

/**
 * Connect to backend WebSocket for live RCA updates
 * Includes auto-reconnect logic (important for stability)
 */
export function connectWebSocket(
  onMessage: (data: any) => void,
  onStatus?: (status: "connected" | "disconnected") => void
) {
  let ws: WebSocket | null = null;
  let retryTimeout: number | null = null;

  const connect = () => {
    ws = new WebSocket("ws://localhost:8000/ws");

    ws.onopen = () => {
      console.log("✅ WebSocket connected");
      onStatus?.("connected");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        onMessage(data);
      } catch (err) {
        console.error("Invalid WS message", err);
      }
    };

    ws.onclose = () => {
      console.warn("⚠️ WebSocket disconnected, retrying...");
      onStatus?.("disconnected");

      retryTimeout = window.setTimeout(() => {
        connect();
      }, 3000);
    };

    ws.onerror = () => {
      ws?.close();
    };
  };

  connect();

  return {
    close: () => {
      if (retryTimeout) clearTimeout(retryTimeout);
      ws?.close();
    },
  };
}