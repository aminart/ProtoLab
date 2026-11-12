/**
 * Lecteur du prototype : affiche un écran du modèle et le fait fonctionner (champs, boutons,
 * listes liées aux données, navigation). Un seul magasin de données pour tout le prototype :
 * ce que le participant crée sur un écran se retrouve sur les suivants. « Réinitialiser » repart
 * du jeu de départ figé.
 *
 * Styles en ligne uniquement (pas de Tailwind) : le même composant sert dans l'app et dans
 * l'export HTML autonome.
 */
import { forwardRef, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { branchTarget, cloneSeed, coerce, formatValue, validate } from "./engine";
import type { Action, DataRecord, Model, PNode, Screen } from "./types";

export interface PlayerHandle {
  goTo: (screenId: string) => void;
  reset: () => void;
}

interface PlayerState {
  screen: string;
  history: string[];
  data: Record<string, DataRecord[]>;
  current: Record<string, string>;
  forms: Record<string, Record<string, string | boolean>>;
  errors: Record<string, Record<string, string>>;
}

interface RenderContext {
  key: string;
  record?: { entity: string; record: DataRecord; fields: Record<string, string>; target: string | null; isRoot: boolean };
  input?: PNode;
  inControl?: boolean;
}

function initialState(model: Model, screen?: string | null): PlayerState {
  return {
    screen: screen && model.screens.some((s) => s.id === screen) ? screen : model.start ?? model.screens[0]?.id ?? "",
    history: [],
    data: cloneSeed(model.seed),
    current: {},
    forms: {},
    errors: {},
  };
}

function playerCss(primary: string): string {
  return `
.pl-root{--pl-primary:${primary}}
.pl-root *{box-sizing:border-box}
.pl-input{border:0;background:transparent;outline:none;padding:0;margin:0;font:inherit;letter-spacing:inherit;resize:none}
.pl-input::placeholder{color:var(--pl-ph,#98A2B3);opacity:1}
.pl-field:focus-within{box-shadow:0 0 0 2px var(--pl-primary) !important}
.pl-click{cursor:pointer}
.pl-click:hover{filter:brightness(0.96)}
.pl-click:focus-visible{outline:2px solid var(--pl-primary);outline-offset:2px}
.pl-hotspots .pl-click{outline:2px dashed rgba(47,84,235,.55);outline-offset:1px}
`;
}

export const Player = forwardRef<PlayerHandle, {
  model: Model;
  initialScreen?: string | null;
  showHotspots?: boolean;
  onScreenChange?: (screenId: string) => void;
}>(function Player({ model, initialScreen, showHotspots, onScreenChange }, ref) {
  const [state, setState] = useState<PlayerState>(() => initialState(model, initialScreen));
  const stateRef = useRef(state);
  stateRef.current = state;

  const screens = useMemo(() => new Map(model.screens.map((screen) => [screen.id, screen])), [model]);
  const entities = useMemo(() => new Map(model.entities.map((entity) => [entity.name, entity])), [model]);

  useEffect(() => {
    // A new model (regenerated prototype): keep the screen when it still exists, restart the data.
    setState((current) => initialState(model, current.screen));
  }, [model]);

  useEffect(() => {
    onScreenChange?.(state.screen);
  }, [state.screen, onScreenChange]);

  const go = useCallback((target: string | null | undefined) => {
    if (!target || !screens.has(target)) return;
    setState((current) => (current.screen === target ? current : { ...current, screen: target, history: [...current.history, current.screen] }));
  }, [screens]);

  const back = useCallback(() => {
    setState((current) => {
      if (!current.history.length) return current;
      const history = current.history.slice(0, -1);
      return { ...current, screen: current.history[current.history.length - 1], history };
    });
  }, []);

  useImperativeHandle(ref, () => ({
    goTo: (screenId: string) => setState((current) => ({ ...current, screen: screenId, history: [...current.history, current.screen] })),
    reset: () => setState(initialState(model)),
  }), [model]);

  const screen = screens.get(state.screen);

  // --- Actions -----------------------------------------------------------------------------

  const validateScreen = (target: Screen): Record<string, string> => {
    const errors: Record<string, string> = {};
    const values = stateRef.current.forms[target.id] ?? {};
    for (const [nodeId, rule] of Object.entries(target.behaviors.fields ?? {})) {
      const message = validate(String(values[nodeId] ?? ""), rule);
      if (message) errors[nodeId] = message;
    }
    return errors;
  };

  const runAction = (action: Action, record?: DataRecord) => {
    if (!screen) return;
    const snapshot = stateRef.current;
    const entity = action.entity;
    if (action.type === "navigate") return go(action.target);
    if (action.type === "back") return back();
    if (action.type === "submit") {
      const errors = validateScreen(screen);
      if (Object.keys(errors).length) {
        setState((current) => ({ ...current, errors: { ...current.errors, [screen.id]: errors } }));
        return;
      }
      const values = snapshot.forms[screen.id] ?? {};
      let next = snapshot.data;
      let current = snapshot.current;
      let created: Record<string, unknown> = {};
      if (entity) {
        created = { id: `${entity}_${Date.now().toString(36)}` };
        for (const [nodeId, rule] of Object.entries(screen.behaviors.fields ?? {})) {
          if (rule.entity === entity && rule.field) created[rule.field] = coerce(String(values[nodeId] ?? ""), rule);
        }
        Object.assign(created, action.set ?? {});
        next = { ...snapshot.data, [entity]: [created as DataRecord, ...(snapshot.data[entity] ?? [])] };
        current = { ...snapshot.current, [entity]: String(created.id) };
      }
      const target = branchTarget(created, action.branches) ?? action.target;
      setState((state) => ({
        ...state,
        data: next,
        current,
        forms: { ...state.forms, [screen.id]: {} },
        errors: { ...state.errors, [screen.id]: {} },
        ...(target && screens.has(target) ? { screen: target, history: [...state.history, state.screen] } : {}),
      }));
      return;
    }
    if (!entity) return go(action.target);
    const recordId = record?.id ?? snapshot.current[entity] ?? snapshot.data[entity]?.[0]?.id;
    if (action.type === "delete") {
      setState((state) => ({
        ...state,
        data: { ...state.data, [entity]: (state.data[entity] ?? []).filter((item) => item.id !== recordId) },
        current: { ...state.current, [entity]: "" },
      }));
      return action.target ? go(action.target) : back();
    }
    if (action.type === "set") {
      setState((state) => ({
        ...state,
        data: { ...state.data, [entity]: (state.data[entity] ?? []).map((item) => (item.id === recordId ? { ...item, ...(action.set ?? {}) } : item)) },
      }));
      const updated = { ...(snapshot.data[entity] ?? []).find((item) => item.id === recordId), ...(action.set ?? {}) };
      return go(branchTarget(updated, action.branches) ?? action.target);
    }
  };

  const onClickNode = (node: PNode, ctx: RenderContext) => {
    if (!screen) return;
    const action = screen.behaviors.actions?.[node.id];
    if (ctx.record) {
      setState((current) => ({ ...current, current: { ...current.current, [ctx.record!.entity]: ctx.record!.record.id } }));
    }
    if (action) return runAction(action, ctx.record?.record);
    if (node.role === "checkbox") {
      setState((current) => {
        const form = current.forms[screen.id] ?? {};
        return { ...current, forms: { ...current.forms, [screen.id]: { ...form, [node.id]: !form[node.id] } } };
      });
      return;
    }
    if (ctx.record?.isRoot && ctx.record.target) return go(ctx.record.target);
    const nav = node.nav;
    if (!nav) return;
    if (nav.kind === "back") return back();
    if (nav.kind === "url" && nav.url) {
      window.open(nav.url, "_blank", "noopener");
      return;
    }
    go(nav.screen);
  };

  const setValue = (nodeId: string, value: string) => {
    if (!screen) return;
    setState((current) => {
      const form = current.forms[screen.id] ?? {};
      const errors = { ...(current.errors[screen.id] ?? {}) };
      delete errors[nodeId];
      return { ...current, forms: { ...current.forms, [screen.id]: { ...form, [nodeId]: value } }, errors: { ...current.errors, [screen.id]: errors } };
    });
  };

  const checkOnBlur = (nodeId: string) => {
    if (!screen) return;
    const rule = screen.behaviors.fields?.[nodeId];
    const value = String(stateRef.current.forms[screen.id]?.[nodeId] ?? "");
    if (!rule || !value.trim()) return;
    const message = validate(value, rule);
    if (message) setState((current) => ({ ...current, errors: { ...current.errors, [screen.id]: { ...(current.errors[screen.id] ?? {}), [nodeId]: message } } }));
  };

  // --- Rendering ---------------------------------------------------------------------------------

  if (!screen) {
    return <div style={{ padding: 24, fontFamily: "system-ui, sans-serif", color: "#475467" }}>Aucun écran à afficher.</div>;
  }

  const behaviors = screen.behaviors;
  const values = state.forms[screen.id] ?? {};
  const errors = state.errors[screen.id] ?? {};
  const theme = model.theme;

  const currentRecord = (entity: string): DataRecord | undefined => {
    const list = state.data[entity] ?? [];
    return list.find((item) => item.id === state.current[entity]) ?? list[0];
  };

  const isClickable = (node: PNode, ctx: RenderContext): boolean =>
    Boolean(behaviors.actions?.[node.id] || node.nav || node.role === "checkbox" || (ctx.record?.isRoot && ctx.record.target));

  const renderText = (node: PNode, ctx: RenderContext): ReactNode => {
    let text = node.text ?? "";
    const listField = ctx.record?.fields[node.id];
    const binding = behaviors.bindings?.[node.id];
    if (ctx.record && listField) {
      text = formatValue(ctx.record.record[listField], entities.get(ctx.record.entity), listField);
    } else if (binding) {
      const record = currentRecord(binding.entity);
      if (record) text = formatValue(record[binding.field], entities.get(binding.entity), binding.field);
    }
    if (ctx.input && ctx.input.input?.valueText === node.id) {
      const inputNode = ctx.input;
      const rule = behaviors.fields?.[inputNode.id];
      const style: CSSProperties = { ...(node.style as CSSProperties), color: theme.text, ["--pl-ph" as string]: node.style.color ?? "#98A2B3", minWidth: 0 };
      if (!node.style.width && !node.style.flex) style.width = "100%";
      const common = {
        className: "pl-input",
        style,
        value: String(values[inputNode.id] ?? ""),
        placeholder: inputNode.input?.placeholder ?? "",
        "aria-label": inputNode.input?.label || inputNode.name,
        "aria-invalid": Boolean(errors[inputNode.id]),
        onChange: (event: { target: { value: string } }) => setValue(inputNode.id, event.target.value),
        onBlur: () => checkOnBlur(inputNode.id),
      };
      if (inputNode.input?.multiline || rule?.format === "long_text") return <textarea key={ctx.key + node.id} rows={3} {...common} />;
      const secret = /mot de passe|password|mdp/i.test(`${inputNode.input?.label ?? ""} ${inputNode.name}`);
      const type = secret ? "password" : rule?.format === "email" ? "email" : rule?.format === "date" ? "date" : rule?.format === "phone" ? "tel" : "text";
      return <input key={ctx.key + node.id} type={type} inputMode={rule?.format === "number" ? "decimal" : undefined} {...common} />;
    }
    return (
      <div key={ctx.key + node.id} style={node.style as CSSProperties}>
        {text}
      </div>
    );
  };

  const renderNode = (node: PNode, ctx: RenderContext): ReactNode => {
    if (node.type === "text") return renderText(node, ctx);
    let style: CSSProperties = { ...(node.style as CSSProperties) };
    const key = ctx.key + node.id;

    if (node.type === "svg") {
      return (
        <svg key={key} style={style} viewBox={node.viewBox} preserveAspectRatio="none" aria-hidden>
          {(node.paths ?? []).map((path, index) => (
            <path key={index} d={path.d} fill={path.fill ?? "none"} fillRule={path.rule === "evenodd" ? "evenodd" : "nonzero"} />
          ))}
        </svg>
      );
    }

    let childCtx: RenderContext = ctx.record?.isRoot ? { ...ctx, record: { ...ctx.record, isRoot: false } } : ctx;
    let className: string | undefined;
    const extra: ReactNode[] = [];

    if (node.role === "input" && !ctx.inControl && !ctx.record) {
      childCtx = { ...childCtx, input: node, inControl: true };
      const error = errors[node.id];
      if (error) {
        if (style.height) {
          style.minHeight = style.height;
          delete style.height;
        }
        extra.push(
          <div key={key + ":error"} role="alert" style={{ color: theme.danger, fontSize: 13, lineHeight: "18px", fontFamily: theme.font, alignSelf: "stretch", marginTop: 2 }}>
            {error}
          </div>,
        );
      }
    }
    if (ctx.input && ctx.input.input?.box === node.id) {
      className = "pl-field";
      if (errors[ctx.input.id]) style = { ...style, boxShadow: `inset 0 0 0 1.5px ${theme.danger}` };
    }
    if (node.role === "checkbox" && values[node.id]) {
      if (!style.position) style.position = "relative";
      extra.push(
        <svg key={key + ":check"} viewBox="0 0 24 24" aria-hidden style={{ position: "absolute", left: 2, top: "50%", width: 18, height: 18, transform: "translateY(-50%)" }}>
          <rect x="1" y="1" width="22" height="22" rx="5" fill={theme.primary} />
          <path d="M6 12.5l4 4 8-9" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>,
      );
    }
    if (node.image) {
      if (!style.position) style.position = "relative";
      extra.push(
        <svg key={key + ":image"} viewBox="0 0 24 24" aria-hidden style={{ position: "absolute", left: "50%", top: "50%", width: 28, height: 28, transform: "translate(-50%, -50%)", opacity: 0.55 }}>
          <rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="#475467" strokeWidth="1.6" />
          <circle cx="9" cy="10" r="1.8" fill="#475467" />
          <path d="M4 18l5.5-5.5 4 4 3-3L20 17" fill="none" stroke="#475467" strokeWidth="1.6" />
        </svg>,
      );
    }

    // A list bound to the data: the first item is the template, repeated for each record.
    const list = !ctx.record ? behaviors.lists?.[node.id] : undefined;
    let children: ReactNode[];
    if (list) {
      const template = node.children?.find((child) => child.id === list.template);
      const records = state.data[list.entity] ?? [];
      children = [];
      for (const child of node.children ?? []) {
        if (child.id === list.template && template) {
          if (!records.length) {
            children.push(
              <div key={key + ":empty"} style={{ color: "#667085", fontStyle: "italic", fontSize: 14, fontFamily: theme.font, padding: "8px 0" }}>
                Aucun élément
              </div>,
            );
          }
          for (const record of records) {
            children.push(renderNode(template, { ...childCtx, key: `${key}/${record.id}/`, record: { entity: list.entity, record, fields: list.fields, target: list.target, isRoot: true } }));
          }
        } else if (!list.items.includes(child.id)) {
          children.push(renderNode(child, childCtx));
        }
      }
    } else {
      children = (node.children ?? []).map((child) => renderNode(child, childCtx));
    }

    const clickable = isClickable(node, ctx) && !(ctx.inControl && node.role !== "checkbox");
    if (clickable) {
      className = className ? `${className} pl-click` : "pl-click";
      return (
        <div
          key={key}
          className={className}
          style={style}
          role="button"
          tabIndex={0}
          aria-label={node.role === "checkbox" ? node.name : undefined}
          aria-pressed={node.role === "checkbox" ? Boolean(values[node.id]) : undefined}
          onClick={(event) => {
            event.stopPropagation();
            onClickNode(node, ctx);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              event.stopPropagation();
              onClickNode(node, ctx);
            }
          }}
        >
          {children}
          {extra}
        </div>
      );
    }
    return (
      <div key={key} className={className} style={style}>
        {children}
        {extra}
      </div>
    );
  };

  return (
    <div className={`pl-root${showHotspots ? " pl-hotspots" : ""}`} data-screen={screen.id}>
      <style>{playerCss(theme.primary)}</style>
      {screen.root ? renderNode(screen.root, { key: "" }) : <DeducedScreen screen={screen} model={model} onGo={go} onBack={back} canGoBack={state.history.length > 0} />}
    </div>
  );
});

/** Écran prévu par le flow mais absent de la maquette : version simple, aux couleurs du design system. */
function DeducedScreen({ screen, model, onGo, onBack, canGoBack }: { screen: Screen; model: Model; onGo: (id: string) => void; onBack: () => void; canGoBack: boolean }) {
  const theme = model.theme;
  const names = new Map(model.screens.map((item) => [item.id, item.name]));
  const button: CSSProperties = {
    minHeight: 44, padding: "0 18px", borderRadius: 8, border: 0, background: theme.primary, color: "#FFFFFF",
    font: `600 15px ${theme.font}`, cursor: "pointer", textAlign: "left",
  };
  return (
    <div style={{ width: screen.width, minHeight: screen.height, background: theme.background, color: theme.text, fontFamily: theme.font, padding: 32, display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <span style={{ alignSelf: "flex-start", fontSize: 12, fontWeight: 600, letterSpacing: ".04em", textTransform: "uppercase", padding: "3px 10px", borderRadius: 999, background: "rgba(16,24,40,.06)", color: "#475467" }}>
          Écran sans maquette
        </span>
        <h1 style={{ margin: 0, fontSize: 26, lineHeight: 1.2 }}>{screen.name}</h1>
        <p style={{ margin: 0, fontSize: 15, lineHeight: 1.5, color: "#475467" }}>Cet écran est prévu par le parcours ; sa maquette reste à faire.</p>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10, maxWidth: 420 }}>
        {screen.links.map((link, index) => (
          <button key={index} type="button" style={button} onClick={() => onGo(link.target)}>
            {link.label || names.get(link.target) || link.target}
            {link.conditions.length > 0 && (
              <span style={{ display: "block", fontWeight: 400, fontSize: 13, opacity: 0.85 }}>
                si {link.conditions.map((c) => `${c.decision} ${c.answer}`).join(", ")}
              </span>
            )}
          </button>
        ))}
        {canGoBack && (
          <button type="button" onClick={onBack} style={{ ...button, background: "transparent", color: theme.primary, padding: 0 }}>
            ← Retour
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * Met l'écran à l'échelle de la place disponible : « width » réduit un écran trop large (jamais
 * d'agrandissement), « none » le laisse à 100 %.
 */
export function ScaledFrame({ width, children, fit = "width", maxScale = 1 }: { width: number; children: ReactNode; fit?: "width" | "none"; maxScale?: number }) {
  const outer = useRef<HTMLDivElement>(null);
  const inner = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [available, setAvailable] = useState(width);
  const [height, setHeight] = useState<number | undefined>(undefined);

  useLayoutEffect(() => {
    const update = () => {
      const room = outer.current?.clientWidth ?? width;
      const next = fit === "none" ? 1 : Math.min(maxScale, room / Math.max(width, 1));
      setAvailable(room);
      setScale(next);
      setHeight((inner.current?.scrollHeight ?? 0) * next);
    };
    update();
    const observer = new ResizeObserver(update);
    if (outer.current) observer.observe(outer.current);
    if (inner.current) observer.observe(inner.current);
    return () => observer.disconnect();
  }, [width, fit, maxScale]);

  return (
    <div ref={outer} style={{ width: "100%", height, overflow: "hidden" }}>
      <div
        ref={inner}
        style={{ width, transform: `scale(${scale})`, transformOrigin: "top left", marginLeft: Math.max(0, (available - width * scale) / 2) }}
      >
        {children}
      </div>
    </div>
  );
}
