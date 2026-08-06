function parts(value: Date, timezone: string) {
  const values = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: timezone,
      year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit", hourCycle: "h23",
    }).formatToParts(value).map((part) => [part.type, part.value]),
  );
  return {
    year: Number(values.year), month: Number(values.month), day: Number(values.day),
    hour: Number(values.hour), minute: Number(values.minute),
  };
}

export function isoToSpotLocalInput(iso: string, timezone: string) {
  const value = parts(new Date(iso), timezone);
  const pad = (item: number) => item.toString().padStart(2, "0");
  return `${value.year}-${pad(value.month)}-${pad(value.day)}T${pad(value.hour)}:${pad(value.minute)}`;
}

export function spotLocalInputToIso(local: string, timezone: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(local);
  if (!match) throw new Error("Ungültiger lokaler Zeitpunkt.");
  const wanted = match.slice(1).map(Number);
  const target = Date.UTC(wanted[0], wanted[1] - 1, wanted[2], wanted[3], wanted[4]);
  let guess = target;
  for (let index = 0; index < 4; index += 1) {
    const shown = parts(new Date(guess), timezone);
    const shownUtc = Date.UTC(shown.year, shown.month - 1, shown.day, shown.hour, shown.minute);
    const delta = target - shownUtc;
    guess += delta;
    if (delta === 0) break;
  }
  if (isoToSpotLocalInput(new Date(guess).toISOString(), timezone) !== local) {
    throw new Error("Diese lokale Uhrzeit existiert wegen der Zeitumstellung nicht.");
  }
  return new Date(guess).toISOString();
}

export function formatTideTime(value: string, timezone: string, uncertainty: number) {
  const instant = new Date(value);
  const time = new Intl.DateTimeFormat("de-DE", {
    timeZone: timezone, hour: "2-digit", minute: "2-digit",
  }).format(instant);
  const date = new Intl.DateTimeFormat("de-DE", {
    timeZone: timezone, weekday: "short", day: "2-digit", month: "2-digit",
  }).format(instant);
  if (uncertainty <= 10) return { date, time: `ca. ${time}` };
  const start = new Date(instant.getTime() - uncertainty * 60_000);
  const end = new Date(instant.getTime() + uncertainty * 60_000);
  const fmt = new Intl.DateTimeFormat("de-DE", {
    timeZone: timezone, hour: "2-digit", minute: "2-digit",
  });
  return { date, time: `ca. ${fmt.format(start)}–${fmt.format(end)}` };
}
