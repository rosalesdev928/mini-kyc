// Safe wrappers around the browser storage: it can be blocked (private mode) or throw, and the app must still work.

function area(kind) {
  try {
    return kind === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function readStored(kind, name, fallback = "") {
  try {
    return area(kind)?.getItem(name) ?? fallback;
  } catch {
    return fallback;
  }
}

export function writeStored(kind, name, value) {
  try {
    area(kind)?.setItem(name, value);
  } catch {
    // ignore: the value just will not survive a reload
  }
}
