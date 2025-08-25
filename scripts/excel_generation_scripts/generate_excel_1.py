import json
import pandas as pd
from pathlib import Path

def convert_json_to_excel():
    # Chemin du fichier JSON d'entrée
    json_path = "/Users/sebastienbatty/Documents/1_Wingleet/2_DEV/THC/TEST/main_10_LOGCARDS-INVENTORYLOGBOOKDataSet_20250730_190445/results/LOGCARDS-INVENTORYLOGBOOKDataSet_logcards.json"
    
    # Lecture du fichier JSON
    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    # Extraction des données des log cards
    log_cards = data.get('logCards', [])
    
    # Préparation des données pour l'Excel
    excel_data = []
    
    for card in log_cards:
        card_data = card.get('logCardData', {})
        
        # Construction de la ligne de données selon le mapping demandé
        row = {
            'Analyse': '',  # Vide
            'Assembly level': '',  # Vide
            'ATA': f"{card_data.get('ATA', '')}-??" if card_data.get('ATA') else '',
            'Kardex No': f"{card_data.get('ATA', '')}-??-????" if card_data.get('ATA') else '',
            'Kardex designation/ Function': f"{card_data.get('Name', '')} ??" if card_data.get('Name') else '',
            'Designation': card_data.get('Name', ''),
            'F.I.N. Code': '',  # Pas dans les données source
            'Zone': '',  # Pas dans les données source
            'ACCESS': '',  # Pas dans les données source
            'P/N': card_data.get('Manufacturer_PN', ''),
            'S/N': card_data.get('SN', ''),
            'Installation Date A/C': card_data.get('install_Date_AC', ''),
            'TSN A/C': card_data.get('TSN_AC', ''),
            'CSN A/C': card_data.get('CSN_AC', ''),
            'Item Consumed (at installation).NEW': build_item_consumed_string(card_data),
            'Item Consumed (at installation).Overhaul': '',  # Vide
            'Item Consumed (at installation).Maintenance': '',  # Vide
            'Item Consumed (at installation).Inspection': '',  # Vide
            'MONITORING': 'HT LLP' if card_data.get('Inventory_lifed_components') else 'O/C'
        }
        
        excel_data.append(row)
    
    # Création du DataFrame
    df = pd.DataFrame(excel_data)
    
    # Définition du chemin de sortie
    json_path_obj = Path(json_path)
    parent_dir = json_path_obj.parent.parent  # Remonte de results/ vers le dossier parent
    output_dir = parent_dir / "results"
    output_dir.mkdir(exist_ok=True)  # Crée le dossier s'il n'existe pas
    
    # Génération du nom du fichier Excel
    json_filename = json_path_obj.stem  # Nom sans extension
    excel_filename = json_filename.replace('_logcards', '_excel.xlsx')
    output_path = output_dir / excel_filename
    
    # Sauvegarde du fichier Excel
    df.to_excel(output_path, index=False, engine='openpyxl')
    
    print(f"Fichier Excel créé avec succès : {output_path}")
    print(f"Nombre de lignes traitées : {len(excel_data)}")
    
    return output_path

def build_item_consumed_string(card_data):
    """
    Construit la chaîne pour Item Consumed (at installation).NEW
    Format: TSN_Part + " FH & " + CSN_Part + " & ?? OCY"
    """
    tsn_part = card_data.get('TSN_Part', '')
    csn_part = card_data.get('CSN_Part', '')
    
    if tsn_part or csn_part:
        # Assure-toi que les valeurs sont des chaînes
        tsn_str = str(tsn_part) if tsn_part is not None else ''
        csn_str = str(csn_part) if csn_part is not None else ''
        return f"{tsn_str} FH & {csn_str} & ?? OCY"
    else:
        return ''

if __name__ == "__main__":
    try:
        output_file = convert_json_to_excel()
        print("Conversion terminée avec succès!")
    except FileNotFoundError as e:
        print(f"Erreur : Fichier non trouvé - {e}")
    except json.JSONDecodeError as e:
        print(f"Erreur : Fichier JSON invalide - {e}")
    except Exception as e:
        print(f"Erreur inattendue : {e}")