import { useCallback, useState } from "react";
import { errorMessage } from "../../i18n.js";
import { readStored, writeStored } from "../../storage.js";
import Overview from "./Overview.jsx";
import Records from "./Records.jsx";

const KEY_STORAGE = "reviewKey";
const NAME_STORAGE = "reviewerName";
// Errors after which the stored key is useless: go back to the sign-in form and say why.
const SIGN_OUT_CODES = ["UNAUTHORIZED", "REVIEW_DISABLED", "TOO_MANY_REQUESTS"];

/**
 * Admin dashboard for operators: overview (statistics), records (search, review, erase, export).
 * Protected with the shared operator key, kept only in sessionStorage (it disappears when the tab closes).
 */
export default function AdminPanel({ t, lang }) {
  const [key, setKey] = useState(() => readStored("session", KEY_STORAGE));
  const [keyDraft, setKeyDraft] = useState("");
  const [loginError, setLoginError] = useState(null);
  const [reviewer, setReviewer] = useState(() => readStored("session", NAME_STORAGE, "operator"));
  const [tab, setTab] = useState("overview");
  const [statusPreset, setStatusPreset] = useState("");

  const signOut = useCallback((message) => {
    writeStored("session", KEY_STORAGE, "");
    setKey("");
    setLoginError(message ?? null);
  }, []);

  /** Children report API failures here: it signs out when the key is the problem, and returns the text to show. */
  const handleFailure = useCallback(
    (failure) => {
      const message = errorMessage(lang, failure.code, failure.message);
      if (SIGN_OUT_CODES.includes(failure.code)) signOut(message);
      return message;
    },
    [lang, signOut],
  );

  function signIn(event) {
    event.preventDefault();
    const value = keyDraft.trim();
    if (!value) return;
    writeStored("session", KEY_STORAGE, value);
    setLoginError(null);
    setKey(value);
    setKeyDraft("");
  }

  function changeReviewer(value) {
    setReviewer(value);
    writeStored("session", NAME_STORAGE, value);
  }

  function openRecords(status) {
    setStatusPreset(status);
    setTab("records");
  }

  if (!key) {
    return (
      <section className="card" aria-labelledby="admin-title">
        <h2 id="admin-title" className="card-title">
          {t.adminTitle}
        </h2>
        <p className="muted">{t.adminLocked}</p>
        <form onSubmit={signIn} noValidate>
          <label className="field-label" htmlFor="admin-key">
            {t.reviewKey}
          </label>
          <input
            id="admin-key"
            type="password"
            className="input"
            value={keyDraft}
            autoComplete="off"
            onChange={(event) => setKeyDraft(event.target.value)}
          />
          {loginError && (
            <p className="alert" role="alert">
              {loginError}
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
    <section aria-labelledby="admin-title">
      <div className="admin-head">
        <h2 id="admin-title" className="card-title">
          {t.adminTitle}
        </h2>
        <div className="admin-tools">
          <label htmlFor="reviewer-name">{t.reviewerName}</label>
          <input
            id="reviewer-name"
            className="input reviewer-input"
            value={reviewer}
            maxLength={100}
            onChange={(event) => changeReviewer(event.target.value)}
          />
          <button type="button" className="button button-secondary button-compact" onClick={() => signOut()}>
            {t.reviewExit}
          </button>
        </div>
      </div>

      <div className="tabs" role="tablist" aria-label={t.adminTitle}>
        {["overview", "records"].map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            id={`tab-${name}`}
            aria-selected={tab === name}
            aria-controls={`panel-${name}`}
            className="tab"
            onClick={() => {
              if (name === "records") setStatusPreset("");
              setTab(name);
            }}
          >
            {name === "overview" ? t.tabOverview : t.tabRecords}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "overview" ? (
          <Overview t={t} lang={lang} adminKey={key} onFailure={handleFailure} onOpenRecords={openRecords} />
        ) : (
          <Records
            key={statusPreset}
            t={t}
            lang={lang}
            adminKey={key}
            reviewer={reviewer}
            initialStatus={statusPreset}
            onFailure={handleFailure}
          />
        )}
      </div>
    </section>
  );
}
