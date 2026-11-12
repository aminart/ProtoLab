import { useState } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";
import { plural } from "../lib/files";
import type { ImportError, LibrarySummary } from "../lib/types";

const VISIBLE = 6;

/** Fichiers d'une bibliothèque (design system global ou bibliothèque projet), chacun retirable. */
export function LibraryFiles({ library, onRemove, onRemoveAll }: { library: LibrarySummary; onRemove: (fileId: string) => void; onRemoveAll: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const files = expanded ? library.files : library.files.slice(0, VISIBLE);
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="chip chip-success">{plural(library.files.length, "fichier", "fichiers")}</span>
        <span className="chip">{plural(library.components, "composant", "composants")}</span>
        <span className="chip">{plural(library.tokens, "token", "tokens")}</span>
        <button type="button" className="ml-auto text-xs font-medium text-danger-text hover:underline" onClick={onRemoveAll}>
          Tout retirer
        </button>
      </div>
      <ul className="flex flex-col divide-y divide-line rounded-[10px] border border-line bg-surface-2">
        {files.map((file) => (
          <li key={file.id} className="flex items-center gap-3 px-3 py-2">
            <span className="min-w-0 flex-1 truncate text-[13px] text-ink" title={file.name}>
              {file.name}
            </span>
            <span className="shrink-0 text-xs text-ink-subtle">
              {file.kind === "components" ? plural(file.components, "composant", "composants") : plural(file.tokens, "token", "tokens")}
            </span>
            <button type="button" className="nn-icon-btn h-7 w-7 shrink-0 hover:text-danger-text" aria-label={`Retirer ${file.name}`} title="Retirer" onClick={() => onRemove(file.id)}>
              <Trash2 className="h-3.5 w-3.5" aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      {library.files.length > VISIBLE && (
        <button type="button" className="self-start text-xs font-medium text-accent hover:underline" onClick={() => setExpanded((value) => !value)}>
          {expanded ? "Réduire la liste" : `Voir les ${library.files.length} fichiers`}
        </button>
      )}
      {library.unresolved.length > 0 && (
        <p className="flex items-start gap-2 rounded-lg bg-warning-soft px-3 py-2 text-[13px] text-warning-text">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span>
            {plural(library.unresolved.length, "token renvoie", "tokens renvoient")} à un token absent des fichiers importés (par exemple « {library.unresolved[0]} ») :
            importez le fichier qui le définit, souvent celui des foundations.
          </span>
        </p>
      )}
    </div>
  );
}

/** Message après un import : fichiers ajoutés, et ceux qui n'ont pas été reconnus. */
export function importMessage(count: number, errors: ImportError[] | undefined): { tone: "success" | "info"; text: string } {
  const skipped = errors ?? [];
  const imported = `${plural(count, "fichier importé", "fichiers importés")}.`;
  if (!skipped.length) return { tone: "success", text: imported };
  return {
    tone: "info",
    text: `${imported} ${plural(skipped.length, "fichier ignoré", "fichiers ignorés")} : ${skipped.slice(0, 3).map((error) => `${error.file} (${error.message})`).join(", ")}${skipped.length > 3 ? "…" : ""}`,
  };
}
