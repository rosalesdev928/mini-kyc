// Applies the saved (or system) colour theme before the first paint, so there is no flash of the wrong theme.
// It is a separate file (not an inline script) so that the Content Security Policy can stay strict.
(function () {
  var theme = null;
  try {
    theme = window.localStorage.getItem("theme");
  } catch (error) {
    theme = null; // storage can be blocked (private mode)
  }
  if (theme !== "light" && theme !== "dark") {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  document.documentElement.setAttribute("data-theme", theme);
})();
