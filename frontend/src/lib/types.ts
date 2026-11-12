export type Page = "projects" | "sources" | "structure" | "prototype" | "libraries" | "settings";

export interface Health {
  configured: boolean;
  missing: string[];
  model: string;
  version: string;
}

// --- Paramètres de connexion (repris de SpecGen) -------------------------------------
export type SettingsField = "api_base" | "api_key" | "ca_bundle" | "model" | "timeout";

export interface ConnectionTest {
  ok: boolean;
  field: "api_base" | "api_key" | "certificate" | null;
  title: string;
  message: string;
  at: string;
  model?: string;
  checks?: { name: string; ok: boolean; message: string }[];
}

export interface ConnectionSettings {
  configured: boolean;
  missing: string[];
  env_fields: SettingsField[];
  env_file: string | null;
  storage_dir: string;
  api_base: string;
  has_api_key: boolean;
  api_key_hint: string;
  certificate: { name: string; imported_at?: string; expires_at?: string } | null;
  model: string;
  timeout: number;
  last_test: ConnectionTest | null;
}

export interface SettingsForm {
  api_base: string;
  api_key: string | null;
  model: string;
  timeout: number;
}

// --- Projets -------------------------------------------------------------------------
export interface ProjectListItem {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface LibrarySummary {
  components: number;
  tokens: number;
  components_source: string | null;
  tokens_source: string | null;
  tokens_from_styles: boolean;
}

export interface AnalysisSummary {
  at: string;
  entities: { name: string; label: string; fields: number; records: number }[];
  profiles: { name: string; description: string }[];
  warnings: string[];
}

export interface VersionInfo {
  id: string;
  label: string;
  created_at: string;
  screens: number;
}

export interface FigmaPage {
  id: string;
  name: string;
  frames: { id: string; name: string; width: number; height: number }[];
}

export interface ProjectOverview {
  id: string;
  name: string;
  updated_at: string;
  context: {
    name: string;
    imported_at: string;
    title: string;
    sections: string[];
    diagrams: number;
    screens: number;
    modules: number;
    error: string | null;
  } | null;
  specs: { id: string; name: string; title: string; imported_at: string; screen: string | null }[];
  figma: {
    name: string;
    imported_at: string;
    page_id: string | null;
    pages: FigmaPage[];
    frames: number;
    interactions: number;
    instances: number;
    images: number;
    icons_without_geometry: number;
    absolute_zones: number;
    error: string | null;
  } | null;
  library: (LibrarySummary & { inventory: Record<"project" | "global" | "local" | "missing", number> }) | null;
  global_library: LibrarySummary | null;
  analysis: AnalysisSummary | null;
  versions: VersionInfo[];
}

export interface FlowLink {
  target: string;
  target_name?: string;
  label: string;
  conditions: { decision: string; answer: string }[];
  via?: string[];
}

export interface StructureScreen {
  id: string;
  name: string;
  module: string;
  frame: string | null;
  frame_name: string | null;
  spec: string | null;
  kind: "figma" | "deduced" | "figma_only";
  excluded: boolean;
  links: FlowLink[];
  enriched: string | null;
  behavior_counts: Record<"fields" | "actions" | "lists" | "bindings", number>;
}

export interface Structure {
  modules: { id: string; title: string; screens: string[] }[];
  screens: StructureScreen[];
  start: string | null;
  warnings: { level: "info" | "warning"; message: string }[];
  frames: { id: string; name: string }[];
  specs: { id: string; name: string; title: string }[];
  inventory: {
    components: { key: string; name: string; count: number; source: "project" | "global" | "local" | "missing" }[];
    counts: Record<"project" | "global" | "local" | "missing", number>;
  };
  mermaid_error: string | null;
  has_context: boolean;
  has_figma: boolean;
  analysis: AnalysisSummary | null;
  decisions: string[];
}

export interface GlobalLibrary extends LibrarySummary {
  components_list: { name: string; key: string }[];
  tokens_list: { name: string; type: string; value: string | number; collection: string }[];
}
