import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { GlobalLibrary } from "../lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { useToast } from "./Toasts";
import { importMessage, LibraryFiles } from "./LibraryFiles";
import { FileDrop, PageHead } from "./ui";

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
      const result = await api.uploadGlobalLibrary(files);
      setLibrary(result.library);
      const message = importMessage(result.imported, result.import_errors);
      toast(message.tone, message.text);
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
            <b className="font-medium text-ink-body">Tokens</b> : autant de fichiers qu’il faut (foundations, un fichier par composant…). Les alias comme{" "}
            <code className="text-[13px]">{"{color.brand.primary}"}</code> sont résolus d’un fichier à l’autre. Les variables du fichier Figma (API REST, offres
            Enterprise : <code className="text-[13px]">/v1/files/:key/variables/local</code>) conviennent aussi.
          </li>
          <li>
            <b className="font-medium text-ink-body">Composants</b> : le JSON du ou des fichiers Figma du design system (pages des composants seulement, pour des fichiers
            plus légers). Leurs styles de couleur servent de tokens à défaut.
          </li>
          <li>Déposez des fichiers, un .zip ou un dossier entier. Un fichier réimporté sous le même nom remplace l’ancien.</li>
        </ul>
        {library && library.files.length > 0 && (
          <LibraryFiles
            library={library}
            onRemove={async (fileId) => {
              try {
                setLibrary(await api.deleteGlobalLibraryFile(fileId));
              } catch (error) {
                toast("error", (error as Error).message);
              }
            }}
            onRemoveAll={() => setConfirm(true)}
          />
        )}
        <FileDrop accept=".json,.zip,application/json,application/zip" multiple folder label="Déposez les fichiers du design system (.json, .zip ou dossier)" busy={busy} onFiles={upload} />
      </section>

      {colors.length > 0 && (
        <section className="card flex flex-col gap-4 p-6">
          <h2 className="text-[17px] font-bold text-ink">Couleurs{colors.length > 96 ? ` (96 sur ${colors.length})` : ""}</h2>
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3">
            {colors.slice(0, 96).map((token) => (
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
          <h2 className="text-[17px] font-bold text-ink">Autres tokens{others.length > 80 ? ` (80 sur ${others.length})` : ""}</h2>
          <div className="flex flex-wrap gap-2">
            {others.slice(0, 80).map((token) => (
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
