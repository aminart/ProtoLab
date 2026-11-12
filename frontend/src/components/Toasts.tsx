import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { AlertCircle, CheckCircle2, Info, X } from "lucide-react";

type ToastTone = "success" | "error" | "info";
interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

const ToastContext = createContext<(tone: ToastTone, message: string) => void>(() => {});

export function useToast() {
  return useContext(ToastContext);
}

const STYLES: Record<ToastTone, { icon: typeof Info; className: string }> = {
  success: { icon: CheckCircle2, className: "text-success" },
  error: { icon: AlertCircle, className: "text-danger-text" },
  info: { icon: Info, className: "text-accent" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), []);

  const push = useCallback(
    (tone: ToastTone, message: string) => {
      const id = Date.now() + Math.random();
      setToasts((current) => [...current, { id, tone, message }]);
      window.setTimeout(() => dismiss(id), tone === "error" ? 10000 : 4000);
    },
    [dismiss],
  );

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[min(380px,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
        {toasts.map((toast) => {
          const { icon: Icon, className } = STYLES[toast.tone];
          return (
            <div key={toast.id} className="pointer-events-auto flex items-start gap-3 rounded-xl border border-line bg-surface p-3 shadow-lg">
              <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${className}`} aria-hidden />
              <p className="flex-1 text-sm text-ink-body">{toast.message}</p>
              <button type="button" onClick={() => dismiss(toast.id)} className="text-ink-subtle hover:text-ink-body" aria-label="Fermer">
                <X className="h-4 w-4" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}
