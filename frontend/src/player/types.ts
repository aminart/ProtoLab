/** Modèle de prototype produit par le backend (backend/prototype_builder.py). */

export type Style = Record<string, string>;

export interface PNode {
  id: string;
  name: string;
  type: "box" | "text" | "svg";
  style: Style;
  children?: PNode[];
  text?: string;
  viewBox?: string;
  paths?: { d: string; fill: string | null; rule: string }[];
  image?: boolean;
  component?: { key: string; name: string; set: string; props: Record<string, string> };
  role?: "input" | "button" | "checkbox";
  input?: { box: string; valueText: string | null; placeholder: string; label: string; multiline: boolean };
  nav?: { kind: "navigate" | "back" | "url"; screen?: string; url?: string; overlay?: boolean; from_flow?: boolean };
}

export interface FieldRule {
  entity: string | null;
  field: string | null;
  required: boolean;
  format: "text" | "long_text" | "number" | "date" | "email" | "phone";
  message: string;
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
}

export interface Branch {
  field: string;
  op: ">" | ">=" | "<" | "<=" | "==" | "!=" | "empty" | "not_empty";
  value: unknown;
  target: string;
}

export interface Action {
  type: "navigate" | "submit" | "delete" | "back" | "set";
  target: string | null;
  entity: string | null;
  set?: Record<string, unknown>;
  branches?: Branch[];
}

export interface ListBinding {
  entity: string;
  template: string;
  items: string[];
  fields: Record<string, string>;
  target: string | null;
}

export interface Behaviors {
  fields?: Record<string, FieldRule>;
  actions?: Record<string, Action>;
  lists?: Record<string, ListBinding>;
  bindings?: Record<string, { entity: string; field: string }>;
}

export interface Link {
  target: string;
  label: string;
  conditions: { decision: string; answer: string }[];
}

export interface Screen {
  id: string;
  name: string;
  module: string;
  kind: "figma" | "deduced";
  width: number;
  height: number;
  root: PNode | null;
  links: Link[];
  behaviors: Behaviors;
}

export interface Entity {
  name: string;
  label: string;
  fields: { name: string; label: string; type: string; options?: string[] }[];
}

export type DataRecord = Record<string, unknown> & { id: string };

export interface Theme {
  primary: string;
  danger: string;
  success: string;
  text: string;
  background: string;
  font: string;
}

export interface Model {
  model_version: number;
  project: string;
  generated_at: string;
  start: string | null;
  modules: { id: string; title: string; screens: string[] }[];
  screens: Screen[];
  entities: Entity[];
  seed: Record<string, DataRecord[]>;
  theme: Theme;
  version?: { id: string; label: string; created_at: string; screens: number };
}
