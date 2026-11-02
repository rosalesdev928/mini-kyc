export default function ResultPanel({ t, lang, status, result, previewUrl, onReset }) {
  return (
    <section className="card result-card" aria-live="polite" aria-labelledby="result-title">
      <div className="card-heading">
        <h2 id="result-title" className="card-title">
          {t.extractedTitle}
        </h2>
        {status === "success" && result && (
          <span className={`badge ${result.status === "VERIFIED" ? "badge-ok" : "badge-warn"}`}>
            {result.status === "VERIFIED" ? t.verified : t.needsReview}
          </span>
        )}
      </div>

      {status === "loading" && (
        <div className="placeholder">
          <span className="spinner spinner-large" aria-hidden="true" />
          <p>{t.loadingText}</p>
        </div>
      )}

      {(status === "idle" || status === "error") && (
        <div className="placeholder">
          <p className="placeholder-title">{t.idleTitle}</p>
          <p className="muted">{t.idleText}</p>
        </div>
      )}

      {status === "success" && result && (
        <>
          <div className="result-grid">
            {previewUrl ? (
              <img className="preview" src={previewUrl} alt={t.imageAlt} />
            ) : (
              <div className="preview preview-empty">{t.imageAlt}</div>
            )}
            <dl className="fields">
              <div>
                <dt>{t.fullName}</dt>
                <dd>{result.full_name}</dd>
              </div>
              <div>
                <dt>{t.documentType}</dt>
                <dd>{result.document_type}</dd>
              </div>
              <div>
                <dt>{t.documentNumber}</dt>
                <dd>{result.document_number}</dd>
              </div>
              <div>
                <dt>{t.confidence}</dt>
                <dd>{result.ocr_confidence.toFixed(1)}%</dd>
              </div>
              <div>
                <dt>{t.registered}</dt>
                <dd>{new Date(result.created_at).toLocaleString(lang)}</dd>
              </div>
            </dl>
          </div>

          <p className="note">{result.status === "VERIFIED" ? t.aiNote : t.reviewNote}</p>
          <button type="button" className="button button-secondary" onClick={onReset}>
            {t.tryAnother}
          </button>
        </>
      )}
    </section>
  );
}
