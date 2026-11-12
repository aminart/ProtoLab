import { useEffect, useState } from "react";
import { Trash2 } from "lucide-react";
import { api } from "../lib/api";
import { plural } from "../lib/files";
import type { GlobalLibrary } from "../lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useToast } from "./Toasts";
import { FileDrop, FileRow, PageHead } from "./ui";

export function LibrariesPage() {
  const toast = useToast();
  const [library, setLibrary] = useState<GlobalLibrary | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    api.globalLibrary().then(setLibrary).catch((error: Error) => toast("error", error.message));
  }, [toast]);

  const upload = async (files: File[]) => {
    setBusy(true);
    try {
      let latest: GlobalLibrary | null = library ?? null;
      for (const file of files) latest = await api.uploadGlobalLibrary(file);
      setLibrary(latest);
      toast("success", "Design system global mis à jour.");
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const colors = (library?.tokens_list ?? []).filter((token) => token.type === "color");
  const others = (library?.tokens_list ?? []).filter((token) => token.type !== "color");

  return (
    <main className="mx-auto flex max-w-[1100px] flex-col gap-7 px-4 py-10 sm:px-7">
      <PageHead
        title="Design system global"
        subtitle="Importé une fois, partagé par tous les projets. Chaque projet ajoute sa propre bibliothèque dans ses sources. Il est distinct de Night Navy, qui habille ProtoLab."
      />

      <section className="card flex flex-col gap-4 p-6">
        <h2 className="text-[17px] font-bold text-ink">Fichiers</h2>
        <ul className="flex list-disc flex-col gap-1 pl-5 text-sm leading-normal text-ink-muted">
          <li>
            <b className="font-medium text-ink-body">Composants</b> : le JSON du fichier Figma du design system (pages des composants seulement, pour un fichier plus léger).
          </li>
          <li>
            <b className="font-medium text-ink-body">Tokens</b> : les variables du fichier (API REST, offres Enterprise : <code className="text-[13px]">/v1/files/:key/variables/local</code>), ou un
            export de tokens fait avec un plugin. À défaut, les styles de couleur du fichier des composants servent de tokens.
          </li>
        </ul>
        {library && (
          <div className="flex flex-col gap-2">
            {library.components_source && <FileRow name={library.components_source} status={<span className="chip chip-success">{plural(library.components, "composant", "composants")}</span>} />}
            {(library.tokens_source || library.tokens_from_styles) && (
              <FileRow
                name={library.tokens_source ?? "Styles du fichier des composants"}
                status={<span className="chip chip-success">{plural(library.tokens, "token", "tokens")}</span>}
              />
            )}
          </div>
        )}
        <FileDrop accept=".json,application/json" multiple label="Déposez les composants et/ou les tokens (.json)" busy={busy} onFiles={upload} />
        {library && (
          <button type="button" className="btn-ghost btn-sm self-start text-danger-text" onClick={() => setConfirm(true)}>
            <Trash2 className="h-4 w-4" aria-hidden />
            Retirer le design system
          </button>
        )}
      </section>

      {colors.length > 0 && (
        <section className="card flex flex-col gap-4 p-6">
          <h2 className="text-[17px] font-bold text-ink">Couleurs</h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
            {colors.map((token) => (
              <div key={token.name} className="flex items-center gap-3 rounded-lg border border-line px-3 py-2">
                <span className="h-8 w-8 shrink-0 rounded-md border border-line" style={{ background: String(token.value) }} aria-hidden />
                <span className="min-w-0">
                  <span className="block truncate text-[13px] font-medium text-ink" title={token.name}>
                    {token.name}
                  </span>
                  <span className="block text-xs text-ink-subtle">{String(token.value)}</span>
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {others.length > 0 && (
        <section className="card flex flex-col gap-3 p-6">
          <h2 className="text-[17px] font-bold text-ink">Autres tokens</h2>
          <div className="flex flex-wrap gap-2">
            {others.map((token) => (
              <span key={token.name} className="chip">
                {token.name} · {String(token.value)}
              </span>
            ))}
          </div>
        </section>
      )}

      {library && library.components_list.length > 0 && (
        <section className="card flex flex-col gap-3 p-6">
          <h2 className="text-[17px] font-bold text-ink">Composants</h2>
          <div className="flex flex-wrap gap-2">
            {[...new Set(library.components_list.map((component) => component.name))].map((name) => (
              <span key={name} className="chip">
                {name}
              </span>
            ))}
          </div>
        </section>
      )}

      <ConfirmDialog
        open={confirm}
        title="Retirer le design system global ?"
        confirmLabel="Retirer"
        onCancel={() => setConfirm(false)}
        onConfirm={async () => {
          await api.deleteGlobalLibrary();
          setLibrary(null);
          setConfirm(false);
        }}
      >
        <p>Les projets garderont leur bibliothèque ; leurs écrans générés reprendront les couleurs par défaut, sauf tokens dans la bibliothèque projet.</p>
      </ConfirmDialog>
    </main>
  );
}
