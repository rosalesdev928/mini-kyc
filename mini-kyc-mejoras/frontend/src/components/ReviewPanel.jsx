import { useCallback, useEffect, useState } from "react";
import { listPendingReviews, reviewRecord } from "../api.js";
import { errorMessage } from "../i18n.js";
import { FlagChips } from "./common.jsx";

const KEY_STORAGE = "reviewKey";
const NAME_STORAGE = "reviewerName";

function readStored(name, fallback = "") {
  try {
    return window.sessionStorage.getItem(name) ?? fallback;
  } catch {
    return fallback; // storage can be blocked (private mode)
  }
}

function writeStored(name, value) {
  try {
    window.sessionStorage.setItem(name, value);
  } catch {
    // ignore: the value just will not survive a reload
  }
}

/** Operator screen: records flagged NEEDS_REVIEW, with approve / reject. Protected with a shared key. */
export default function ReviewPanel({ t, lang }) {
  const [key, setKey] = useState(() => readStored(KEY_STORAGE));
  const [keyDraft, setKeyDraft] = useState("");
  const [reviewer, setReviewer] = useState(() => readStored(NAME_STORAGE, "operator"));
  const [records, setRecords] = useState(null); // null = not loaded yet
  const [comments, setComments] = useState({});
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = useCallback(
    async (activeKey) => {
      setLoading(true);
      setError(null);
      try {
        setRecords(await listPendingReviews(activeKey));
      } catch (failure) {
        setRecords(null);
        if (failure.code === "UNAUTHORIZED") {
          setKey("");
          writeStored(KEY_STORAGE, "");
        }
        setError(errorMessage(lang, failure.code, failure.message));
      } finally {
        setLoading(false);
      }
    },
    [lang],
  );

  useEffect(() => {
    if (key) load(key);
  }, [key, load]);

  function signIn(event) {
    event.preventDefault();
    const value = keyDraft.trim();
    if (!value) return;
    writeStored(KEY_STORAGE, value);
    setKey(value);
    setKeyDraft("");
  }

  function signOut() {
    writeStored(KEY_STORAGE, "");
    setKey("");
    setRecords(null);
    setNotice(null);
  }

  async function decide(record, decision) {
    setBusyId(record.id);
    setError(null);
    setNotice(null);
    const name = reviewer.trim() || "operator";
    writeStored(NAME_STORAGE, name);
    try {
      await reviewRecord(key, record.id, { decision, reviewer: name, comment: comments[record.id] });
      setRecords((current) => current.filter((item) => item.id !== record.id));
      setNotice(`#${record.id} · ${decision === "APPROVED" ? t.statuses.APPROVED : t.statuses.REJECTED}`);
    } catch (failure) {
      setError(errorMessage(lang, failure.code, failure.message));
      if (failure.code === "NOT_PENDING_REVIEW") load(key); // someone else already decided: refresh
    } finally {
      setBusyId(null);
    }
  }

  if (!key) {
    return (
      <section className="card review-card" aria-labelledby="review-title">
        <h2 id="review-title" className="card-title">
          {t.reviewTitle}
        </h2>
        <p className="muted">{t.reviewLocked}</p>
        <form onSubmit={signIn} noValidate>
          <label className="field-label" htmlFor="review-key">
            {t.reviewKey}
          </label>
          <input
            id="review-key"
            type="password"
            className="input"
            value={keyDraft}
            autoComplete="off"
            onChange={(event) => setKeyDraft(event.target.value)}
          />
          {error && (
            <p className="alert" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="button">
            {t.reviewEnter}
          </button>
        </form>
      </section>
    );
  }

  return (
    <section className="card review-card" aria-labelledby="review-title">
      <div className="card-heading review-heading">
        <h2 id="review-title" className="card-title">
          {t.reviewTitle}
        </h2>
        <div className="review-actions">
          <button type="button" className="button button-secondary" onClick={() => load(key)} disabled={loading}>
            {loading ? t.reviewLoading : t.reviewRefresh}
          </button>
          <button type="button" className="button button-secondary" onClick={signOut}>
            {t.reviewExit}
          </button>
        </div>
      </div>

      <label className="field-label" htmlFor="reviewer-name">
        {t.reviewerName}
      </label>
      <input
        id="reviewer-name"
        className="input reviewer-input"
        value={reviewer}
        maxLength={100}
        onChange={(event) => setReviewer(event.target.value)}
      />

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}

      {records && records.length === 0 && <p className="placeholder muted">{t.reviewEmpty}</p>}

      <ul className="review-list">
        {(records ?? []).map((record) => (
          <li key={record.id} className="review-item">
            <div className="review-item-head">
              <strong>
                #{record.id} · {record.full_name}
              </strong>
              <span className="muted small">{new Date(record.created_at).toLocaleString(lang)}</span>
            </div>
            <dl className="review-fields">
              <div>
                <dt>{t.email}</dt>
                <dd>{record.email}</dd>
              </div>
              <div>
                <dt>{t.documentType}</dt>
                <dd>
                  {record.document_type} · {record.document_number}
                </dd>
              </div>
              <div>
                <dt>{t.confidence}</dt>
                <dd>{record.ocr_confidence.toFixed(1)}%</dd>
              </div>
            </dl>
            <FlagChips t={t} flags={record.flags} />
            <input
              className="input"
              placeholder={t.reviewComment}
              aria-label={t.reviewComment}
              maxLength={500}
              value={comments[record.id] ?? ""}
              onChange={(event) => setComments((current) => ({ ...current, [record.id]: event.target.value }))}
            />
            <div className="review-buttons">
              <button
                type="button"
                className="button button-approve"
                disabled={busyId === record.id}
                onClick={() => decide(record, "APPROVED")}
              >
                {t.reviewApprove}
              </button>
              <button
                type="button"
                className="button button-reject"
                disabled={busyId === record.id}
                onClick={() => decide(record, "REJECTED")}
              >
                {t.reviewReject}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
