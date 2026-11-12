import nightNavy from "night-navy/tailwind-v3-preset";

/**
 * Couleurs, police et arrondis : design system commun Night Navy (github:aminart/Design-system-).
 * Pour du texte, utiliser text-accent (text-navy suit le fond du bouton principal, trop foncé en sombre).
 * Le lecteur de prototype (src/player) n'utilise pas Tailwind : il garde les styles de la maquette.
 */
/** @type {import('tailwindcss').Config} */
export default {
  presets: [nightNavy],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
};
