// Small shared pieces: status badge, review-reason chips and number masking.

const BADGE_CLASS = {
  VERIFIED: "badge-ok",
  APPROVED: "badge-ok",
  NEEDS_REVIEW: "badge-warn",
  REJECTED: "badge-danger",
};

export function statusLabel(t, status) {
  return t.statuses[status] ?? status;
}

export function StatusBadge({ t, status }) {
  return <span className={`badge ${BADGE_CLASS[status] ?? "badge-warn"}`}>{statusLabel(t, status)}</span>;
}

export function FlagChips({ t, flags }) {
  if (!flags?.length) return null;
  return (
    <ul className="flags" aria-label={t.flagsTitle}>
      {flags.map((code) => (
        <li key={code} className="flag">
          {t.flags[code] ?? code}
        </li>
      ))}
    </ul>
  );
}

/** Show only the last 3 characters of a document number in lists (privacy by default). */
export function maskNumber(value) {
  if (!value || value.length <= 3) return value ?? "";
  return "•".repeat(value.length - 3) + value.slice(-3);
}
