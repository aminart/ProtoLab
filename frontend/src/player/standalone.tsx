/** Point d'entrée de l'export HTML : le modèle figé est posé dans window.__PROTOLAB_MODEL__. */
import { createRoot } from "react-dom/client";
import { TestShell } from "./TestShell";
import type { Model } from "./types";

declare global {
  interface Window {
    __PROTOLAB_MODEL__?: Model;
  }
}

const container = document.getElementById("protolab-player");
const model = window.__PROTOLAB_MODEL__;
if (container && model) {
  document.title = document.title || model.project;
  createRoot(container).render(<TestShell model={model} />);
}
