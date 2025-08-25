## 🎯 **OBJECTIF PRINCIPAL**

**Transformer un PDF de fiches techniques aéronautiques en données structurées exploitables**

Votre PDF contient des **Log Cards / Fiches Matricules** d'équipements d'hélicoptère (actuateurs, pièces, etc.) avec des informations critiques comme :
- Numéros de série
- Références fabricant
- Dates de maintenance
- Historique des modifications
- Limites de vie des composants

**Le défi :** Ces données sont "emprisonnées" dans un PDF scanné → **Notre solution :** Les extraire et les structurer automatiquement.

---

## 🔄 **WORKFLOW EN 2 PHASES SÉPARÉES**

### 📖 **PHASE 1 : EXTRACTION OCR**
**Objectif :** Convertir les images PDF en texte brut

```
📄 PDF (50+ pages) 
    ↓
📦 Division en chunks de 2 pages (optimisation API)
    ↓
🔍 OCR Mistral par chunk (extraction texte)
    ↓
💾 Sauvegarde progressive (résistant aux interruptions)
    ↓
📝 Fichier Markdown consolidé
```

**Pourquoi par chunks ?**
- Limite API : 413 Request too large
- Robustesse : si 1 chunk échoue, les autres continuent
- Reprise : peut reprendre où ça s'est arrêté

### 🤖 **PHASE 2 : ANALYSE STRUCTURÉE LLM**
**Objectif :** Identifier et extraire les données des Log Cards

```
📝 Markdown (toutes les pages)
    ↓
📄 Analyse page par page avec Mistral Large
    ↓
🔍 Détection : "Est-ce une Log Card ?"
    ↓
📊 Extraction JSON structurée (si Log Card)
    ↓
💾 Consolidation finale
```

**Pourquoi page par page ?**
- Précision maximale
- Pas de confusion entre pages
- Gestion fine des erreurs

---

## 📁 **ORGANISATION DES FICHIERS**

```
TEST/
└── LOG_CARDS_INVENTORY_LOG_BOOK_20241229_143052/
    ├── 📂 results/          ← Résultats finaux
    │   ├── 📄 document.md   ← Texte complet
    │   └── 📊 document.json ← Données structurées
    ├── 📂 temp_ocr/         ← Chunks OCR temporaires
    ├── 📂 temp_llm/         ← Pages LLM temporaires
    └── 📋 progression files ← État des phases
```

---

## 🏷️ **RÉSULTAT FINAL : DONNÉES STRUCTURÉES**

### **Input :** Page PDF illisible
```
[Image scannée d'une fiche technique avec tableaux]
```

### **Output :** JSON exploitable
```json
{
  "logCard": 1,
  "pageNumber": 3,
  "logCardData": {
        "ATA": "21",
        "Designation_Function": "VERIN SEMA",
        "Designation": "SEMA ACTUATOR",
        "FIN_Code": "FAQ15",
        "Zone": "?", 
        "Access": "?",
        "PN": "261087183-8002",
        "SN": "1202",
        "install_Date_AC": "01/11/2022"
    }
}
```

Nous n'avons pas accès à Zone et Access dans le cas suivant, nous allons donc pas prendre ces termes en compte pour le moment.


Le Json que nous allons extraire est donc le suivant : 

```json
{
  "logCard": 1, #Correspond au numéro de LogCard qu'on extrait
  "pageNumber": [3,4] #Correspond au numéro de pages d'où proviennent les données
  "logCardData": { # les informations suivantes seront demandées à être extraite par le LLM depuis le Markdown généré.
        "ATA": 21, #Correspond au l'ATA de la pièce. 
        "Name": "VERIN SEMA",
        "Manufacturer_PN": "261087183-8002" #Correspond au Part Number du Manufacturer,
        "SN": "1202" #Correspond au Serial Number,
        "install_Date_AC": "01/11/2022", #Correspond à la date d'installation de la pièce sur l'AeroNef. 
        "TSN_AC": "00:00", #Correspond au Time Since New de l'Aircraft, dans ce cas spéficique, il sera toujours égal à 00:00 car le document sur lequel nous travaillons correspond à des pièces ajouter à un aircraft neuf. 
        "CSN_AC" : 0, #Correspond au Cycle Since New de l'Aricraft, l'Aircraft est neuf dans ce cas particulier, donc toujours 0.
        "TSN_Part" : "04:26" #Correspond au Time Since New de la Part installé sur l'Aicraft, les valeurs peuvent aller de 00:00 à +infini:59.
        "CSN_Part" :  6, #Correspond au Cycle Since New de la pièce, les valeurs peuvent aller de 0 à + infini en nombre entier.
        "Inventory_lifed_components" : true # Cette valeur se trouve directement dans le document, et nous permettra de déterminer si la pièce est On Condition (OC) ou à Potentiel : HT LLP. Les valeurs possibles sont true or false.
    }
}
```

Dans notre document, la Designation Function correspond au "Name", la 
---

## ⚡ **AVANTAGES DE CETTE APPROCHE**

### ✅ **Robustesse**
- **Séparation des phases** : OCR échoue ≠ LLM échoue
- **Sauvegarde progressive** : reprendre après interruption
- **Gestion d'erreurs** : continue même si certaines pages échouent

### ✅ **Précision**
- **OCR optimisé** : chunks de 2 pages (limite API)
- **LLM précis** : analyse page par page
- **Double validation** : OCR + IA pour plus de fiabilité

### ✅ **Exploitation**
- **Markdown** → lecture humaine, édition
- **JSON** → intégration base de données, API
- **Structure uniforme** → traitement automatisé

### ✅ **Organisation**
- **Tests isolés** : chaque exécution = dossier unique
- **Traçabilité** : progression, métadonnées, résumés
- **Archivage** : résultats finaux séparés des temporaires

---

## 🎪 **CAS D'USAGE CONCRETS**

1. **Inventaire automatisé** : Base de données des pièces
2. **Suivi maintenance** : Historique et échéances
3. **Conformité réglementaire** : Traçabilité complète
4. **Recherche rapide** : "Toutes les pièces SAGEM série 12xx"
5. **Alertes** : Pièces approchant leurs limites de vie

---

## 🚀 **EN RÉSUMÉ**

**Problème :** PDF illisible avec données critiques  
**Solution :** OCR robuste + IA d'analyse + Structure organisée  
**Résultat :** Données exploitables pour la maintenance aéronautique

**Le tout de manière robuste, reprennable et parfaitement organisée !** 🎯