// Keep the wall clock and offset the server supplied; never consult the browser's zone.
export function fmtTime(iso) {
  const match = typeof iso === "string" && iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2}:\d{2}(?:\.\d+)?)(Z|[+-]\d{2}:\d{2})$/);
  return match ? `${match[1]} ${match[2]} ${match[3] === "Z" ? "+00:00" : match[3]}` : "—";
}

const validDay = (day) => /^\d{4}-\d{2}-\d{2}$/.test(day ?? "") &&
  Number.isFinite(Date.parse(`${day}T00:00:00Z`)) && new Date(`${day}T00:00:00Z`).toISOString().slice(0, 10) === day;

// today is the operating date returned by /stats/trend, not a date derived from the host clock.
export function reportPeriod(today, type, from, to) {
  if (type === "custom") return validDay(from) && validDay(to) && from <= to ? { label: `${from} 至 ${to} `, from, to } : null;
  if (!validDay(today)) return null;
  if (type === "month") return { label: `${Number(today.slice(5, 7))} 月`, from: `${today.slice(0, 7)}-01`, to: today };
  const monday = new Date(`${today}T00:00:00Z`);
  monday.setUTCDate(monday.getUTCDate() - ((monday.getUTCDay() + 6) % 7));
  return { label: "本周", from: monday.toISOString().slice(0, 10), to: today };
}
