export async function sendChat(message: string) {
  const res = await fetch('/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  })

  return res.json()
}

export function connectWebSocket(onMessage: (data: any) => void) {
  const ws = new WebSocket('ws://localhost:5173/ws')

  ws.onmessage = (event) => {
    onMessage(JSON.parse(event.data))
  }

  return ws
}