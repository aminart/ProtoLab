/**
 * Mode test : le prototype seul, en plein écran, pour un participant. Les commandes de
 * l'animateur (réinitialiser, aller à un écran, quitter) restent discrètes, en bas à droite.
 * Utilisé dans l'app et dans l'export HTML autonome : styles en ligne uniquement.
 */
import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { Player, ScaledFrame, type PlayerHandle } from "./Player";
import type { Model } from "./types";

const FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
const control: CSSProperties = {
  minHeight: 36, padding: "0 12px", borderRadius: 8, border: "1px solid rgba(16,24,40,.14)", background: "#FFFFFF", color: "#1D2939",
  font: `500 13px ${FONT}`, cursor: "pointer", boxShadow: "0 1px 2px rgba(16,24,40,.08)",
};

export function TestShell({ model, onExit }: { model: Model; onExit?: () => void }) {
  const player = useRef<PlayerHandle>(null);
  const [screen, setScreen] = useState(model.start ?? model.screens[0]?.id ?? "");
  const [confirmReset, setConfirmReset] = useState(false);
  const [open, setOpen] = useState(false);
  const width = model.screens.find((item) => item.id === screen)?.width ?? 390;

  useEffect(() => {
    if (!confirmReset) return;
    const timer = window.setTimeout(() => setConfirmReset(false), 4000);
    return () => window.clearTimeout(timer);
  }, [confirmReset]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [screen]);

  const onScreenChange = useCallback((id: string) => setScreen(id), []);

  const reset = () => {
    if (!confirmReset) {
      setConfirmReset(true);
      return;
    }
    player.current?.reset();
    setConfirmReset(false);
    setOpen(false);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#E4E7EC", display: "flex", justifyContent: "center", fontFamily: FONT }}>
      <div style={{ width: "100%", maxWidth: Math.max(width, 390), alignSelf: "flex-start", margin: width < 900 ? "24px 0 72px" : 0,
        boxShadow: width < 900 ? "0 0 0 1px rgba(16,24,40,.06), 0 12px 40px rgba(16,24,40,.12)" : undefined }}>
        <ScaledFrame width={width}>
          <Player ref={player} model={model} onScreenChange={onScreenChange} />
        </ScaledFrame>
      </div>

      <div style={{ position: "fixed", right: 12, bottom: 12, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8, zIndex: 10 }}>
        {open && (
          <div style={{ background: "#FFFFFF", borderRadius: 10, padding: 8, boxShadow: "0 8px 30px rgba(16,24,40,.18)", maxHeight: "60vh", overflow: "auto", minWidth: 240 }}>
            <div style={{ font: `600 12px ${FONT}`, color: "#667085", padding: "4px 8px", textTransform: "uppercase", letterSpacing: ".04em" }}>Aller à l’écran</div>
            {model.screens.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  player.current?.goTo(item.id);
                  setOpen(false);
                }}
                style={{ display: "block", width: "100%", textAlign: "left", padding: "8px", border: 0, borderRadius: 6, cursor: "pointer",
                  background: item.id === screen ? "#EEF0FB" : "transparent", color: "#1D2939", font: `400 14px ${FONT}` }}
              >
                {item.name}
              </button>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, opacity: open || confirmReset ? 1 : 0.55 }}>
          <button type="button" style={control} onClick={() => setOpen((value) => !value)} aria-expanded={open}>
            Écrans
          </button>
          <button type="button" style={{ ...control, ...(confirmReset ? { background: "#B42318", color: "#FFFFFF", borderColor: "#B42318" } : {}) }} onClick={reset}>
            {confirmReset ? "Confirmer la réinitialisation" : "Réinitialiser"}
          </button>
          {onExit && (
            <button type="button" style={control} onClick={onExit}>
              Quitter le test
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
