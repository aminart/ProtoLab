import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowRight, Info, Sparkles, Trash2 } from "lucide-react";
import { api, type ScreenUpdate } from "../lib/api";
import { plural } from "../lib/files";
import type { Page, Structure, StructureScreen } from "../lib/types";
import { useToast } from "./Toasts";
import { BusyButton, Empty, PageHead } from "./ui";

const KIND_CHIPS: Record<StructureScreen["kind"], { label: string; className: string }> = {
  figma: { label: "Figma", className: "chip chip-accent" },
  deduced: { label: "Déduit", className: "chip chip-warning" },
  figma_only: { label: "Hors flow", className: "chip chip-warning" },
};

export function StructurePage({ projectId, llmReady, onNavigate }: { projectId: string; llmReady: boolean; onNavigate: (page: Page) => void }) {
  const toast = useToast();
  const [structure, setStructure] = useState<Structure | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [progress, setProgress] = useState<{ done: number; total: number; current: string } | null>(null);

  useEffect(() => {
    api.structure(projectId).then((loaded) => {
      setStructure(loaded);
      setSelected((current) => current ?? loaded.screens.find((s) => !s.excluded)?.id ?? null);
    }).catch((error: Error) => toast("error", error.message));
  }, [projectId, toast]);

  const screen = structure?.screens.find((item) => item.id === selected) ?? null;
  const byId = useMemo(() => new Map(structure?.screens.map((item) => [item.id, item]) ?? []), [structure]);

  const update = async (screenId: string, change: ScreenUpdate) => {
    try {
      setStructure(await api.updateScreen(projectId, screenId, change));
    } catch (error) {
      toast("error", (error as Error).message);
    }
  };

  const analyze = async () => {
    setBusy("analyze");
    try {
      await api.analyze(projectId);
      setStructure(await api.structure(projectId));
      toast("success", "Objets métier et données de départ générés.");
      return true;
    } catch (error) {
      toast("error", (error as Error).message);
      return false;
    } finally {
      setBusy(null);
    }
  };

  const enrichOne = async (screenId: string) => {
    setBusy(`enrich:${screenId}`);
    try {
      const result = await api.enrich(projectId, screenId);
      setStructure(await api.structure(projectId));
      toast(result.dropped.length ? "info" : "success", result.dropped.length ? `Comportements générés ; ${plural(result.dropped.length, "proposition écartée", "propositions écartées")} (calque ou écran inconnu).` : "Comportements générés.");
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const generateAll = async () => {
    if (!structure) return;
    if (!structure.analysis && structure.has_context && !(await analyze())) return;
    const targets = structure.screens.filter((item) => item.frame && !item.excluded);
    setBusy("all");
    const failures: string[] = [];
    for (const [index, item] of targets.entries()) {
      setProgress({ done: index, total: targets.length, current: item.name });
      try {
        await api.enrich(projectId, item.id);
      } catch (error) {
        failures.push(`${item.name} : ${(error as Error).message}`);
      }
    }
    setProgress(null);
    setBusy(null);
    setStructure(await api.structure(projectId));
    if (failures.length) toast("error", `${plural(failures.length, "écran en échec", "écrans en échec")} — ${failures[0]}`);
    else toast("success", `Comportements générés pour ${plural(targets.length, "écran", "écrans")}.`);
  };

  if (!structure) return <main className="mx-auto max-w-[1320px] px-7 py-12 text-ink-muted">Chargement de la structure…</main>;

  if (!structure.has_context && !structure.has_figma) {
    return (
      <main className="mx-auto max-w-[960px] px-4 py-10 sm:px-7">
        <Empty title="Aucune source pour l’instant" action={<button type="button" className="btn-primary" onClick={() => onNavigate("sources")}>Importer les sources</button>}>
          La structure se construit à partir du diagramme Mermaid du document de contexte et des frames de la maquette Figma.
        </Empty>
      </main>
    );
  }

  const deduced = structure.screens.filter((item) => item.kind === "deduced" && !item.excluded).length;
  const withFrame = structure.screens.filter((item) => item.frame && !item.excluded).length;
  const analysis = structure.analysis;

  return (
    <main className="mx-auto flex max-w-[1320px] flex-col gap-6 px-4 py-10 sm:px-7">
      <PageHead
        title="Structure de l’app"
        subtitle="Lue sans IA dans le diagramme Mermaid, puis rattachée aux frames et aux specs par leur nom. Corrigez ce qui doit l’être, puis générez les comportements."
        actions={
          <>
            <BusyButton className="btn-secondary" busy={busy === "all"} disabled={!llmReady || busy !== null || withFrame === 0} onClick={generateAll} title={llmReady ? undefined : "Configurez la connexion au modèle dans Paramètres"}>
              <Sparkles className="h-4 w-4" aria-hidden />
              Générer données et comportements
            </BusyButton>
            <button type="button" className="btn-primary" onClick={() => onNavigate("prototype")}>
              Voir le prototype
              <ArrowRight className="h-4 w-4" aria-hidden />
            </button>
          </>
        }
      />

      {progress && (
        <div className="card flex flex-col gap-2 px-5 py-4" role="status">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="font-medium text-ink">Génération : {progress.current}</span>
            <span className="text-ink-subtle">
              {progress.done} / {progress.total}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-3">
            <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${(progress.done / progress.total) * 100}%` }} />
          </div>
        </div>
      )}

      {structure.mermaid_error && (
        <p className="flex items-start gap-2 rounded-[10px] bg-warning-soft px-4 py-3 text-sm text-warning-text">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {structure.mermaid_error} Les écrans viennent alors des seules frames Figma.
        </p>
      )}

      <section className="flex flex-wrap items-center gap-3 rounded-[10px] bg-ia-soft px-4 py-3 text-ink">
        <span className="chip chip-ia bg-surface">IA</span>
        {analysis ? (
          <span className="flex flex-[1_1_320px] flex-wrap items-center gap-2 text-sm">
            Objets métier :
            {analysis.entities.map((entity) => (
              <span key={entity.name} className="chip bg-surface">
                {entity.label} · {plural(entity.records, "donnée", "données")}
              </span>
            ))}
            {analysis.profiles.length > 0 && <span className="text-ink-muted">Profils : {analysis.profiles.map((p) => p.name).join(", ")}</span>}
          </span>
        ) : (
          <span className="flex-[1_1_320px] text-sm">
            {structure.has_context
              ? "Le modèle peut tirer du contexte les objets métier et un jeu de données fictives, partagé par tous les écrans."
              : "Importez le document de contexte pour générer les objets métier et les données."}
          </span>
        )}
        {structure.has_context && (
          <BusyButton className="btn-soft btn-sm" busy={busy === "analyze"} disabled={!llmReady || busy !== null} onClick={analyze}>
            {analysis ? "Régénérer" : "Générer"}
          </BusyButton>
        )}
      </section>

      {structure.warnings.length > 0 && (
        <details className="card px-5 py-3" open={structure.warnings.some((w) => w.level === "warning")}>
          <summary className="cursor-pointer text-sm font-medium text-ink">
            {plural(structure.warnings.length, "point à vérifier", "points à vérifier")}
          </summary>
          <ul className="mt-3 flex flex-col gap-2">
            {structure.warnings.map((warning, index) => (
              <li key={index} className="flex items-start gap-2 text-sm text-ink-body">
                {warning.level === "warning" ? <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-hidden /> : <Info className="mt-0.5 h-4 w-4 shrink-0 text-ink-subtle" aria-hidden />}
                {warning.message}
              </li>
            ))}
          </ul>
        </details>
      )}

      <div className="flex flex-wrap items-center gap-2 text-[13px] text-ink-muted">
        <span>Légende :</span>
        <span className="chip chip-accent">Figma</span> frame rattachée
        <span className="chip chip-success">Spec</span> comportement décrit
        <span className="chip chip-warning">Déduit</span> écran sans maquette ({deduced})
        <span className="chip chip-ia">IA</span> comportements générés
      </div>

      <div className="flex flex-wrap items-start gap-6">
        <div className="grid min-w-0 flex-[999_1_560px] grid-cols-[repeat(auto-fit,minmax(250px,1fr))] gap-4">
          {structure.modules.map((module) => (
            <section key={module.id} aria-label={`Module ${module.title}`} className="flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 p-4">
              <div className="flex items-center justify-between gap-2 text-[13px] font-bold uppercase tracking-[.04em] text-ink-muted">
                <span>{module.title}</span>
                <span className="chip normal-case tracking-normal">{plural(module.screens.length, "écran", "écrans")}</span>
              </div>
              {module.screens.map((screenId) => {
                const item = byId.get(screenId);
                if (!item) return null;
                const active = item.id === selected;
                const kind = KIND_CHIPS[item.kind];
                return (
                  <button
                    key={item.id}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setSelected(item.id)}
                    className={`flex w-full flex-col gap-2 rounded-[10px] border bg-surface px-3.5 py-3 text-left transition hover:border-line-strong ${
                      active ? "border-2 border-accent px-[13px] py-[11px]" : item.kind === "figma" ? "border-line" : "border-dashed border-line-dashed"
                    } ${item.excluded ? "opacity-50" : ""}`}
                  >
                    <span className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-medium text-ink">
                        {item.name}
                        {structure.start === item.id && <span className="ml-2 text-xs font-normal text-ink-subtle">(départ)</span>}
                      </span>
                      <span className="flex flex-wrap gap-1.5">
                        {item.excluded ? <span className="chip">Exclu</span> : <span className={kind.className}>{kind.label}</span>}
                        {item.spec && <span className="chip chip-success">Spec</span>}
                        {item.enriched && <span className="chip chip-ia">IA</span>}
                      </span>
                    </span>
                    {item.links.length > 0 && (
                      <span className="text-xs leading-normal text-ink-subtle">
                        {item.links.slice(0, 4).map((link, index) => (
                          <span key={index} className="block">
                            → {link.target_name}
                            {link.conditions.length > 0 && ` (${link.conditions.map((c) => c.answer).join(", ")})`}
                          </span>
                        ))}
                        {item.links.length > 4 && <span className="block">+ {item.links.length - 4}</span>}
                      </span>
                    )}
                  </button>
                );
              })}
            </section>
          ))}
        </div>

        {screen && (
          <ScreenPanel
            key={screen.id}
            screen={screen}
            structure={structure}
            llmReady={llmReady}
            busy={busy}
            onUpdate={(change) => update(screen.id, change)}
            onStart={async () => setStructure(await api.setStart(projectId, screen.id))}
            onEnrich={() => enrichOne(screen.id)}
            onClear={async () => setStructure(await api.clearBehaviors(projectId, screen.id))}
          />
        )}
      </div>

      {structure.inventory.components.length > 0 && (
        <details className="card px-5 py-3">
          <summary className="cursor-pointer text-sm font-medium text-ink">
            Composants de la maquette : {structure.inventory.counts.project} projet, {structure.inventory.counts.global} design system, {structure.inventory.counts.local} locaux
            {structure.inventory.counts.missing > 0 && `, ${structure.inventory.counts.missing} introuvables`}
          </summary>
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead className="text-xs uppercase tracking-[.04em] text-ink-subtle">
                <tr>
                  <th className="py-2 pr-4 font-medium">Composant</th>
                  <th className="py-2 pr-4 font-medium">Utilisations</th>
                  <th className="py-2 font-medium">Origine</th>
                </tr>
              </thead>
              <tbody>
                {structure.inventory.components.map((component) => (
                  <tr key={component.key || component.name} className="border-t border-line">
                    <td className="py-2 pr-4 text-ink">{component.name}</td>
                    <td className="py-2 pr-4 text-ink-muted">{component.count}</td>
                    <td className="py-2">
                      {component.source === "missing" ? (
                        <span className="chip chip-warning">Introuvable</span>
                      ) : (
                        <span className="chip">{{ project: "Bibliothèque projet", global: "Design system", local: "Fichier de la maquette" }[component.source]}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
    </main>
  );
}

function ScreenPanel({ screen, structure, llmReady, busy, onUpdate, onStart, onEnrich, onClear }: {
  screen: StructureScreen;
  structure: Structure;
  llmReady: boolean;
  busy: string | null;
  onUpdate: (change: ScreenUpdate) => void;
  onStart: () => void;
  onEnrich: () => void;
  onClear: () => void;
}) {
  const [name, setName] = useState(screen.name);
  const counts = screen.behavior_counts;
  const total = counts.fields + counts.actions + counts.lists + counts.bindings;

  return (
    <aside aria-label="Écran sélectionné" className="card box-border flex max-w-full flex-[1_1_340px] flex-col gap-[18px] p-6 lg:max-w-[420px]">
      <div className="flex flex-col gap-1">
        <span className="text-xs font-medium uppercase tracking-[.04em] text-ink-subtle">Écran sélectionné</span>
        <h2 className="text-xl font-bold text-ink">{screen.name}</h2>
        <span className="text-xs text-ink-subtle">Identifiant : {screen.id}</span>
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="screen-name" className="text-[13px] font-medium text-ink">
          Nom affiché
        </label>
        <input id="screen-name" className="input-area min-h-[40px]" value={name} onChange={(event) => setName(event.target.value)} onBlur={() => name !== screen.name && onUpdate({ name })} />
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="screen-frame" className="text-[13px] font-medium text-ink">
          Frame Figma
        </label>
        <select id="screen-frame" className="input-area min-h-[40px]" value={screen.frame ?? "none"} onChange={(event) => onUpdate({ frame: event.target.value })} disabled={screen.kind === "figma_only"}>
          <option value="none">Aucune (écran généré en version simple)</option>
          {structure.frames.map((frame) => (
            <option key={frame.id} value={frame.id}>
              {frame.name}
            </option>
          ))}
        </select>
        {screen.kind !== "figma_only" && (
          <button type="button" className="self-start text-xs text-accent hover:underline" onClick={() => onUpdate({ frame: "auto" })}>
            Rattacher automatiquement (par le nom)
          </button>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="screen-spec" className="text-[13px] font-medium text-ink">
          Spec rattachée
        </label>
        <select id="screen-spec" className="input-area min-h-[40px]" value={screen.spec ?? "none"} onChange={(event) => onUpdate({ spec: event.target.value })}>
          <option value="none">Aucune</option>
          {structure.specs.map((spec) => (
            <option key={spec.id} value={spec.id}>
              {spec.title || spec.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col gap-2.5">
        <label className="flex items-center gap-2 text-sm text-ink-body">
          <input type="checkbox" className="h-[18px] w-[18px] accent-[var(--nn-primary)]" checked={screen.excluded} onChange={(event) => onUpdate({ excluded: event.target.checked })} />
          Exclure du prototype
        </label>
        <label className="flex items-center gap-2 text-sm text-ink-body">
          <input type="radio" className="h-[18px] w-[18px] accent-[var(--nn-primary)]" checked={structure.start === screen.id} disabled={screen.excluded} onChange={onStart} />
          Écran de départ du prototype
        </label>
      </div>

      {screen.links.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-[13px] font-medium text-ink">Navigation du flow</span>
          {screen.links.map((link, index) => (
            <div key={index} className="rounded-lg border border-line bg-surface-2 px-3 py-2.5 text-[13px] text-ink-body">
              {link.label ? `« ${link.label} »` : "Lien"} → <strong className="font-medium">{link.target_name}</strong>
              {link.conditions.length > 0 && <span className="block text-ink-subtle">si {link.conditions.map((c) => `${c.decision} ${c.answer}`).join(", ")}</span>}
              {link.via && link.via.length > 0 && <span className="block text-ink-subtle">via {link.via.join(", ")}</span>}
            </div>
          ))}
        </div>
      )}

      {screen.frame && !screen.excluded && (
        <div className="flex flex-col gap-2 border-t border-line pt-4">
          <div className="flex items-center gap-2">
            <span className="text-[13px] font-medium text-ink">Comportements</span>
            <span className="chip chip-ia">IA</span>
          </div>
          {screen.enriched ? (
            <div className="flex flex-wrap gap-2">
              <span className="chip">{plural(counts.fields, "champ", "champs")}</span>
              <span className="chip">{plural(counts.actions, "action", "actions")}</span>
              <span className="chip">{plural(counts.lists, "liste", "listes")}</span>
              <span className="chip">{plural(counts.bindings, "texte lié", "textes liés")}</span>
              {total === 0 && <span className="text-xs text-ink-subtle">Rien de particulier pour cet écran.</span>}
            </div>
          ) : (
            <p className="text-[13px] text-ink-subtle">Pas encore générés : la navigation Figma et celle du flow fonctionnent déjà.</p>
          )}
          <div className="flex flex-wrap gap-2">
            <BusyButton className="btn-soft btn-sm" busy={busy === `enrich:${screen.id}`} disabled={!llmReady || busy !== null} onClick={onEnrich}>
              {screen.enriched ? "Régénérer pour cet écran" : "Générer pour cet écran"}
            </BusyButton>
            {screen.enriched && (
              <button type="button" className="btn-ghost btn-sm" onClick={onClear}>
                <Trash2 className="h-4 w-4" aria-hidden />
                Effacer
              </button>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}
