import { useState } from "react";
import { ArrowRight, BookOpen, Component, FileText, LayoutGrid, ListChecks, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { formatDateTime, plural } from "../lib/files";
import type { Page, ProjectOverview } from "../lib/types";
import { useToast } from "./Toasts";
import { FileDrop, FileRow, PageHead, SourceCard } from "./ui";

const iconClass = "h-5 w-5";

export function SourcesPage({ project, onChange, onNavigate }: { project: ProjectOverview; onChange: (project: ProjectOverview) => void; onNavigate: (page: Page) => void }) {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);

  const run = async (key: string, task: () => Promise<ProjectOverview>, success?: string) => {
    setBusy(key);
    try {
      onChange(await task());
      if (success) toast("success", success);
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const uploadSpecs = async (files: File[]) => {
    setBusy("specs");
    try {
      let latest = project;
      for (const file of files) latest = await api.uploadSpec(project.id, file);
      onChange(latest);
      toast("success", `${plural(files.length, "spec importée", "specs importées")}.`);
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const context = project.context;
  const figma = project.figma;
  const library = project.library;
  const ready = Boolean(context || figma);
  const remove = (label: string, onClick: () => void) => (
    <button type="button" className="nn-icon-btn hover:text-danger-text" aria-label={`Retirer ${label}`} title="Retirer" onClick={onClick}>
      <Trash2 className="h-4 w-4" aria-hidden />
    </button>
  );

  return (
    <main className="mx-auto flex max-w-[1200px] flex-col gap-7 px-4 py-10 sm:px-7">
      <PageHead
        title="Sources du prototype"
        subtitle="Importez les documents de SpecGen, le JSON de la maquette Figma et la bibliothèque du projet. Seuls les textes passent par le modèle IA ; la structure et la maquette sont lues sans IA."
      />

      <div className="grid grid-cols-[repeat(auto-fit,minmax(340px,1fr))] gap-5">
        <SourceCard
          icon={<FileText className={iconClass} aria-hidden />}
          title="Document de contexte"
          tag={<span className="chip">SpecGen · Markdown</span>}
          description="Son diagramme Mermaid donne l’arborescence et la navigation ; son texte, les objets métier et les données."
        >
          {context ? (
            <>
              <FileRow
                name={context.name}
                meta={`Importé le ${formatDateTime(context.imported_at)}`}
                status={context.error ? <span className="chip chip-warning">À vérifier</span> : <span className="chip chip-success">Prêt</span>}
                actions={remove("le document de contexte", () => run("context", () => api.deleteContext(project.id)))}
              />
              {context.error ? (
                <p className="rounded-lg bg-warning-soft px-3 py-2 text-[13px] text-warning-text">{context.error}</p>
              ) : (
                <div className="flex flex-wrap gap-2">
                  <span className="chip">{plural(context.modules, "module", "modules")}</span>
                  <span className="chip">{plural(context.screens, "écran", "écrans")}</span>
                  <span className="chip">{plural(context.sections.length, "section", "sections")}</span>
                </div>
              )}
            </>
          ) : null}
          <FileDrop
            accept=".md,.markdown,text/markdown"
            label={context ? "Remplacer par un autre .md" : "Déposez le document de contexte (.md)"}
            busy={busy === "context"}
            compact={Boolean(context)}
            onFiles={([file]) => run("context", () => api.uploadContext(project.id, file), "Document de contexte importé.")}
          />
        </SourceCard>

        <SourceCard
          icon={<ListChecks className={iconClass} aria-hidden />}
          title="Spécifications"
          tag={<span className="chip">SpecGen · Markdown</span>}
          description="Une spec par fonctionnalité : elle donne les règles des champs et l’effet des boutons de l’écran auquel elle est rattachée."
        >
          {project.specs.length > 0 && (
            <div className="flex flex-col gap-2">
              {project.specs.map((spec) => (
                <FileRow
                  key={spec.id}
                  name={spec.name}
                  meta={spec.title !== spec.name ? spec.title : undefined}
                  status={spec.screen ? <span className="chip chip-success">Rattachée · {spec.screen}</span> : <span className="chip chip-warning">À rattacher</span>}
                  actions={remove(spec.name, () => run("specs", () => api.deleteSpec(project.id, spec.id)))}
                />
              ))}
            </div>
          )}
          <FileDrop accept=".md,.markdown,text/markdown" multiple label="Déposez une ou plusieurs specs (.md)" busy={busy === "specs"} compact={project.specs.length > 0} onFiles={uploadSpecs} />
        </SourceCard>

        <SourceCard
          icon={<LayoutGrid className={iconClass} aria-hidden />}
          title="Maquette Figma"
          tag={<span className="chip">JSON de l’API</span>}
          description="Les frames deviennent les écrans, les interactions Figma la navigation. Ajoutez geometry=paths à la requête pour récupérer les icônes."
        >
          {figma && (
            <>
              <FileRow
                name={figma.name}
                meta={`Importé le ${formatDateTime(figma.imported_at)}`}
                status={<span className="chip chip-success">Prêt</span>}
                actions={remove("la maquette", () => run("figma", () => api.deleteFigma(project.id)))}
              />
              {figma.pages.length > 1 && (
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="figma-page" className="text-[13px] font-medium text-ink">
                    Page des écrans
                  </label>
                  <select
                    id="figma-page"
                    className="input-area min-h-[40px]"
                    value={figma.page_id ?? ""}
                    onChange={(event) => run("figma", () => api.choosePage(project.id, event.target.value))}
                  >
                    {figma.pages.map((page) => (
                      <option key={page.id} value={page.id}>
                        {page.name} · {plural(page.frames.length, "frame", "frames")}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <span className="chip">{plural(figma.frames, "frame", "frames")}</span>
                <span className="chip">{plural(figma.interactions, "interaction", "interactions")}</span>
                <span className="chip">{plural(figma.instances, "instance de composant", "instances de composants")}</span>
                {figma.absolute_zones > 0 && <span className="chip chip-warning">{plural(figma.absolute_zones, "zone sans auto-layout", "zones sans auto-layout")}</span>}
                {figma.images > 0 && <span className="chip chip-warning">{plural(figma.images, "image remplacée", "images remplacées")}</span>}
                {figma.icons_without_geometry > 0 && <span className="chip chip-warning">{plural(figma.icons_without_geometry, "icône sans tracé", "icônes sans tracé")}</span>}
              </div>
            </>
          )}
          <FileDrop
            accept=".json,application/json"
            label={figma ? "Remplacer par un nouvel export" : "Déposez le JSON produit par votre script"}
            busy={busy === "figma"}
            compact={Boolean(figma)}
            onFiles={([file]) => run("figma", () => api.uploadFigma(project.id, file), "Maquette importée.")}
          />
        </SourceCard>

        <SourceCard
          icon={<Component className={iconClass} aria-hidden />}
          title="Bibliothèque du projet"
          tag={<span className="chip">Composants · tokens</span>}
          description="Le JSON du fichier de bibliothèque, ses variables, ou un export de tokens : le type est reconnu à l’import."
        >
          {library && (
            <>
              <FileRow
                name={[library.components_source, library.tokens_source].filter(Boolean).join(" + ") || "Bibliothèque"}
                status={<span className="chip chip-success">{plural(library.components, "composant", "composants")} · {plural(library.tokens, "token", "tokens")}</span>}
                actions={remove("la bibliothèque", () => run("library", () => api.deleteLibrary(project.id)))}
              />
            </>
          )}
          {figma && library?.inventory && (
            <div className="flex flex-wrap gap-2">
              <span className="chip">Projet : {library.inventory.project}</span>
              <span className="chip">Design system : {library.inventory.global}</span>
              {library.inventory.missing > 0 && <span className="chip chip-warning">{plural(library.inventory.missing, "composant introuvable", "composants introuvables")}</span>}
            </div>
          )}
          <FileDrop
            accept=".json,application/json"
            label={library ? "Ajouter ou remplacer un fichier" : "Déposez la bibliothèque du projet (.json)"}
            busy={busy === "library"}
            compact={Boolean(library)}
            onFiles={([file]) => run("library", () => api.uploadLibrary(project.id, file), "Bibliothèque importée.")}
          />
          <button type="button" className="flex items-center gap-2 self-start text-[13px] font-medium text-accent underline-offset-2 hover:underline" onClick={() => onNavigate("libraries")}>
            <BookOpen className="h-4 w-4" aria-hidden />
            {project.global_library ? "Design system global importé" : "Importer le design system global"}
          </button>
        </SourceCard>
      </div>

      <section className="card flex flex-wrap items-center gap-4 px-6 py-5">
        <div className="flex flex-[1_1_360px] flex-col gap-1">
          <span className="text-[15px] font-bold text-ink">Prochaine étape : vérifier la structure</span>
          <p className="text-sm leading-normal text-ink-muted">
            Les écrans du diagramme sont rattachés aux frames et aux specs par leur nom. Vous corrigez ce qui doit l’être avant de générer.
          </p>
        </div>
        <button type="button" className="btn-primary" disabled={!ready} onClick={() => onNavigate("structure")}>
          Voir la structure
          <ArrowRight className="h-4 w-4" aria-hidden />
        </button>
      </section>
    </main>
  );
}
