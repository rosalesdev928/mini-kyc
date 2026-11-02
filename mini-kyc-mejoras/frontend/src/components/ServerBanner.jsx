import { useEffect, useState } from "react";
import { getHealth } from "../api.js";

const SHOW_AFTER_MS = 2500; // a normal answer takes well under this
const RETRY_EVERY_MS = 5000;
const MAX_TRIES = 14;
const PER_TRY_TIMEOUT_MS = 70000; // a cold start of the free hosting takes up to ~1 minute

/**
 * Free hosting puts the server to sleep after 15 minutes without traffic. When the page opens it
 * pings /health; if the answer is slow it tells the user the server is waking up instead of
 * looking frozen.
 */
export default function ServerBanner({ t }) {
  const [state, setState] = useState("checking"); // checking | waking | ready | down

  useEffect(() => {
    let cancelled = false;
    let retryTimer;
    let controller;
    let tries = 0;

    const wakeTimer = setTimeout(() => {
      if (!cancelled) setState((current) => (current === "checking" ? "waking" : current));
    }, SHOW_AFTER_MS);

    async function check() {
      tries += 1;
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), PER_TRY_TIMEOUT_MS);
      try {
        const health = await getHealth(controller.signal);
        if (cancelled) return;
        if (health?.status === "ok") {
          setState("ready");
          return;
        }
      } catch {
        // fall through to the retry below
      } finally {
        clearTimeout(timeout);
      }
      if (cancelled) return;
      if (tries >= MAX_TRIES) {
        setState("down");
        return;
      }
      setState((current) => (current === "down" ? current : "waking"));
      retryTimer = setTimeout(check, RETRY_EVERY_MS);
    }

    check();
    return () => {
      cancelled = true;
      clearTimeout(wakeTimer);
      clearTimeout(retryTimer);
      controller?.abort();
    };
  }, []);

  if (state === "waking") {
    return (
      <div className="banner banner-info" role="status">
        <span className="spinner spinner-dark" aria-hidden="true" />
        <span>{t.serverWaking}</span>
      </div>
    );
  }
  if (state === "down") {
    return (
      <div className="banner banner-error" role="alert">
        {t.serverDown}
      </div>
    );
  }
  return null;
}
