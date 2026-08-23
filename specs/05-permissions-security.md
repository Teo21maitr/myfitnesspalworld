# 05 — Permissions, sécurité et confidentialité

## 1. Principe fondamental

Toute donnée est privée par défaut.

Un utilisateur actif peut accéder :

- à ses propres données ;
- aux ressources globales en lecture ;
- aux ressources explicitement partagées avec lui ;
- aux ressources marquées `app_users`.

Toutes les vérifications se font côté backend.

## 2. États de compte

### ACTIVE

Accès normal.

### PENDING

Pas d'accès aux fonctions métier. Écran d'attente seulement si un compte existe temporairement dans ce statut.

### SUSPENDED

- connexion interdite ;
- sessions invalidées ;
- données conservées ;
- anciens partages rendus inaccessibles.

### REJECTED

Pas de User persistant recommandé. RegistrationRequest supprimée après refus.

## 3. Rôles

Seulement :

- utilisateur normal ;
- admin/staff.

Pas de rôle métier intermédiaire dans la V1.

## 4. Admin

L'admin peut :

- accepter/refuser demandes ;
- suspendre/réactiver ;
- forcer reset mot de passe ;
- consulter données ;
- gérer imports CIQUAL ;
- gérer produits cache ;
- consulter logs IA ;
- activer/désactiver IA ;
- gérer configuration globale ;
- consulter notifications/emails.

L'admin ne peut jamais lire le mot de passe actuel.

## 5. Authentification

Architecture recommandée :

- access token court ;
- refresh token long ;
- cookies `HttpOnly` ;
- `Secure` en production ;
- `SameSite` adapté à l'architecture frontend/backend ;
- protection CSRF ;
- access ~15 minutes ;
- session refresh ~30 jours ;
- pas de « se souvenir de moi » séparé ;
- logout appareil courant ;
- logout all devices.

Ne jamais stocker un token d'authentification sensible dans `localStorage`.

## 6. Foods

### CIQUAL

- lecture : tous actifs ;
- création : import/admin ;
- modification/désactivation : admin.

### OFF cache

- lecture : tous actifs ;
- création : backend ;
- modification : backend/admin.

### User food

- owner : CRUD ;
- autre utilisateur : lecture uniquement si partage ;
- jamais modifier l'original d'un autre utilisateur.

## 7. Recettes / repas

Owner :

- CRUD ;
- partage.

Destinataire :

- lecture seule ;
- copie possible ;
- copie indépendante.

## 8. Journal

- privé par défaut ;
- partage lecture seule ;
- partage peut donner accès à toutes les dates tant qu'il existe ;
- partage d'une journée spécifique peut être supporté ;
- aucun utilisateur tiers ne peut créer/modifier/supprimer une entrée.

## 9. Progression

Partage séparé du journal.

Photos exclues de tout partage.

## 10. Photos privées

- stockage privé ;
- pas d'URL publique permanente ;
- accès via autorisation backend puis URL signée courte ;
- suppression fichier lors de suppression de la photo/du compte ;
- noms de clés non prédictibles.

## 11. Suppression

Compte :

- confirmation username exacte ;
- suppression immédiate ;
- données et fichiers supprimés ;
- sessions révoquées ;
- partages supprimés ;
- relations sociales supprimées.

Recette/aliment personnel/repas :

- soft delete conseillé si nécessaire pour historique ;
- snapshots de journal conservés.

## 12. Sécurité API

Chaque endpoint doit :

- filtrer queryset par utilisateur ;
- vérifier l'ownership ;
- vérifier l'état ACTIVE ;
- empêcher IDOR ;
- valider les payloads ;
- appliquer rate limit aux endpoints sensibles/IA ;
- ne jamais accepter `owner_id` du frontend comme source de vérité.

## 13. CORS / CSRF

Production :

- allowlist stricte du domaine frontend ;
- pas de `*` ;
- cookies `Secure` ;
- CSRF trusted origins configurés ;
- HTTPS uniquement.

Local :

- uniquement origines locales nécessaires.

## 14. Uploads

Valider :

- taille maximale ;
- MIME ;
- extension ;
- contenu minimalement cohérent ;
- nombre de fichiers ;
- ownership.

Les fichiers temporaires doivent être supprimés même en cas d'erreur.

## 15. Logs

Interdit :

- mot de passe ;
- secret ;
- API key ;
- token ;
- cookie auth ;
- image privée ;
- audio brut.

Autorisé :

- id utilisateur interne ;
- type de tâche ;
- provider/model ;
- statut ;
- durée ;
- erreur nettoyée ;
- coût approximatif.

## 16. Périmètre santé

Les objectifs calculés sont des estimations.

L'application ne doit pas se présenter comme un professionnel de santé ni afficher une recommandation médicale certaine.

Les valeurs externes doivent indiquer leur source.
