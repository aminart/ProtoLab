# Portail des demandes

## Contexte métier
Les salariés déposent des demandes d'achat. Une demande a un objet, un montant en euros et un statut
(Brouillon, En attente, Validée, Refusée). Au-delà de 500 €, la demande passe par la validation du manager.

## Profils
- **Demandeur** : crée et suit ses demandes.
- **Manager** : valide les demandes de plus de 500 €.

## Structure de l'app

```mermaid
flowchart TD
  debut((Début)) --> ecran_connexion[Connexion]
  subgraph acces [Accès]
    ecran_connexion -->|Mot de passe oublié| ecran_mot_de_passe[Mot de passe oublié]
    ecran_mot_de_passe -->|Retour| ecran_connexion
  end
  subgraph demandes [Demandes]
    ecran_liste[Liste des demandes] -->|Nouvelle demande| ecran_nouvelle[Nouvelle demande]
    ecran_nouvelle -->|Envoyer| verif{Montant > 500 € ?}
    verif -- Oui --> notif(Notification du manager) --> ecran_confirmation[Confirmation]
    verif -- Non --> ecran_confirmation
    ecran_confirmation -->|Retour à la liste| ecran_liste
  end
  ecran_connexion -->|Se connecter| ecran_liste
```

## Fonctionnalités
Le demandeur voit la liste de ses demandes, en crée une nouvelle et reçoit une confirmation.
