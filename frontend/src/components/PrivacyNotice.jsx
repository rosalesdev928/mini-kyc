import { useState } from "react";
import { readStored, writeStored } from "../storage.js";

const STORAGE_KEY = "privacyNoticeDismissed";

/** Reminder that this is a demo: do not upload real documents. Can be dismissed (remembered when storage allows). */
export default function PrivacyNotice({ t }) {
  const [hidden, setHidden] = useState(() => readStored("local", STORAGE_KEY) === "1");
  if (hidden) return null;

  function dismiss() {
    writeStored("local", STORAGE_KEY, "1");
    setHidden(true);
  }

  return (
    <div className="privacy" role="note">
      <p>
        <strong>{t.privacyTitle}</strong> {t.privacyText}
      </p>
      <button type="button" onClick={dismiss}>
        {t.privacyDismiss}
      </button>
    </div>
  );
}
