export function formatDateTime(iso: string | undefined | null): string {
  const date = iso ? new Date(iso) : new Date();
  return `${date.toLocaleDateString("fr-FR")} à ${date.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

export function plural(count: number, one: string, many: string): string {
  return `${count.toLocaleString("fr-FR")} ${count > 1 ? many : one}`;
}
