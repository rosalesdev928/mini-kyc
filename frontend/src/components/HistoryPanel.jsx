import { StatusBadge, maskNumber } from "./common.jsx";

/** Recent registrations of the email that was just used (document numbers are masked). */
export default function HistoryPanel({ t, lang, email, records }) {
  if (!records.length) return null;
  return (
    <section className="card history" aria-labelledby="history-title">
      <h2 id="history-title" className="card-title">
        {t.historyTitle}
      </h2>
      <p className="muted small history-email">{email}</p>
      <ul className="history-list">
        {records.map((record) => (
          <li key={record.id} className="history-item">
            <div>
              <strong>{record.full_name}</strong>
              <span className="muted small">
                {record.document_type} {maskNumber(record.document_number)} ·{" "}
                {new Date(record.created_at).toLocaleString(lang)}
              </span>
            </div>
            <StatusBadge t={t} status={record.status} />
          </li>
        ))}
      </ul>
    </section>
  );
}
