import type { Model } from "../player/types";
import type {
  ConnectionSettings, ConnectionTest, GlobalLibrary, Health, ProjectListItem, ProjectOverview, SettingsForm, Structure, VersionInfo,
} from "./types";

async function parseError(response: Response): Promise<Error> {
  let detail = `Erreur ${response.status}`;
  try {
    const payload = await response.json();
    if (typeof payload.detail === "string") detail = payload.detail;
  } catch {
    // Non-JSON error body: keep the status message.
  }
  return new Error(detail);
}

async function request<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const response = await fetch(path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch(path, { method: "POST", body: form });
  if (!response.ok) throw await parseError(response);
  return response.json() as Promise<T>;
}

const project = (id: string) => `/api/projects/${encodeURIComponent(id)}`;

export interface ScreenUpdate {
  frame?: string;
  spec?: string;
  excluded?: boolean;
  name?: string;
}

export const api = {
  health: () => request<Health>("/api/health"),
  settings: () => request<ConnectionSettings>("/api/settings"),
  saveSettings: (form: SettingsForm) => request<ConnectionSettings>("/api/settings", form, "PUT"),
  clearSettings: () => request<ConnectionSettings>("/api/settings", undefined, "DELETE"),
  testSettings: (form: SettingsForm) => request<ConnectionTest>("/api/settings/test", form),
  uploadCertificate: (file: File) => upload<ConnectionSettings>("/api/settings/certificate", file),

  projects: () => request<ProjectListItem[]>("/api/projects"),
  createProject: (name: string) => request<ProjectOverview>("/api/projects", { name }),
  project: (id: string) => request<ProjectOverview>(project(id)),
  renameProject: (id: string, name: string) => request<ProjectOverview>(project(id), { name }, "PATCH"),
  deleteProject: (id: string) => request<{ ok: boolean }>(project(id), undefined, "DELETE"),

  uploadContext: (id: string, file: File) => upload<ProjectOverview>(`${project(id)}/context`, file),
  deleteContext: (id: string) => request<ProjectOverview>(`${project(id)}/context`, undefined, "DELETE"),
  uploadSpec: (id: string, file: File) => upload<ProjectOverview>(`${project(id)}/specs`, file),
  deleteSpec: (id: string, specId: string) => request<ProjectOverview>(`${project(id)}/specs/${specId}`, undefined, "DELETE"),
  uploadFigma: (id: string, file: File) => upload<ProjectOverview>(`${project(id)}/figma`, file),
  choosePage: (id: string, pageId: string) => request<ProjectOverview>(`${project(id)}/figma/page`, { page_id: pageId }, "PUT"),
  deleteFigma: (id: string) => request<ProjectOverview>(`${project(id)}/figma`, undefined, "DELETE"),
  uploadLibrary: (id: string, file: File) => upload<ProjectOverview>(`${project(id)}/library`, file),
  deleteLibrary: (id: string) => request<ProjectOverview>(`${project(id)}/library`, undefined, "DELETE"),

  globalLibrary: () => request<GlobalLibrary | null>("/api/libraries/global"),
  uploadGlobalLibrary: (file: File) => upload<GlobalLibrary>("/api/libraries/global", file),
  deleteGlobalLibrary: () => request<null>("/api/libraries/global", undefined, "DELETE"),

  structure: (id: string) => request<Structure>(`${project(id)}/structure`),
  updateScreen: (id: string, screenId: string, update: ScreenUpdate) => request<Structure>(`${project(id)}/screens/${encodeURIComponent(screenId)}`, update, "PUT"),
  setStart: (id: string, screen: string | null) => request<Structure>(`${project(id)}/start`, { screen }, "PUT"),
  analyze: (id: string) => request<{ analysis: unknown }>(`${project(id)}/analyze`, {}),
  enrich: (id: string, screenId: string) =>
    request<{ screen: string; counts: Record<string, number>; dropped: string[] }>(`${project(id)}/screens/${encodeURIComponent(screenId)}/enrich`, {}),
  clearBehaviors: (id: string, screenId: string) => request<Structure>(`${project(id)}/screens/${encodeURIComponent(screenId)}/behaviors`, undefined, "DELETE"),

  prototype: (id: string) => request<Model>(`${project(id)}/prototype`),
  freeze: (id: string, label: string) => request<VersionInfo>(`${project(id)}/versions`, { label }),
  version: (id: string, versionId: string) => request<Model>(`${project(id)}/versions/${versionId}`),
  deleteVersion: (id: string, versionId: string) => request<VersionInfo[]>(`${project(id)}/versions/${versionId}`, undefined, "DELETE"),
};

export async function downloadExport(id: string, versionId?: string): Promise<void> {
  const query = versionId ? `?version=${encodeURIComponent(versionId)}` : "";
  const response = await fetch(`${project(id)}/export${query}`);
  if (!response.ok) throw await parseError(response);
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = /filename="([^"]+)"/.exec(disposition)?.[1] ?? "prototype.html";
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}
