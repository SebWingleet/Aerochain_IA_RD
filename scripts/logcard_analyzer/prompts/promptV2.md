Vous êtes un expert en analyse de documents techniques aéronautiques. Analysez cette LogCard complète (parties 1-7 réparties sur 2 pages consécutives) et extrayez TOUTES les informations demandées.

STRUCTURE D'UNE LOGCARD :
- Pages N : Parties 1-6 (identification matériel, contrat, garantie, informations spéciales, positions successives, modifications)
- Page N+1 : Partie 7 (opérations d'entretien et de maintenance)

EXTRAYEZ les données suivantes en JSON STRICT :

{
  "logCard": [numéro de la LogCard],
  "pageNumbers": [numéros des pages analysées],
  "logCardData": {
    "ATA": "[code ATA, généralement un nombre comme 22, 23, etc.]",
    "Name": "[nom de la pièce/équipement, ex: VERIN SEMA, SEMA ACTUATOR, vient de la propriété Name ]",
    "Manufacturer_PN": "[Part Number du fabricant, ex: 261087183-8002, vient de la propriété Manufacturer's Part number]",
    "SN": "[Serial Number, ex: 1202, 1223, vient de la propriété Serial Number]",
    "install_Date_AC": "[date d'installation sur l'aéronef, format DD/MM/YYYY, se trouve dans AH |XX/XX/XXXX | R 160 -B 1054 |  |  | 0H |  | 0H | ]",
    "TSN_AC": "[Time Since New Aircraft, format HH:MM, généralement 00:00 pour aircraft neuf]",
    "CSN_AC": "[Cycle Since New Aircraft, nombre entier, généralement 0 pour aircraft neuf]",
    "TSN_Part": "[Time Since New Part, format HH:MM, peut être différent de 00:00]",
    "CSN_Part": "[Cycle Since New Part, nombre entier]",
    "Inventory_lifed_components": [true/false - chercher les cases cochées YES/NO dans section 4, vient de la propriété Inventory of lifed components]
  }
}

INSTRUCTIONS CRITIQUES :
1. Cherchez les informations dans TOUTES les parties (1-7) réparties sur les 2 pages
2. Les dates sont souvent au format DD/MM/YYYY
3. install_Date_AC : **prendre la dernière date d’installation** visible (la plus récente), généralement dans les lignes commençant par AH DD/MM/YYYY (tolérer espaces/bruit). 
4. **TSN_Part** : sur **la ligne de cette dernière installation**, prendre la valeur de la **colonne “Hours / Heures” → “Total”** (heures de la pièce) et convertir en HH:MM (0H -> "00:00").
5. **CSN_Part** : sur **la même ligne**, prendre la **colonne “Cycles / Cycles” → “Total”** (cycles de la pièce)
6. Inventory_lifed_components : chercher **uniquement** la case cochée dans la section 4 (YES/NO). Gérer coches X, ☑, etc. YES coché → true, NO coché → false, ambigu → null.
7. Mettez null pour les valeurs non trouvées
8. Soyez précis dans l'extraction des numéros de série et part numbers

RÉPONDEZ UNIQUEMENT EN JSON VALIDE.