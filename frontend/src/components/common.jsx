// Small shared pieces: status badge, review-reason chips, confidence meter and number masking.

const BADGE_CLASS = {
  VERIFIED: "badge-ok",
  APPROVED: "badge-ok",
  NEEDS_REVIEW: "badge-warn",
  REJECTED: "badge-danger",
  ERASED: "badge-muted",
};

// Same default as the backend (MIN_VERIFIED_CONFIDENCE = 0.85): below it the record goes to manual review.
const CONFIDENCE_THRESHOLD = 85;

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

/** A small bar plus the number. Green at or above the review threshold, amber below it. */
export function ConfidenceMeter({ t, value }) {
  const percent = Math.max(0, Math.min(100, value));
  return (
    <span className="meter">
      <span
        className="meter-track"
        role="meter"
        aria-label={t.confidence}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(percent)}
      >
        <span
          className={`meter-fill${percent < CONFIDENCE_THRESHOLD ? " meter-fill-low" : ""}`}
          style={{ width: `${percent}%` }}
        />
      </span>
      <span>{percent.toFixed(1)}%</span>
    </span>
  );
}

/** Show only the last 3 characters of a document number in lists (privacy by default). */
export function maskNumber(value) {
  if (!value || value.length <= 3) return value ?? "";
  return "•".repeat(value.length - 3) + value.slice(-3);
}
