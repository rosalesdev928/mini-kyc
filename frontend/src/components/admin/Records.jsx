import { useCallback, useEffect, useRef, useState } from "react";
import { adminExportCsv, adminSearch } from "../../api.js";
import { StatusBadge, maskNumber } from "../common.jsx";
import RecordDetail from "./RecordDetail.jsx";

const PAGE_SIZE = 20;
const STATUS_OPTIONS = ["VERIFIED", "NEEDS_REVIEW", "APPROVED", "REJECTED", "ERASED"];

/** Searchable, filterable, paginated list of every record, with CSV export and a detail dialog. */
export default function Records({ t, lang, adminKey, reviewer, initialStatus, onFailure }) {
  const [draft, setDraft] = useState({ status: initialStatus, q: "", dateFrom: "", dateTo: "" });
  const [applied, setApplied] = useState({ status: initialStatus, q: "", dateFrom: "", dateTo: "" });
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState(null); // { items, total }
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [exporting, setExporting] = useState(false);
  const latestRequest = useRef(0);

  const load = useCallback(async () => {
    const request = ++latestRequest.current;
    setLoading(true);
    setError(null);
    try {
      const result = await adminSearch(adminKey, applied, { limit: PAGE_SIZE, offset });
      if (request === latestRequest.current) setPage(result); // ignore answers of outdated requests
    } catch (failure) {
      if (request === latestRequest.current) setError(onFailure(failure));
    } finally {
      if (request === latestRequest.current) setLoading(false);
    }
  }, [adminKey, applied, offset, onFailure]);

  useEffect(() => {
    load();
  }, [load]);

  function update(field, value) {
    setDraft((current) => ({ ...current, [field]: value }));
  }

  function apply(event) {
    event?.preventDefault();
    setOffset(0);
    setApplied({ ...draft, q: draft.q.trim() });
  }

  function clear() {
    const empty = { status: "", q: "", dateFrom: "", dateTo: "" };
    setDraft(empty);
    setOffset(0);
    setApplied(empty);
  }

  async function exportCsv() {
    setExporting(true);
    setError(null);
    try {
      await adminExportCsv(adminKey, applied);
    } catch (failure) {
      setError(onFailure(failure));
    } finally {
      setExporting(false);
    }
  }

  const total = page?.total ?? 0;
  const items = page?.items ?? [];
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, total);
  const range = t.pageRange.replace("{from}", from).replace("{to}", to).replace("{total}", total);

  return (
    <section className="card" aria-labelledby="records-title">
      <h3 id="records-title" className="card-title">
        {t.tabRecords}
      </h3>

      <form className="filters" onSubmit={apply}>
        <div>
          <label className="field-label" htmlFor="f-status">
            {t.filterStatus}
          </label>
          <select
            id="f-status"
            className="input"
            value={draft.status}
            onChange={(event) => {
              update("status", event.target.value);
              setOffset(0);
              setApplied((current) => ({ ...current, status: event.target.value }));
            }}
          >
            <option value="">{t.filterAll}</option>
            {STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {t.statuses[status]}
              </option>
            ))}
          </select>
        </div>
        <div className="filters-wide">
          <label className="field-label" htmlFor="f-q">
            {t.filterSearch}
          </label>
          <input
            id="f-q"
            className="input"
            value={draft.q}
            maxLength={100}
            placeholder={t.filterSearchPlaceholder}
            onChange={(event) => update("q", event.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="f-from">
            {t.filterFrom}
          </label>
          <input
            id="f-from"
            type="date"
            className="input"
            value={draft.dateFrom}
            onChange={(event) => update("dateFrom", event.target.value)}
          />
        </div>
        <div>
          <label className="field-label" htmlFor="f-to">
            {t.filterTo}
          </label>
          <input
            id="f-to"
            type="date"
            className="input"
            value={draft.dateTo}
            onChange={(event) => update("dateTo", event.target.value)}
          />
        </div>
        <div className="filter-buttons">
          <button type="submit" className="button button-compact">
            {t.filterApply}
          </button>
          <button type="button" className="button button-secondary button-compact" onClick={clear}>
            {t.filterClear}
          </button>
          <button
            type="button"
            className="button button-secondary button-compact"
            onClick={exportCsv}
            disabled={exporting || total === 0}
          >
            {exporting ? t.reviewLoading : t.exportCsv}
          </button>
        </div>
      </form>

      {error && (
        <p className="alert" role="alert">
          {error}
        </p>
      )}

      {page && items.length === 0 && !loading && <p className="placeholder muted">{t.noRecords}</p>}

      {items.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t.colId}</th>
                <th scope="col">{t.colDate}</th>
                <th scope="col">{t.colEmail}</th>
                <th scope="col">{t.colName}</th>
                <th scope="col">{t.colDocument}</th>
                <th scope="col">{t.colConfidence}</th>
                <th scope="col">{t.colStatus}</th>
                <th scope="col">
                  <span className="visually-hidden">{t.viewRecord}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((record) => (
                <tr
                  key={record.id}
                  className="table-row"
                  tabIndex={0}
                  onClick={() => setSelectedId(record.id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") setSelectedId(record.id);
                  }}
                >
                  <td>{record.id}</td>
                  <td>{new Date(record.created_at).toLocaleString(lang)}</td>
                  <td className="cell-wrap">{record.email}</td>
                  <td className="cell-wrap">{record.full_name}</td>
                  <td>
                    {record.document_type} {maskNumber(record.document_number)}
                  </td>
                  <td>{record.ocr_confidence.toFixed(1)}%</td>
                  <td>
                    <StatusBadge t={t} status={record.status} />
                  </td>
                  <td>
                    <button type="button" className="link-button" onClick={() => setSelectedId(record.id)}>
                      {t.viewRecord}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="pager">
        <span className="muted small" aria-live="polite">
          {loading ? t.reviewLoading : range}
        </span>
        <div className="pager-buttons">
          <button
            type="button"
            className="button button-secondary button-compact"
            disabled={loading || offset === 0}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            {t.pagePrev}
          </button>
          <button
            type="button"
            className="button button-secondary button-compact"
            disabled={loading || offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            {t.pageNext}
          </button>
        </div>
      </div>

      {selectedId !== null && (
        <RecordDetail
          t={t}
          lang={lang}
          adminKey={adminKey}
          id={selectedId}
          reviewer={reviewer}
          onFailure={onFailure}
          onChanged={load}
          onClose={() => setSelectedId(null)}
        />
      )}
    </section>
  );
}
