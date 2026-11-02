import { useCallback, useEffect, useState } from "react";
import { createOnboarding, listByEmail } from "./api.js";
import { errorMessage, messages } from "./i18n.js";
import { writeStored } from "./storage.js";
import UploadPanel from "./components/UploadPanel.jsx";
import ResultPanel from "./components/ResultPanel.jsx";
import ChatWidget from "./components/ChatWidget.jsx";
import HistoryPanel from "./components/HistoryPanel.jsx";
import AdminPanel from "./components/admin/AdminPanel.jsx";
import Logo from "./components/Logo.jsx";
import PrivacyNotice from "./components/PrivacyNotice.jsx";
import ServerBanner from "./components/ServerBanner.jsx";

const SLOW_AFTER_MS = 10000; // after this the UI explains that the AI is busy and retrying

/** Light / dark theme. theme-init.js sets the first value before the first paint; here we only toggle and remember it. */
function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute("data-theme") || "light");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);
  const toggle = useCallback(() => {
    setTheme((current) => {
      const next = current === "dark" ? "light" : "dark";
      writeStored("local", "theme", next);
      return next;
    });
  }, []);
  return [theme, toggle];
}

export default function App() {
  const [lang, setLang] = useState("en");
  const [status, setStatus] = useState("idle"); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [errorState, setErrorState] = useState(null); // { code, message }
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [view, setView] = useState("onboarding"); // onboarding | admin
  const [theme, toggleTheme] = useTheme();
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
          <Logo />
          <span className="brand-text">
            <span className="brand-name">{t.brandName}</span>
            <span className="brand-tagline">{t.brandTagline}</span>
          </span>
        </div>
        <div className="topbar-actions">
          <button type="button" className="lang-toggle" onClick={() => setLang(lang === "en" ? "es" : "en")}>
            {t.lang}
          </button>
          <button
            type="button"
            className="theme-toggle"
            onClick={toggleTheme}
            aria-label={theme === "dark" ? t.themeToLight : t.themeToDark}
            title={theme === "dark" ? t.themeToLight : t.themeToDark}
          >
            <span aria-hidden="true">{theme === "dark" ? "☀" : "☾"}</span>
          </button>
          <button
            type="button"
            className="operator"
            aria-pressed={view === "admin"}
            onClick={() => setView(view === "admin" ? "onboarding" : "admin")}
          >
            {view === "admin" ? t.backToOnboarding : t.openOperator}
          </button>
        </div>
      </header>

      <PrivacyNotice t={t} />
      <ServerBanner t={t} />

      {view === "admin" ? (
        <main className="layout layout-wide">
          <AdminPanel t={t} lang={lang} />
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
