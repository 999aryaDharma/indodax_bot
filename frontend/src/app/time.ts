const witaClock = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Makassar",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});
const witaTimestamp = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Makassar",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
});

export function formatWitaClock(value: Date): string {
  return witaClock.format(value);
}

export function formatWitaTimestamp(value: string): string {
  return witaTimestamp.format(new Date(value));
}

export function formatAge(value: string, now: Date): string {
  const difference = Date.parse(value) - now.getTime();
  if (!Number.isFinite(difference)) return "age unavailable";
  const seconds = Math.floor(Math.abs(difference) / 1000);
  const [amount, unit] = seconds < 60
    ? [seconds, "s"]
    : seconds < 3600
      ? [Math.floor(seconds / 60), "m"]
      : seconds < 86400
        ? [Math.floor(seconds / 3600), "h"]
        : [Math.floor(seconds / 86400), "d"];
  return difference > 0 ? `in ${amount}${unit}` : `${amount}${unit} ago`;
}
