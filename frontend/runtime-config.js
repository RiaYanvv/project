/* Production-safe runtime settings.
   The browser key is a placeholder: the real DeepSeek credential stays in the
   Render environment and is never shipped to the frontend. */
(function configureLocusRuntime() {
  var host = window.location.hostname;
  var localHost =
    window.location.protocol === "file:" ||
    host === "localhost" ||
    host === "127.0.0.1" ||
    host === "::1";
  var defaultApiBase = localHost
    ? "http://127.0.0.1:8000"
    : "https://georisk-agent.onrender.com";

  window.LOCUS_API_BASE = window.LOCUS_API_BASE || defaultApiBase;
  window.LOCUS_API_KEY = window.LOCUS_API_KEY || "server-managed";
  window.LOCUS_MODEL = window.LOCUS_MODEL || "deepseek-flash";
})();
