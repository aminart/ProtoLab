import { useEffect, useRef, useState, type ReactNode } from "react";
import { FolderOpen, Loader2, Upload } from "lucide-react";

export function PageHead({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="nn-page-head">
      <div>
        <h1 className="nn-page-title">{title}</h1>
        {subtitle && <p className="nn-page-subtitle">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  );
}

export function SourceCard({ icon, title, tag, description, children }: { icon: ReactNode; title: string; tag?: ReactNode; description: string; children: ReactNode }) {
  return (
    <section className="card flex flex-col gap-4 p-6">
      <div className="flex items-start gap-3.5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-accent-soft text-accent-ink">{icon}</span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[17px] font-bold text-ink">{title}</h2>
            {tag}
          </div>
          <p className="text-sm leading-normal text-ink-muted">{description}</p>
        </div>
      </div>
      {children}
    </section>
  );
}

/** Files of a drop, folders included (walked recursively; each file keeps its path in the folder). */
async function droppedFiles(transfer: DataTransfer): Promise<File[]> {
  const entries = Array.from(transfer.items)
    .map((item) => item.webkitGetAsEntry?.())
    .filter((entry): entry is FileSystemEntry => Boolean(entry));
  if (!entries.length) return Array.from(transfer.files);
  const files: File[] = [];
  const walk = async (entry: FileSystemEntry, folder: string): Promise<void> => {
    if (entry.isFile) {
      const file = await new Promise<File>((resolve, reject) => (entry as FileSystemFileEntry).file(resolve, reject));
      Object.defineProperty(file, "relativePath", { value: folder + file.name });
      files.push(file);
    } else if (entry.isDirectory) {
      const reader = (entry as FileSystemDirectoryEntry).createReader();
      let batch: FileSystemEntry[];
      do {
        batch = await new Promise<FileSystemEntry[]>((resolve, reject) => reader.readEntries(resolve, reject));
        for (const child of batch) await walk(child, `${folder}${entry.name}/`);
      } while (batch.length);
    }
  };
  for (const entry of entries) await walk(entry, "");
  return files;
}

/** Zone de dépôt + bouton Parcourir (et Dossier) : appelle `onFiles` avec les fichiers choisis. */
export function FileDrop({ accept, multiple, folder, label, onFiles, busy, compact }: {
  accept: string;
  multiple?: boolean;
  /** Propose aussi de choisir un dossier entier (ses fichiers du bon type, sous-dossiers compris). */
  folder?: boolean;
  label: string;
  onFiles: (files: File[]) => void;
  busy?: boolean;
  compact?: boolean;
}) {
  const input = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const [over, setOver] = useState(false);
  const extensions = accept.split(",").map((item) => item.trim().toLowerCase()).filter((item) => item.startsWith("."));
  const keep = (files: File[]) =>
    files.filter((file) => !file.name.startsWith(".") && (!extensions.length || extensions.some((extension) => file.name.toLowerCase().endsWith(extension))));
  const deliver = (files: File[]) => {
    const kept = keep(files);
    if (kept.length) onFiles(multiple ? kept : kept.slice(0, 1));
  };

  useEffect(() => {
    folderInput.current?.setAttribute("webkitdirectory", "");
  }, []);

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setOver(false);
        if (busy) return;
        droppedFiles(event.dataTransfer).then(deliver);
      }}
      className={`flex flex-wrap items-center justify-center gap-3 rounded-[10px] border border-dashed px-4 ${compact ? "py-3" : "py-5"} text-center transition ${
        over ? "border-accent bg-accent-soft" : "border-line-dashed"
      }`}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin text-ink-subtle" aria-hidden /> : <Upload className="h-4 w-4 text-ink-subtle" aria-hidden />}
      <span className="text-sm text-ink-muted">{busy ? "Import en cours…" : label}</span>
      <button type="button" className="btn-soft btn-sm" disabled={busy} onClick={() => input.current?.click()}>
        Parcourir
      </button>
      {folder && (
        <button type="button" className="btn-ghost btn-sm" disabled={busy} onClick={() => folderInput.current?.click()}>
          <FolderOpen className="h-4 w-4" aria-hidden />
          Dossier
        </button>
      )}
      <input
        ref={input}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(event) => {
          deliver(Array.from(event.target.files ?? []));
          event.target.value = "";
        }}
      />
      {folder && (
        <input
          ref={folderInput}
          type="file"
          multiple
          className="hidden"
          onChange={(event) => {
            deliver(Array.from(event.target.files ?? []));
            event.target.value = "";
          }}
        />
      )}
    </div>
  );
}

export function FileRow({ name, meta, status, actions }: { name: string; meta?: ReactNode; status?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-[10px] border border-line bg-surface-2 px-3.5 py-2.5">
      <div className="min-w-[160px] flex-1">
        <div className="break-words text-sm font-medium text-ink">{name}</div>
        {meta && <div className="mt-0.5 text-xs text-ink-subtle">{meta}</div>}
      </div>
      {status}
      {actions}
    </div>
  );
}

export function BusyButton({ busy, children, className = "btn-primary", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button type="button" className={className} disabled={busy || props.disabled} {...props}>
      {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-12 text-center">
      <h2 className="text-lg font-bold text-ink">{title}</h2>
      {children && <p className="max-w-[520px] text-sm leading-normal text-ink-muted">{children}</p>}
      {action}
    </div>
  );
}
