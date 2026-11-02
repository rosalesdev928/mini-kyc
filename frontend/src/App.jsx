import { useCallback, useEffect, useState } from "react";
import { createOnboarding, listByEmail } from "./api.js";
import { errorMessage, messages } from "./i18n.js";
import UploadPanel from "./components/UploadPanel.jsx";
import ResultPanel from "./components/ResultPanel.jsx";
import ChatWidget from "./components/ChatWidget.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import ReviewPanel from "./components/ReviewPanel.jsx";
import ServerBanner from "./components/ServerBanner.jsx";

const SLOW_AFTER_MS = 10000; // after this the UI explains that the AI is busy and retrying

export default function App() {
  const [lang, setLang] = useState("en");
  const [status, setStatus] = useState("idle"); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [errorState, setErrorState] = useState(null); // { code, message }
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [view, setView] = useState("onboarding"); // onboarding | operator
  const [slow, setSlow] = useState(false);
  const [history, setHistory] = useState({ email: "", records: [] });

  const t = messages[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  useEffect(() => {
    if (status !== "loading") {
      setSlow(false);
      return undefined;
    }
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, [status]);

  // Build (and always release) an object URL for the selected image.
  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFileChange = useCallback((selected) => {
    setFile(selected);
    setErrorState(null);
    setStatus((current) => (current === "success" ? "idle" : current));
  }, []);

  async function handleSubmit({ email, file: selected }) {
    setStatus("loading");
    setErrorState(null);
    setResult(null);
    try {
      const record = await createOnboarding({ email, file: selected });
      setResult(record);
      setStatus("success");
      loadHistory(record.email);
    } catch (error) {
      setErrorState({ code: error.code, message: error.message });
      setStatus("error");
    }
  }

  async function loadHistory(email) {
    try {
      const records = await listByEmail(email);
      setHistory({ email, records: records.slice(0, 5) });
    } catch {
      setHistory({ email, records: [] }); // the history is a nicety: never block the main flow
    }
  }

  function handleReset() {
    setStatus("idle");
    setResult(null);
    setErrorState(null);
  }

  const error = errorState ? errorMessage(lang, errorState.code, errorState.message) : null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <span className="brand-name">{t.appName}</span>
        </div>
        <div className="topbar-actions">
          <button type="button" className="lang-toggle" onClick={() => setLang(lang === "en" ? "es" : "en")}>
            {t.lang}
          </button>
          <button
            type="button"
            className="operator"
            aria-pressed={view === "operator"}
            onClick={() => setView(view === "operator" ? "onboarding" : "operator")}
          >
            {view === "operator" ? t.backToOnboarding : t.openOperator}
          </button>
        </div>
      </header>

      <ServerBanner t={t} />

      {view === "operator" ? (
        <main className="layout layout-single">
          <ReviewPanel t={t} lang={lang} />
        </main>
      ) : (
        <main className="layout">
          <UploadPanel
            t={t}
            loading={status === "loading"}
            error={error}
            onSubmit={handleSubmit}
            onFileChange={handleFileChange}
          />
          <div className="column">
            <ResultPanel
              t={t}
              lang={lang}
              status={status}
              result={result}
              previewUrl={previewUrl}
              slow={slow}
              onReset={handleReset}
            />
            <HistoryPanel t={t} lang={lang} email={history.email} records={history.records} />
          </div>
        </main>
      )}

      <ChatWidget t={t} />
    </div>
  );
}
