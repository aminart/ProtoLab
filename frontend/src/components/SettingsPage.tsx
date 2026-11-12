import { useEffect, useRef, useState, type ReactNode } from "react";
import { AlertCircle, ArrowRight, Check, Eye, EyeOff, Info, Lock, Plus, ShieldAlert, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/files";
import type { ConnectionSettings, ConnectionTest, SettingsField, SettingsForm } from "../lib/types";
import { useToast } from "./Toasts";

const EXPIRY_WARNING_DAYS = 30;

function TextInput({
  id,
  value,
  onChange,
  type = "text",
  placeholder,
  disabled,
  invalid,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
}) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      placeholder={placeholder}
      disabled={disabled}
      aria-invalid={invalid || undefined}
      onChange={(event) => onChange(event.target.value)}
      className={`min-h-[44px] w-full min-w-0 rounded-lg border bg-surface px-3.5 text-[15px] text-ink placeholder:text-ink-subtle focus:outline-none focus:ring-[3px] focus:ring-navy-soft disabled:bg-surface-3 disabled:text-ink-muted ${
        invalid ? "border-[1.5px] border-danger focus:border-danger" : "border-line-strong focus:border-accent"
      }`}
    />
  );
}

function SettingsField({ label, htmlFor, hint, children }: { label: string; htmlFor?: string; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      {htmlFor ? (
        <label htmlFor={htmlFor} className="text-[15px] font-medium">
          {label}
        </label>
      ) : (
        <span className="text-[15px] font-medium">{label}</span>
      )}
      {children}
      {hint && <p className="text-[13px] text-ink-subtle">{hint}</p>}
    </div>
  );
}

function expiryStatus(expiresAt: string | undefined): { label: string; tone: "muted" | "warning" | "error" } | null {
  if (!expiresAt) return null;
  const expires = new Date(expiresAt);
  const daysLeft = (expires.getTime() - Date.now()) / 86_400_000;
  const date = expires.toLocaleDateString("fr-FR");
  if (daysLeft < 0) return { label: `expiré depuis le ${date}`, tone: "error" };
  if (daysLeft < EXPIRY_WARNING_DAYS) return { label: `expire bientôt, le ${date}`, tone: "warning" };
  return { label: `expire le ${date}`, tone: "muted" };
}

export function SettingsPage({ onSaved, onLater }: { onSaved: (settings: ConnectionSettings, firstSetup: boolean) => void; onLater: () => void }) {
  const toast = useToast();
  const [saved, setSaved] = useState<ConnectionSettings | null>(null);
  const [apiBase, setApiBase] = useState("");
  // null = keep the stored key.
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [showKey, setShowKey] = useState(false);
  const [model, setModel] = useState("mistral");
  const [timeout, setTimeoutValue] = useState("300");
  const [test, setTest] = useState<ConnectionTest | null>(null);
  const [busy, setBusy] = useState<"test" | "save" | "certificate" | "clear" | null>(null);
  const certificateInput = useRef<HTMLInputElement>(null);
  // Decided once when the screen opens, so importing the certificate does not end the "first launch" flow.
  const [isFirstSetup, setIsFirstSetup] = useState(false);

  const applySaved = (settings: ConnectionSettings) => {
    setSaved(settings);
    setApiBase(settings.api_base);
    setApiKey(settings.has_api_key ? null : "");
    setModel(settings.model);
    setTimeoutValue(String(settings.timeout));
    setTest(settings.last_test);
  };

  useEffect(() => {
    api
      .settings()
      .then((settings) => {
        setIsFirstSetup(!settings.configured);
        applySaved(settings);
      })
      .catch((error: Error) => toast("error", error.message));
  }, [toast]);

  if (!saved) {
    return <main className="mx-auto max-w-[760px] px-6 py-12 text-ink-muted">Chargement des paramètres…</main>;
  }

  const fromEnv = (field: SettingsField) => saved.env_fields.includes(field);
  const form: SettingsForm = { api_base: apiBase, api_key: apiKey, model, timeout: Number(timeout) || 300 };
  const hasKey = apiKey === null ? saved.has_api_key : apiKey.trim().length > 0;
  const isComplete = Boolean(apiBase.trim()) && hasKey && Boolean(saved.certificate);
  const isDirty = apiBase !== saved.api_base || apiKey !== null && (apiKey !== "" || saved.has_api_key) || model !== saved.model || Number(timeout) !== saved.timeout;
  const failedField = test && !test.ok ? test.field : null;
  const expiry = expiryStatus(saved.certificate?.expires_at);

  const run = async (kind: NonNullable<typeof busy>, action: () => Promise<void>) => {
    setBusy(kind);
    try {
      await action();
    } catch (error) {
      toast("error", (error as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const handleCertificate = (file: File) =>
    run("certificate", async () => {
      const settings = await api.uploadCertificate(file);
      setSaved(settings);
      setTest(null);
    });

  const handleTest = () => run("test", async () => setTest(await api.testSettings(form)));

  const handleSave = () =>
    run("save", async () => {
      const settings = await api.saveSettings(form);
      applySaved({ ...settings, last_test: test ?? settings.last_test });
      onSaved(settings, isFirstSetup);
      if (!isFirstSetup) toast("success", "Paramètres enregistrés.");
      setIsFirstSetup(false);
    });

  const handleClear = () => {
    if (!window.confirm("Effacer l’URL, la clé API et le certificat enregistrés sur ce poste ?")) return;
    run("clear", async () => {
      const settings = await api.clearSettings();
      applySaved(settings);
      onSaved(settings, false);
      toast("info", "Paramètres effacés.");
    });
  };

  const envHint = "Défini par le fichier .env";

  return (
    <main className="mx-auto flex w-full max-w-[760px] flex-col gap-6 px-4 pb-16 pt-8 sm:px-6 sm:pt-12">
      {isFirstSetup && (
        <div className="flex gap-4 rounded-xl bg-navy-soft px-6 py-5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[10px] bg-navy">
            <ArrowRight className="h-5 w-5 text-white" aria-hidden />
          </span>
          <div>
            <h2 className="text-lg font-bold text-ink">Bienvenue dans ProtoLab</h2>
            <p className="mt-1 text-sm leading-normal text-ink-body">
              Configurez la connexion au service IA pour générer les données et les comportements du prototype. L’import des sources, la
              structure et la navigation fonctionnent déjà sans configuration.
            </p>
          </div>
        </div>
      )}

      {saved.env_fields.length > 0 && (
        <div className="flex gap-3 rounded-[10px] border border-line bg-surface px-5 py-4 text-[13px] leading-relaxed text-ink-muted">
          <Info className="mt-0.5 h-[18px] w-[18px] shrink-0" aria-hidden />
          <p>
            Certains paramètres sont fournis par le fichier <b className="font-medium text-ink-body">.env</b>
            {saved.env_file ? ` (${saved.env_file})` : ""} : ils sont prioritaires et ne sont pas modifiables ici.
          </p>
        </div>
      )}

      <section className="rounded-xl border border-line bg-surface shadow-[0_1px_3px_rgba(16,24,64,0.06)]">
        <div className="px-6 pb-2 pt-8 sm:px-10">
          <h1 className="text-[30px] font-bold leading-tight text-ink">Paramètres de connexion</h1>
          <p className="mt-2 text-sm leading-normal text-ink-muted">
            Ces informations sont fournies par votre service informatique. Elles restent enregistrées sur ce poste.
          </p>
        </div>

        <div className="flex flex-col gap-6 px-6 pb-8 pt-6 sm:px-10">
          {test?.ok && (
            <div role="status" className="flex items-center gap-3 rounded-lg border border-success-soft bg-success-soft px-4 py-3.5">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-success">
                <Check className="h-[13px] w-[13px] text-surface" strokeWidth={3.5} aria-hidden />
              </span>
              <div>
                <p className="text-[15px] font-medium text-success-text">{test.title}</p>
                <p className="mt-0.5 text-[13px] text-success-text">
                  Testée le {formatDateTime(test.at)} · {test.message}
                </p>
              </div>
            </div>
          )}

          {test?.ok && test.checks && test.checks.length > 0 && (
            <ul className="-mt-3 flex flex-col gap-2 rounded-lg border border-line bg-surface-2 px-4 py-3 text-[13px]">
              {test.checks.map((check) => (
                <li key={check.name} className="flex gap-2">
                  {check.ok ? (
                    <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" strokeWidth={3} aria-label="Conforme" />
                  ) : (
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-warning" aria-label="À ajuster" />
                  )}
                  <span className="text-ink-body">
                    <b className="font-medium">{check.name}</b> · {check.message}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <SettingsField label="URL du service" htmlFor="api-base" hint={fromEnv("api_base") ? envHint : undefined}>
            <TextInput
              id="api-base"
              type="url"
              value={apiBase}
              onChange={setApiBase}
              placeholder="https://llm.mon-entreprise.fr/v1"
              disabled={fromEnv("api_base")}
              invalid={failedField === "api_base"}
            />
          </SettingsField>

          {apiKey === null ? (
            <SettingsField
              label="Clé API"
              hint={fromEnv("api_key") ? envHint : "Chiffrée avec votre compte Windows : elle n’est jamais réaffichée en clair."}
            >
              <div
                className={`flex min-h-[48px] items-center gap-3 rounded-lg border bg-surface-2 pl-3.5 pr-2 ${
                  failedField === "api_key" ? "border-[1.5px] border-danger" : "border-line-strong"
                }`}
              >
                <Lock className="h-[18px] w-[18px] text-ink-muted" aria-hidden />
                <span className="flex-1 text-[15px] tracking-[0.08em] text-ink-body">•••• •••• •••• {saved.api_key_hint}</span>
                {!fromEnv("api_key") && (
                  <button
                    type="button"
                    onClick={() => setApiKey("")}
                    className="min-h-[36px] rounded-md border border-line-strong bg-surface px-3 text-[13px] font-medium text-ink hover:bg-surface-3"
                  >
                    Modifier
                  </button>
                )}
              </div>
            </SettingsField>
          ) : (
            <SettingsField label="Clé API" htmlFor="api-key">
              <div className="flex gap-2">
                <TextInput
                  id="api-key"
                  type={showKey ? "text" : "password"}
                  value={apiKey}
                  onChange={setApiKey}
                  placeholder="Collez votre clé API"
                  invalid={failedField === "api_key"}
                />
                <button
                  type="button"
                  onClick={() => setShowKey((current) => !current)}
                  aria-label={showKey ? "Masquer la clé" : "Afficher la clé"}
                  className="flex min-h-[44px] w-11 shrink-0 items-center justify-center rounded-lg border border-line-strong bg-surface hover:bg-surface-3"
                >
                  {showKey ? <EyeOff className="h-[18px] w-[18px] text-ink-muted" /> : <Eye className="h-[18px] w-[18px] text-ink-muted" />}
                </button>
              </div>
              {saved.has_api_key && (
                <button type="button" className="self-start text-[13px] font-medium text-accent underline" onClick={() => setApiKey(null)}>
                  Garder la clé enregistrée
                </button>
              )}
            </SettingsField>
          )}

          <SettingsField
            label="Certificat de l’entreprise"
            hint={
              fromEnv("ca_bundle")
                ? envHint
                : saved.certificate
                  ? undefined
                  : "Le fichier est copié dans l’application : vous pouvez ensuite le déplacer ou le supprimer."
            }
          >
            {saved.certificate ? (
              <div
                className={`flex items-center gap-3 rounded-lg bg-surface px-3.5 py-3 ${
                  failedField === "certificate" ? "border-[1.5px] border-danger" : "border border-line-strong"
                }`}
              >
                {failedField === "certificate" || expiry?.tone === "error" ? (
                  <ShieldAlert className="h-[22px] w-[22px] shrink-0 text-danger-text" strokeWidth={1.8} aria-hidden />
                ) : (
                  <ShieldCheck className="h-[22px] w-[22px] shrink-0 text-accent" strokeWidth={1.8} aria-hidden />
                )}
                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">{saved.certificate.name}</div>
                  <div className={`text-xs ${failedField === "certificate" || expiry?.tone === "error" ? "text-danger-text" : expiry?.tone === "warning" ? "text-warning-text" : "text-ink-muted"}`}>
                    {failedField === "certificate"
                      ? "Non reconnu par le serveur"
                      : [saved.certificate.imported_at && `Importé le ${new Date(saved.certificate.imported_at).toLocaleDateString("fr-FR")}`, expiry?.label]
                          .filter(Boolean)
                          .join(" · ")}
                  </div>
                </div>
                {!fromEnv("ca_bundle") && (
                  <button
                    type="button"
                    disabled={busy === "certificate"}
                    onClick={() => certificateInput.current?.click()}
                    className="min-h-[36px] rounded-md border border-line-strong bg-surface px-3 text-[13px] font-medium text-ink hover:bg-surface-3"
                  >
                    {busy === "certificate" ? "Import…" : "Remplacer"}
                  </button>
                )}
              </div>
            ) : (
              <button
                type="button"
                disabled={busy === "certificate"}
                onClick={() => certificateInput.current?.click()}
                className="flex min-h-[52px] items-center justify-center gap-2 rounded-lg border-[1.5px] border-dashed border-line-dashed text-sm font-medium text-accent hover:border-accent hover:bg-navy-softer"
              >
                <Plus className="h-[18px] w-[18px]" aria-hidden />
                {busy === "certificate" ? "Import…" : "Choisir le fichier .crt"}
              </button>
            )}
            <input
              ref={certificateInput}
              type="file"
              accept=".crt"
              className="hidden"
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) handleCertificate(file);
                event.target.value = "";
              }}
            />
          </SettingsField>

          <details className="border-t border-line pt-4">
            <summary className="cursor-pointer text-sm font-medium text-ink-muted hover:text-ink">
              Options avancées · modèle {model || "mistral"}, délai {timeout} s
            </summary>
            <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <SettingsField label="Modèle" htmlFor="model" hint={fromEnv("model") ? envHint : undefined}>
                <TextInput id="model" value={model} onChange={setModel} disabled={fromEnv("model")} />
              </SettingsField>
              <SettingsField label="Délai maximal (secondes)" htmlFor="timeout" hint={fromEnv("timeout") ? envHint : undefined}>
                <TextInput id="timeout" type="number" value={timeout} onChange={setTimeoutValue} disabled={fromEnv("timeout")} />
              </SettingsField>
            </div>
          </details>

          {test && !test.ok && (
            <div role="alert" className="flex gap-3 rounded-lg border border-danger-soft bg-danger-soft p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger-text" aria-hidden />
              <div>
                <p className="text-[15px] font-medium text-danger-text">{test.title}</p>
                <p className="mt-1 text-sm leading-normal text-ink-body">{test.message}</p>
              </div>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3 rounded-b-xl border-t border-line bg-surface-2 px-6 py-5 sm:px-10">
          {saved.configured && !isDirty ? (
            <>
              <button type="button" onClick={handleClear} disabled={busy !== null} className="min-h-[44px] px-1 text-sm font-medium text-danger-text underline">
                Effacer les paramètres
              </button>
              <span className="flex-[1_1_40px]" />
            </>
          ) : (
            <p className="flex-[1_1_200px] text-[13px] text-ink-subtle">
              {!isComplete
                ? "Renseignez les trois champs pour tester la connexion."
                : test && !test.ok
                  ? "Vous pouvez enregistrer malgré l’échec, la génération risque de ne pas fonctionner."
                  : "Testez la connexion avant d’enregistrer."}
            </p>
          )}
          <button type="button" className="btn-secondary" disabled={!isComplete || busy !== null} onClick={handleTest}>
            {busy === "test" ? "Test en cours (jusqu’à 3 min)…" : test && !test.ok ? "Tester à nouveau" : "Tester la connexion"}
          </button>
          {saved.configured && !isDirty ? (
            <button type="button" className="btn-primary" disabled>
              <Check className="h-[15px] w-[15px]" strokeWidth={3} aria-hidden /> Enregistré
            </button>
          ) : (
            <button type="button" className="btn-primary px-5" disabled={!isComplete || busy !== null} onClick={handleSave}>
              {busy === "save" ? "Enregistrement…" : isFirstSetup ? "Enregistrer et commencer" : "Enregistrer"}
            </button>
          )}
        </div>
      </section>

      {isFirstSetup ? (
        <button type="button" onClick={onLater} className="self-center text-sm font-medium text-accent hover:text-accent-ink">
          Configurer plus tard
        </button>
      ) : (
        <div className="flex gap-3 rounded-[10px] border border-line bg-surface px-5 py-4">
          <Info className="mt-0.5 h-[18px] w-[18px] shrink-0 text-ink-muted" aria-hidden />
          <p className="text-[13px] leading-relaxed text-ink-muted">
            Paramètres enregistrés dans <b className="font-medium text-ink-body">{saved.storage_dir}</b>. Pour un déploiement sur plusieurs postes, un fichier{" "}
            <b className="font-medium text-ink-body">.env</b> placé à côté de ProtoLab.exe est prioritaire sur cet écran.
          </p>
        </div>
      )}
    </main>
  );
}
