import { useEffect, useState } from 'react'
import { sendChat, connectWebSocket } from './api'

function App() {
  const [input, setInput] = useState('')
  const [incidents, setIncidents] = useState<any[]>([])

  useEffect(() => {
    connectWebSocket((update) => {
      setIncidents((prev) =>
        prev.map((i) =>
          i.incident_id === update.incident_id ? update : i
        )
      )
    })
  }, [])

  const send = async () => {
    const res = await sendChat(input)
    setIncidents((prev) => [res, ...prev])
    setInput('')
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>DevOps AI – SRE Dashboard</h2>

      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder="Ask DevOps AI..."
      />
      <button onClick={send}>Send</button>

      <hr />

      {incidents.map((inc) => (
        <div key={inc.incident_id} style={{ border: '1px solid #ccc', margin: 10, padding: 10 }}>
          <h4>{inc.summary}</h4>

          {inc.analysis_status === 'PENDING' && (
            <p>🔄 Analyzing root cause...</p>
          )}

          {inc.analysis_status === 'COMPLETE' && (
            <pre>{inc.raw_output}</pre>
          )}
        </div>
      ))}
    </div>
  )
}

export default App