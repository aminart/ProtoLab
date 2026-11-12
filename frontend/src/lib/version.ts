// Version de l'app : fichier VERSION à la racine du dépôt (source unique, aussi lue par le backend et l'exe).
import rawVersion from "../../../VERSION?raw";

export const APP_VERSION = rawVersion.trim();
