import ReactMarkdown from "react-markdown";

export default function IncidentCard({ incident }: { incident: any }) {
  return (
    <div className="incident-card">
      <div className="incident-header">
        <strong>{incident.category}</strong>
        <span className={`status ${incident.analysis_status}`}>
          {incident.analysis_status}
        </span>
      </div>

      {incident.analysis_status === "PENDING" && (
        <p className="thinking">🔄 DevOps AI is analyzing…</p>
      )}

      {incident.analysis_status === "COMPLETE" && (
        <>
          <ReactMarkdown>{incident.raw_output}</ReactMarkdown>

          {incident.recommendations?.length > 0 && (
            <ul className="recommendations">
              {incident.recommendations.map((r: string, i: number) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}