/** Logique du lecteur, sans React : validation des champs, conditions, mise en forme des données. */
import type { Branch, DataRecord, Entity, FieldRule } from "./types";

export function parseNumber(value: string): number | null {
  const cleaned = value.replace(/[\s €$%]/g, "").replace(",", ".");
  if (!cleaned || !/^-?\d*\.?\d+$/.test(cleaned)) return null;
  return Number(cleaned);
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE = /^[+\d][\d\s.-]{5,}$/;

/** Message d'erreur du champ, ou null s'il est valide. */
export function validate(value: string, rule: FieldRule | undefined): string | null {
  if (!rule) return null;
  const text = value.trim();
  const fail = (fallback: string) => rule.message || fallback;
  if (!text) return rule.required ? rule.message && /obligatoire|indiquez|saisissez|renseignez/i.test(rule.message) ? rule.message : "Ce champ est obligatoire." : null;
  if (rule.format === "number") {
    const number = parseNumber(text);
    if (number === null) return fail("Saisissez un nombre.");
    if (rule.min !== undefined && number < rule.min) return fail(`La valeur doit être au moins ${rule.min}.`);
    if (rule.max !== undefined && number > rule.max) return fail(`La valeur ne peut pas dépasser ${rule.max}.`);
  }
  if (rule.format === "email" && !EMAIL.test(text)) return fail("Saisissez une adresse e-mail valide.");
  if (rule.format === "phone" && !PHONE.test(text)) return fail("Saisissez un numéro de téléphone valide.");
  if (rule.format === "date" && Number.isNaN(Date.parse(text))) return fail("Saisissez une date valide.");
  if (rule.min_length !== undefined && text.length < rule.min_length) return fail(`Saisissez au moins ${rule.min_length} caractères.`);
  if (rule.max_length !== undefined && text.length > rule.max_length) return fail(`Saisissez au plus ${rule.max_length} caractères.`);
  return null;
}

export function coerce(value: string, rule: FieldRule | undefined): unknown {
  if (rule?.format === "number") return parseNumber(value) ?? value;
  return value;
}

function compare(left: unknown, op: Branch["op"], right: unknown): boolean {
  if (op === "empty") return left === undefined || left === null || String(left).trim() === "";
  if (op === "not_empty") return !compare(left, "empty", right);
  const a = typeof left === "number" ? left : parseNumber(String(left ?? ""));
  const b = typeof right === "number" ? right : parseNumber(String(right ?? ""));
  if (a !== null && b !== null) {
    switch (op) {
      case ">": return a > b;
      case ">=": return a >= b;
      case "<": return a < b;
      case "<=": return a <= b;
      case "==": return a === b;
      case "!=": return a !== b;
    }
  }
  const sa = String(left ?? "").trim().toLowerCase();
  const sb = String(right ?? "").trim().toLowerCase();
  if (op === "==") return sa === sb;
  if (op === "!=") return sa !== sb;
  return false;
}

export function branchTarget(record: Record<string, unknown>, branches: Branch[] | undefined): string | null {
  for (const branch of branches ?? []) {
    if (compare(record[branch.field], branch.op, branch.value)) return branch.target;
  }
  return null;
}

export function formatValue(value: unknown, entity: Entity | undefined, field: string): string {
  if (value === undefined || value === null) return "";
  const type = entity?.fields.find((item) => item.name === field)?.type;
  if (type === "number" && typeof value === "number") {
    const label = entity?.fields.find((item) => item.name === field)?.label ?? "";
    const formatted = value.toLocaleString("fr-FR", { maximumFractionDigits: 2 });
    return /€|eur/i.test(label + field) ? `${formatted} €` : formatted;
  }
  if (type === "date" && typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    return new Date(value).toLocaleDateString("fr-FR");
  }
  if (type === "boolean") return value ? "Oui" : "Non";
  return String(value);
}

export function cloneSeed(seed: Record<string, DataRecord[]>): Record<string, DataRecord[]> {
  return JSON.parse(JSON.stringify(seed ?? {}));
}
