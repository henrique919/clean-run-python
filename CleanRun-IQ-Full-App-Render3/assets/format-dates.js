(function () {
  "use strict";

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  function formatFieldDate(iso) {
    try {
      const text = String(iso || "").trim();
      if (!text) return "";
      if (/^\d{4}-\d{2}-\d{2}$/.test(text)) {
        const parts = text.split("-").map(Number);
        return `${parts[2]} ${MONTHS[parts[1] - 1]} ${parts[0]}`;
      }
      const d = new Date(text);
      if (Number.isNaN(d.getTime())) return text;
      const h = d.getHours() % 12 || 12;
      const m = String(d.getMinutes()).padStart(2, "0");
      const ampm = d.getHours() < 12 ? "am" : "pm";
      return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}, ${h}:${m}${ampm}`;
    } catch {
      return iso || "";
    }
  }

  window.formatFieldDate = formatFieldDate;
  window.fmt = formatFieldDate;
})();
