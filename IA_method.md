### 1. La méthode du "Premier Message" (La plus sûre)

À chaque fois que tu ouvres une nouvelle session ou que tu commences un gros bloc de travail, impose-lui une lecture de contrôle. Ne lui pose pas de question technique tout de suite.

**Ton prompt d'ouverture :**

> "Initialise-toi en lisant `.cursorrules` et `CONTEXT.md`. Confirme-moi uniquement par 'OK' quand tu es prêt à travailler sur le build du projet en respectant ces règles."

* **Pourquoi ça marche ?** Cela force l'agent à charger ces fichiers dans sa fenêtre de contexte active (sa mémoire de travail immédiate). S'il ne les trouve pas ou s'il y a une erreur, il te le dira tout de suite.

### 2. Le mécanisme d'auto-référence dans le système

Dans ton fichier `.cursorrules`, ajoute cette ligne tout en haut :
`CRITICAL: Always cross-reference instructions with CONTEXT.md before proposing any code change.`

Les outils comme AGY ou Cursor scannent prioritairement le fichier `.cursorrules` à chaque message envoyé par l'utilisateur. C'est l'équivalent d'une "instruction système" qui tourne en arrière-plan. Si ce fichier dit explicitement de regarder `CONTEXT.md`, l'agent le fera de manière quasi-instinctive.

### 3. La vérification par le "Test de Cohérence"

Si tu as un doute sur le fait qu'il utilise bien tes fichiers, pose-lui une question dont la réponse **ne se trouve que dans ton `CONTEXT.md**`.

**Exemple de test :**

> "Agent, quel est le nom exact de la colonne où je stocke les émojis de statut ?"

* **S'il répond `code_etat` :** C'est gagné, il utilise tes fichiers.
* **S'il répond `emoji` ou `status` :** Il hallucine ou utilise d'anciennes versions. Tu dois alors lui dire : *"Relis `CONTEXT.md`, tu n'utilises pas les bons noms de colonnes."*

---

### Pourquoi c'est le "Gold Standard" en Data Engineering ?

En structurant ton projet ainsi, tu crées ce qu'on appelle une **"Source Unique de Vérité" (SSOT)**.

1. **Économie :** L'agent ne "divague" pas. Il va droit au but car le cadre est fermé.
2. **Modularité :** Si demain Yoann veut changer la base de données pour une autre solution que Neon, tu n'as qu'à modifier **une ligne** dans `CONTEXT.md` au lieu de réexpliquer le changement à l'agent pendant 10 minutes.
3. **Transfert :** Si un jour tu travailles avec un autre consultant sur ce repo, il lui suffira de lire ces deux fichiers pour comprendre comment l'agent doit être utilisé pour maintenir le code.

**Résumé de l'emplacement :**
Assure-toi que ces fichiers sont bien **à la racine du dossier** que tu as ouvert dans ton éditeur (là où se trouve ton `.git`). AGY ne scanne généralement pas les dossiers parents.