import { useCallback, useEffect, useRef, useState } from "react";
import { adminAnonymize, adminDetail, reviewRecord } from "../../api.js";
import { ConfidenceMeter, FlagChips, StatusBadge } from "../common.jsx";

/** Dialog with one record: data, audit trail and the actions an operator can take (approve / reject / erase). */
export default function RecordDetail({ t, lang, adminKey, id, reviewer, onFailure, onChanged, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [comment, setComment] = useState("");
  const [reason, setReason] = useState("");
  const [confirmErase, setConfirmErase] = useState(false);
  const closeRef = useRef(null);

  const reload = useCallback(async () => {
    try {
      setDetail(await adminDetail(adminKey, id));
    } catch (failure) {
      setError(onFailure(failure));
    }
  }, [adminKey, id, onFailure]);

  useEffect(() => {
    reload();
  }, [reload]);

  useEffect(() => {
    closeRef.current?.focus();
    function onKey(event) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const name = reviewer.trim() || "operator";

  async function run(action) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await reload();
      onChanged();
    } catch (failure) {
      setError(onFailure(failure));
      if (failure.code === "NOT_PENDING_REVIEW" || failure.code === "CONFLICT") {
        await reload();
        onChanged();
      }
    } finally {
      setBusy(false);
    }
  }

  const decide = (decision) => run(() => reviewRecord(adminKey, id, { decision, reviewer: name, comment }));
  const erase = () =>
    run(async () => {
      await adminAnonymize(adminKey, id, { reviewer: name, reason });
      setConfirmErase(false);
      setReason("");
    });

  const record = detail?.record;

  return (
    <div
      className="modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="detail-title">
        <div className="modal-head">
          <h2 id="detail-title">{t.detailTitle.replace("{id}", id)}</h2>
          <button ref={closeRef} type="button" className="modal-close" aria-label={t.close} onClick={onClose}>
            ×
          </button>
        </div>

        {error && (
          <p className="alert" role="alert">
            {error}
          </p>
        )}
        {!record && !error && <p className="muted">{t.reviewLoading}</p>}

        {record && (
          <>
            <p>
              <StatusBadge t={t} status={record.status} />
            </p>
            <dl className="detail-grid">
              <div>
                <dt>{t.fullName}</dt>
                <dd>{record.full_name}</dd>
              </div>
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
                <dd>
                  <ConfidenceMeter t={t} value={record.ocr_confidence} />
                </dd>
              </div>
              <div>
                <dt>{t.registered}</dt>
                <dd>{new Date(record.created_at).toLocaleString(lang)}</dd>
              </div>
              {record.original_filename && (
                <div>
                  <dt>{t.fileName}</dt>
                  <dd>{record.original_filename}</dd>
                </div>
              )}
            </dl>
            <FlagChips t={t} flags={record.flags} />

            <h3 className="section-title">{t.timelineTitle}</h3>
            <ol className="timeline">
              {detail.events.map((event, index) => (
                <li key={`${event.event_type}-${index}`}>
                  <strong>{t.events[event.event_type] ?? event.event_type}</strong>
                  {event.actor && <span> · {event.actor}</span>}
                  {event.detail && <span className="muted"> · {t.flags[event.detail] ?? t.statuses[event.detail] ?? event.detail}</span>}
                  <span className="when">{new Date(event.occurred_at).toLocaleString(lang)}</span>
                </li>
              ))}
            </ol>

            {record.status === "NEEDS_REVIEW" && (
              <div className="action-box">
                <h3>{t.reviewActionTitle}</h3>
                <input
                  className="input"
                  placeholder={t.reviewComment}
                  aria-label={t.reviewComment}
                  maxLength={500}
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                />
                <div className="action-buttons">
                  <button
                    type="button"
                    className="button button-approve button-compact"
                    disabled={busy}
                    onClick={() => decide("APPROVED")}
                  >
                    {t.reviewApprove}
                  </button>
                  <button
                    type="button"
                    className="button button-reject button-compact"
                    disabled={busy}
                    onClick={() => decide("REJECTED")}
                  >
                    {t.reviewReject}
                  </button>
                </div>
              </div>
            )}

            {record.status === "ERASED" ? (
              <p className="note">{t.erasedNote}</p>
            ) : (
              <div className="action-box action-box-danger">
                <h3>{t.eraseTitle}</h3>
                <p>{t.eraseText}</p>
                <input
                  className="input"
                  placeholder={t.eraseReason}
                  aria-label={t.eraseReason}
                  maxLength={200}
                  value={reason}
                  onChange={(event) => setReason(event.target.value)}
                />
                <label className="check-row">
                  <input
                    type="checkbox"
                    checked={confirmErase}
                    onChange={(event) => setConfirmErase(event.target.checked)}
                  />
                  {t.eraseConfirm}
                </label>
                <div className="action-buttons">
                  <button
                    type="button"
                    className="button button-danger button-compact"
                    disabled={busy || !confirmErase}
                    onClick={erase}
                  >
                    {t.eraseButton}
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
