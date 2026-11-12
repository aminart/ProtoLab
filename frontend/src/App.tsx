import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, FolderOpen, Settings } from "lucide-react";
import logoApp from "./assets/protolab.svg";
import { LibrariesPage } from "./components/LibrariesPage";
import { ProjectsPage } from "./components/ProjectsPage";
import { PrototypePage } from "./components/PrototypePage";
import { SettingsPage } from "./components/SettingsPage";
import { SourcesPage } from "./components/SourcesPage";
import { StructurePage } from "./components/StructurePage";
import { ThemeToggle } from "./components/ThemeToggle";
import { ToastProvider, useToast } from "./components/Toasts";
import { api } from "./lib/api";
import type { Health, Page, ProjectOverview } from "./lib/types";
import { usePersistentState } from "./lib/usePersistentState";
import { TestShell } from "./player/TestShell";
import type { Model } from "./player/types";

export default function App() {
  return (
    <ToastProvider>
      <Workspace />
    </ToastProvider>
  );
}

const STEPS: { id: Page; label: string }[] = [
  { id: "sources", label: "Sources" },
  { id: "structure", label: "Structure" },
  { id: "prototype", label: "Prototype" },
];

function Workspace() {
  const toast = useToast();
  const [page, setPage] = usePersistentState<Page>("page", "projects");
  const [projectId, setProjectId] = usePersistentState<string | null>("project", null);
  const [project, setProject] = useState<ProjectOverview | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [settingsDismissed, setSettingsDismissed] = usePersistentState("settingsDismissed", false);
  const [test, setTest] = useState<Model | null>(null);

  const refreshHealth = useCallback(() => api.health().then(setHealth), []);

  useEffect(() => {
    api.health()
      .then((loaded) => {
        setHealth(loaded);
        if (!loaded.configured && !settingsDismissed) setPage("settings");
      })
      .catch(() => setHealthError(true));
    // Only on startup.
  }, []);

  useEffect(() => {
    if (!projectId) {
      setProject(null);
      if (STEPS.some((step) => step.id === page)) setPage("projects");
      return;
    }
    api.project(projectId)
      .then(setProject)
      .catch(() => {
        setProjectId(null);
        setPage("projects");
      });
  }, [projectId]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [page]);

  const openTest = async (versionId: string | null) => {
    if (!projectId) return;
    try {
      setTest(versionId ? await api.version(projectId, versionId) : await api.prototype(projectId));
    } catch (error) {
      toast("error", (error as Error).message);
    }
  };

  if (test) return <TestShell model={test} onExit={() => setTest(null)} />;

  const llmReady = Boolean(health?.configured);
  const needsProject = STEPS.some((step) => step.id === page);

  return (
    <div className="min-h-screen">
      <header className="nn-appbar z-40 lg:sticky lg:top-0">
        <a
          href="#"
          className="nn-appbar-brand"
          onClick={(event) => {
            event.preventDefault();
            setPage(projectId ? "sources" : "projects");
          }}
        >
          <img className="nn-appbar-icon" src={logoApp} alt="" />
          ProtoLab
        </a>
        <nav aria-label="Navigation principale" className="nn-appbar-nav">
          <button type="button" onClick={() => setPage("projects")} aria-current={page === "projects" ? "page" : undefined} className={`nn-appbar-tab gap-2 ${page === "projects" ? "is-active" : ""}`}>
            <FolderOpen className="h-4 w-4" aria-hidden />
            {project ? project.name : "Projets"}
          </button>
          {STEPS.map((step, index) => {
            const active = page === step.id;
            return (
              <button
                key={step.id}
                type="button"
                disabled={!project}
                onClick={() => setPage(step.id)}
                aria-current={active ? "page" : undefined}
                className={`nn-appbar-tab gap-2 ${active ? "is-active" : ""}`}
              >
                <span className={`flex h-[22px] w-[22px] items-center justify-center rounded-full text-xs font-medium ${active ? "bg-accent-soft text-accent-ink" : "bg-surface-3 text-ink-muted"}`}>
                  {index + 1}
                </span>
                {step.label}
              </button>
            );
          })}
          <button type="button" onClick={() => setPage("libraries")} aria-current={page === "libraries" ? "page" : undefined} className={`nn-appbar-tab ${page === "libraries" ? "is-active" : ""}`}>
            Design system
          </button>
        </nav>
        <div className="nn-appbar-tools">
          {health && (
            <button
              type="button"
              onClick={() => setPage("settings")}
              aria-label={`${llmReady ? "Modèle IA connecté" : "IA non configurée"} : paramètres de connexion`}
              title={llmReady ? `Modèle : ${health.model}` : "Configurer la connexion"}
              className={`flex min-h-[32px] items-center gap-2 rounded-full px-3 text-[13px] font-medium transition hover:opacity-90 ${
                llmReady ? "bg-success-soft text-success-text" : "bg-warning-soft text-warning-text"
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${llmReady ? "bg-success" : "bg-warning"}`} />
              <span className="hidden sm:inline">{llmReady ? "Modèle IA connecté" : "IA non configurée"}</span>
            </button>
          )}
          <ThemeToggle />
          <button
            type="button"
            onClick={() => setPage("settings")}
            aria-label="Paramètres"
            aria-current={page === "settings" ? "page" : undefined}
            title="Paramètres"
            className={`nn-icon-btn ${page === "settings" ? "bg-accent-soft text-accent-ink" : ""}`}
          >
            <Settings className="h-[19px] w-[19px]" aria-hidden />
          </button>
        </div>
      </header>

      {(healthError || (health && !llmReady)) && page !== "settings" && (
        <div className="border-b border-warning-line bg-warning-soft">
          <p className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm text-warning-text sm:px-7">
            <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden />
            {healthError
              ? "Le serveur Python est injoignable. Vérifiez qu’il est bien démarré."
              : "Sans connexion au modèle IA, le prototype garde la navigation de Figma et du flow, sans données ni règles de champs."}
            {!healthError && (
              <button type="button" className="ml-1 font-medium underline" onClick={() => setPage("settings")}>
                Configurer
              </button>
            )}
          </p>
        </div>
      )}

      {page === "projects" && (
        <ProjectsPage
          currentId={projectId}
          onOpen={(id) => {
            setProjectId(id);
            setPage("sources");
          }}
          onDeleted={(id) => id === projectId && setProjectId(null)}
        />
      )}
      {page === "libraries" && <LibrariesPage />}
      {page === "settings" && (
        <SettingsPage
          onSaved={(_settings, firstSetup) => {
            refreshHealth().catch(() => setHealthError(true));
            if (firstSetup) {
              toast("success", "Connexion configurée : la génération est activée.");
              setPage(projectId ? "sources" : "projects");
            }
          }}
          onLater={() => {
            setSettingsDismissed(true);
            setPage(projectId ? "sources" : "projects");
          }}
        />
      )}
      {needsProject && project && projectId && (
        <div key={projectId}>
          {page === "sources" && <SourcesPage project={project} onChange={setProject} onNavigate={setPage} />}
          {page === "structure" && <StructurePage projectId={projectId} llmReady={llmReady} onNavigate={setPage} />}
          {page === "prototype" && <PrototypePage projectId={projectId} onNavigate={setPage} onTest={openTest} />}
        </div>
      )}
    </div>
  );
}
