import { useCallback, useEffect, useState } from "react";
import { adminOverview } from "../../api.js";

const STATUS_ORDER = ["VERIFIED", "APPROVED", "NEEDS_REVIEW", "REJECTED", "ERASED"];

function shortDay(isoDate, lang) {
  // The API sends UTC calendar days ("2026-11-02"): format them as UTC so they never shift to the previous day.
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(lang, { weekday: "short", day: "numeric", timeZone: "UTC" });
}

/** Statistics: totals by status (cards and a distribution bar) and registrations of the last 7 days. */
export default function Overview({ t, lang, adminKey, onFailure, onOpenRecords }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await adminOverview(adminKey));
    } catch (failure) {
      setError(onFailure(failure));
    } finally {
      setLoading(false);
    }
  }, [adminKey, onFailure]);

  useEffect(() => {
    load();
  }, [load]);

  if (!data) {
    return error ? (
      <p className="alert" role="alert">
        {error}
      </p>
    ) : (
      <p className="muted">{t.reviewLoading}</p>
    );
  }

  const { stats, last_days: days } = data;
  const counts = {
    VERIFIED: stats.verified,
    APPROVED: stats.approved,
    NEEDS_REVIEW: stats.needs_review,
    REJECTED: stats.rejected,
    ERASED: stats.erased,
  };
  const maxDay = Math.max(1, ...days.map((day) => day.total));

  return (
    <>
      <div className="stat-cards">
        <Card label={t.statTotal} value={stats.total} onClick={() => onOpenRecords("")} />
        <Card label={t.statVerified} value={stats.verified} onClick={() => onOpenRecords("VERIFIED")} />
        <Card
          label={t.statPending}
          value={stats.needs_review}
          attention={stats.needs_review > 0}
          onClick={() => onOpenRecords("NEEDS_REVIEW")}
        />
        <Card label={t.statApproved} value={stats.approved} onClick={() => onOpenRecords("APPROVED")} />
        <Card label={t.statRejected} value={stats.rejected} onClick={() => onOpenRecords("REJECTED")} />
        <Card label={t.statErased} value={stats.erased} onClick={() => onOpenRecords("ERASED")} />
        <Card label={t.statConfidence} value={`${stats.avg_confidence.toFixed(1)}%`} />
      </div>

      <div className="panels">
        <section className="card" aria-labelledby="dist-title">
          <h3 id="dist-title" className="card-title">
            {t.distributionTitle}
          </h3>
          <div className="distribution" role="img" aria-label={t.distributionTitle}>
            {STATUS_ORDER.filter((status) => counts[status] > 0).map((status) => (
              <span key={status} className={`seg-${status}`} style={{ width: `${(counts[status] / stats.total) * 100}%` }} />
            ))}
          </div>
          <ul className="legend">
            {STATUS_ORDER.map((status) => (
              <li key={status}>
                <span className={`swatch swatch-${status}`} aria-hidden="true" />
                {t.statuses[status]}
                <span className="count">{counts[status]}</span>
              </li>
            ))}
          </ul>
        </section>

        <section className="card" aria-labelledby="days-title">
          <h3 id="days-title" className="card-title">
            {t.chartTitle}
          </h3>
          <ul className="bars">
            {days.map((day) => (
              <li key={day.day} className="bar">
                <span className="bar-value">{day.total}</span>
                <span className="bar-fill" style={{ height: `${(day.total / maxDay) * 100}%` }} />
                <span className="bar-label">{shortDay(day.day, lang)}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <p>
        <button type="button" className="button button-secondary button-compact" onClick={load} disabled={loading}>
          {loading ? t.reviewLoading : t.reviewRefresh}
        </button>
      </p>
    </>
  );
}

function Card({ label, value, onClick, attention = false }) {
  const content = (
    <>
      <span className="stat-value">{value}</span>
      <span className="stat-label">{label}</span>
    </>
  );
  const className = `stat-card${attention ? " stat-attention" : ""}`;
  return onClick ? (
    <button type="button" className={className} onClick={onClick}>
      {content}
    </button>
  ) : (
    <div className={className}>{content}</div>
  );
}
