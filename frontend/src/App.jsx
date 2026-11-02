import { useCallback, useEffect, useState } from "react";
import { createOnboarding } from "./api.js";
import { errorMessage, messages } from "./i18n.js";
import UploadPanel from "./components/UploadPanel.jsx";
import ResultPanel from "./components/ResultPanel.jsx";
import ChatWidget from "./components/ChatWidget.jsx";

export default function App() {
  const [lang, setLang] = useState("en");
  const [status, setStatus] = useState("idle"); // idle | loading | success | error
  const [result, setResult] = useState(null);
  const [errorState, setErrorState] = useState(null); // { code, message }
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  const t = messages[lang];

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

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
    } catch (error) {
      setErrorState({ code: error.code, message: error.message });
      setStatus("error");
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
          <span className="brand-mark" aria-hidden="true">
            ◭
          </span>
          <span className="brand-name">{t.appName}</span>
        </div>
        <div className="topbar-actions">
          <button type="button" className="lang-toggle" onClick={() => setLang(lang === "en" ? "es" : "en")}>
            {t.lang}
          </button>
          <span className="operator">{t.operator}</span>
        </div>
      </header>

      <main className="layout">
        <UploadPanel
          t={t}
          loading={status === "loading"}
          error={error}
          onSubmit={handleSubmit}
          onFileChange={handleFileChange}
        />
        <ResultPanel
          t={t}
          lang={lang}
          status={status}
          result={result}
          previewUrl={previewUrl}
          onReset={handleReset}
        />
      </main>

      <ChatWidget t={t} />
    </div>
  );
}
