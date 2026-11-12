import { useCallback, useEffect, useRef, useState } from "react";
import { Download, Lock, MousePointerClick, Play, RotateCcw, Trash2 } from "lucide-react";
import { Player, ScaledFrame, type PlayerHandle } from "../player/Player";
import type { Model } from "../player/types";
import { api, downloadExport } from "../lib/api";
import { formatDateTime, plural } from "../lib/files";
import type { Page, VersionInfo } from "../lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useToast } from "./Toasts";
import { BusyButton, Empty } from "./ui";

export function PrototypePage({ projectId, onNavigate, onTest }: { projectId: string; onNavigate: (page: Page) => void; onTest: (versionId: string | null) => void }) {
  const toast = useToast();
  const player = useRef<PlayerHandle>(null);
  const [model, setModel] = useState<Model | null>(null);
  const [versions, setVersions] = useState<VersionInfo[]>([]);
  const [screen, setScreen] = useState<string | null>(null);
  const [hotspots, setHotspots] = useState(true);
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<VersionInfo | null>(null);

  useEffect(() => {
    api.prototype(projectId).then(setModel).catch((error: Error) => toast("error", error.message));
    api.project(projectId).then((project) => setVersions(project.versions)).catch(() => undefined);
  }, [projectId, toast]);

  const onScreenChange = useCallback((id: string) => setScreen(id), []);

  if (!model) return <main className="mx-auto max-w-[1440px] px-7 py-12 text-ink-muted">Chargement du prototype…</main>;
  if (!model.screens.length) {
    return (
      <main className="mx-auto max-w-[960px] px-4 py-10 sm:px-7">
        <Empty title="Pas encore d’écran" action={<button type="button" className="btn-primary" onClick={() => onNavigate("sources")}>Importer les sources</button>}>
          Le prototype a besoin du document de contexte (son diagramme Mermaid) ou d’une maquette Figma.
        </Empty>
      </main>
    );
  }

  const current = model.screens.find((item) => item.id === screen) ?? model.screens[0];
  const moduleTitle = model.modules.find((module) => module.screens.includes(current.id))?.title;
  const generated = model.screens.some((item) => Object.values(item.behaviors ?? {}).some((value) => value && Object.keys(value).length));

  const freeze = async () => {
    setBusy("freeze");
    try {
      const version = await api.freeze(projectId, label);
      setVersions((list) => [version, ...list]);
      setLabel("");
      toast("success", `« ${version.label} » figée : tous les participants verront exactement cette version.`);
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const exportHtml = async (versionId?: string) => {
    setBusy(`export:${versionId ?? "draft"}`);
    try {
      await downloadExport(projectId, versionId);
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex min-h-[calc(100vh-64px)] flex-col">
      <div className="flex flex-wrap items-center gap-3 border-b border-line bg-surface px-4 py-3 sm:px-7">
        <div className="flex flex-[1_1_260px] flex-wrap items-center gap-2 text-sm">
          {moduleTitle && <span className="text-ink-subtle">{moduleTitle}</span>}
          {moduleTitle && <span className="text-ink-subtle" aria-hidden>/</span>}
          <span className="text-base font-bold text-ink">{current.name}</span>
          <span className="chip">Brouillon</span>
          {current.kind === "deduced" && <span className="chip chip-warning">Sans maquette</span>}
        </div>
        <label className="flex items-center gap-2 text-[13px] text-ink-body">
          <input type="checkbox" className="h-4 w-4 accent-[var(--nn-primary)]" checked={hotspots} onChange={(event) => setHotspots(event.target.checked)} />
          <MousePointerClick className="h-4 w-4 text-ink-subtle" aria-hidden />
          Zones cliquables
        </label>
        <button type="button" className="btn-secondary btn-sm" onClick={() => player.current?.reset()}>
          <RotateCcw className="h-4 w-4" aria-hidden />
          Réinitialiser
        </button>
        <button type="button" className="btn-soft btn-sm" onClick={() => onTest(null)}>
          <Play className="h-4 w-4" aria-hidden />
          Tester le brouillon
        </button>
        <BusyButton className="btn-secondary btn-sm" busy={busy === "export:draft"} onClick={() => exportHtml()}>
          <Download className="h-4 w-4" aria-hidden />
          Exporter en HTML
        </BusyButton>
      </div>

      <div className="flex flex-wrap items-start gap-5 px-4 pb-10 pt-5 sm:px-7">
        <nav aria-label="Écrans du prototype" className="card box-border max-w-full flex-[1_1_220px] px-2 py-3 lg:max-w-[260px]">
          {model.modules.map((module) => (
            <div key={module.id}>
              <div className="mb-1 mt-3 px-2.5 text-xs font-bold uppercase tracking-[.04em] text-ink-subtle first:mt-1">{module.title}</div>
              {module.screens.map((screenId) => {
                const item = model.screens.find((s) => s.id === screenId);
                if (!item) return null;
                const active = item.id === current.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-current={active ? "true" : undefined}
                    onClick={() => player.current?.goTo(item.id)}
                    className={`flex min-h-[40px] w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm ${
                      active ? "bg-accent-soft font-medium text-accent-ink" : "text-ink-body hover:bg-surface-3"
                    }`}
                  >
                    {item.name}
                    {item.kind === "deduced" && <span className="chip chip-warning px-2 py-0 text-[11px]">Déduit</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <section aria-label="Aperçu du prototype" className="flex min-w-0 flex-[999_1_520px] flex-col gap-2.5">
          <div className="rounded-xl border border-line bg-surface-2 p-5">
            <div className="mx-auto overflow-hidden rounded-[10px] bg-[#FFFFFF] shadow-[0_1px_3px_rgba(16,24,40,.10),0_1px_2px_rgba(16,24,40,.06)]" style={{ maxWidth: current.width }}>
              <ScaledFrame width={current.width}>
                <Player ref={player} model={model} showHotspots={hotspots} onScreenChange={onScreenChange} />
              </ScaledFrame>
            </div>
          </div>
          <p className="text-center text-[13px] text-ink-subtle">
            Aperçu interactif{generated ? "" : " · navigation seule : générez les comportements dans Structure pour les champs et les données"}
          </p>
        </section>

        <aside aria-label="Données et versions" className="box-border flex max-w-full flex-[1_1_300px] flex-col gap-4 lg:max-w-[360px]">
          <section className="card flex flex-col gap-3 p-5">
            <h2 className="text-[15px] font-bold text-ink">Données de départ</h2>
            {model.entities.length ? (
              model.entities.map((entity) => (
                <div key={entity.name} className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2.5 text-[13px]">
                  <span className="text-ink">{entity.label}</span>
                  <span className="chip">{plural(model.seed[entity.name]?.length ?? 0, "élément", "éléments")}</span>
                </div>
              ))
            ) : (
              <p className="text-[13px] text-ink-subtle">Aucune donnée : générez les objets métier dans Structure pour que les listes et les formulaires se répondent.</p>
            )}
            <p className="text-xs leading-normal text-ink-subtle">Ce que le participant saisit s’ajoute à ces données pendant le test ; « Réinitialiser » les remet à zéro.</p>
          </section>

          <section className="card flex flex-col gap-3 p-5">
            <div className="flex items-center gap-2">
              <Lock className="h-4 w-4 text-ink-subtle" aria-hidden />
              <h2 className="text-[15px] font-bold text-ink">Versions figées</h2>
            </div>
            <p className="text-xs leading-normal text-ink-subtle">Figez le prototype avant une session : tous les participants verront exactement la même version, même si vous régénérez ensuite.</p>
            <div className="flex flex-wrap gap-2">
              <input
                aria-label="Nom de la version"
                className="input-area min-h-[36px] flex-[1_1_160px]"
                placeholder={`Version ${versions.length + 1}`}
                value={label}
                onChange={(event) => setLabel(event.target.value)}
              />
              <BusyButton className="btn-primary btn-sm" busy={busy === "freeze"} onClick={freeze}>
                Figer
              </BusyButton>
            </div>
            {versions.map((version) => (
              <div key={version.id} className="flex flex-col gap-2 rounded-lg border border-line bg-surface-2 px-3 py-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium text-ink">{version.label}</div>
                    <div className="text-xs text-ink-subtle">
                      {formatDateTime(version.created_at)} · {plural(version.screens, "écran", "écrans")}
                    </div>
                  </div>
                  <button type="button" className="nn-icon-btn h-8 w-8 hover:text-danger-text" aria-label={`Supprimer ${version.label}`} onClick={() => setToDelete(version)}>
                    <Trash2 className="h-4 w-4" aria-hidden />
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn-soft btn-sm" onClick={() => onTest(version.id)}>
                    <Play className="h-4 w-4" aria-hidden />
                    Mode test
                  </button>
                  <BusyButton className="btn-ghost btn-sm" busy={busy === `export:${version.id}`} onClick={() => exportHtml(version.id)}>
                    <Download className="h-4 w-4" aria-hidden />
                    HTML
                  </BusyButton>
                </div>
              </div>
            ))}
          </section>
        </aside>
      </div>

      <ConfirmDialog
        open={toDelete !== null}
        title="Supprimer cette version ?"
        confirmLabel="Supprimer"
        onCancel={() => setToDelete(null)}
        onConfirm={async () => {
          if (!toDelete) return;
          try {
            setVersions(await api.deleteVersion(projectId, toDelete.id));
          } catch (error) {
            toast("error", (error as Error).message);
          }
          setToDelete(null);
        }}
      >
        <p>« {toDelete?.label} » ne pourra plus être ouverte en mode test. Les exports HTML déjà téléchargés restent utilisables.</p>
      </ConfirmDialog>
    </div>
  );
}
