import { useEffect, useState } from "react";
import { FolderOpen, Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/files";
import type { ProjectListItem } from "../lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useToast } from "./Toasts";
import { BusyButton, PageHead } from "./ui";

export function ProjectsPage({ currentId, onOpen, onDeleted }: { currentId: string | null; onOpen: (id: string) => void; onDeleted: (id: string) => void }) {
  const toast = useToast();
  const [projects, setProjects] = useState<ProjectListItem[] | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [renaming, setRenaming] = useState<{ id: string; name: string } | null>(null);
  const [toDelete, setToDelete] = useState<ProjectListItem | null>(null);

  const load = () => api.projects().then(setProjects).catch((error: Error) => toast("error", error.message));
  useEffect(() => {
    load();
  }, []);

  const create = async () => {
    setBusy(true);
    try {
      const project = await api.createProject(name.trim() || "Nouveau projet");
      setName("");
      onOpen(project.id);
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const rename = async () => {
    if (!renaming) return;
    try {
      await api.renameProject(renaming.id, renaming.name);
      setRenaming(null);
      load();
    } catch (error) {
      toast("error", (error as Error).message);
    }
  };

  const remove = async () => {
    if (!toDelete) return;
    try {
      await api.deleteProject(toDelete.id);
      onDeleted(toDelete.id);
      toast("info", `Projet « ${toDelete.name} » supprimé.`);
      setToDelete(null);
      load();
    } catch (error) {
      toast("error", (error as Error).message);
    }
  };

  return (
    <main className="mx-auto flex max-w-[960px] flex-col gap-7 px-4 py-10 sm:px-7">
      <PageHead
        title="Projets"
        subtitle="Un projet réunit le document de contexte et les specs de SpecGen, la maquette Figma et sa bibliothèque. Tout reste sur ce poste."
      />

      <section className="card flex flex-col gap-3 p-6">
        <label htmlFor="new-project" className="field-label">
          Nouveau projet
        </label>
        <div className="flex flex-wrap gap-3">
          <input
            id="new-project"
            className="input-area min-h-[44px] flex-[1_1_280px]"
            placeholder="Ex. : Portail des demandes"
            value={name}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => event.key === "Enter" && create()}
          />
          <BusyButton busy={busy} onClick={create}>
            <Plus className="h-4 w-4" aria-hidden />
            Créer le projet
          </BusyButton>
        </div>
      </section>

      {projects && projects.length > 0 && (
        <section className="flex flex-col gap-3" aria-label="Projets existants">
          {projects.map((project) => (
            <div key={project.id} className={`card flex flex-wrap items-center gap-4 px-5 py-4 ${project.id === currentId ? "border-accent" : ""}`}>
              {renaming?.id === project.id ? (
                <div className="flex flex-[1_1_280px] flex-wrap gap-2">
                  <input
                    aria-label="Nom du projet"
                    className="input-area min-h-[40px] flex-1"
                    value={renaming.name}
                    autoFocus
                    onChange={(event) => setRenaming({ ...renaming, name: event.target.value })}
                    onKeyDown={(event) => {
                      if (event.key === "Enter") rename();
                      if (event.key === "Escape") setRenaming(null);
                    }}
                  />
                  <button type="button" className="btn-soft btn-sm" onClick={rename}>
                    Renommer
                  </button>
                  <button type="button" className="btn-ghost btn-sm" onClick={() => setRenaming(null)}>
                    Annuler
                  </button>
                </div>
              ) : (
                <div className="min-w-0 flex-[1_1_280px]">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-base font-bold text-ink">{project.name}</span>
                    {project.id === currentId && <span className="chip chip-accent">Ouvert</span>}
                  </div>
                  <div className="mt-0.5 text-[13px] text-ink-subtle">Modifié le {formatDateTime(project.updated_at)}</div>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <button type="button" className="btn-primary btn-sm" onClick={() => onOpen(project.id)}>
                  <FolderOpen className="h-4 w-4" aria-hidden />
                  Ouvrir
                </button>
                <button type="button" className="nn-icon-btn" aria-label={`Renommer ${project.name}`} onClick={() => setRenaming({ id: project.id, name: project.name })}>
                  <Pencil className="h-4 w-4" aria-hidden />
                </button>
                <button type="button" className="nn-icon-btn hover:text-danger-text" aria-label={`Supprimer ${project.name}`} onClick={() => setToDelete(project)}>
                  <Trash2 className="h-4 w-4" aria-hidden />
                </button>
              </div>
            </div>
          ))}
        </section>
      )}

      <ConfirmDialog open={toDelete !== null} title="Supprimer ce projet ?" confirmLabel="Supprimer" onConfirm={remove} onCancel={() => setToDelete(null)}>
        <p>
          « {toDelete?.name} » sera supprimé de ce poste, avec ses sources, ses réglages et ses versions figées. Les exports HTML déjà téléchargés ne sont
          pas touchés.
        </p>
      </ConfirmDialog>
    </main>
  );
}
