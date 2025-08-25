import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime
import os

def xml_to_excel(xml_file_path, excel_file_path=None):
    """
    Convertit un fichier XML avec structure RalWebDataTable en fichier Excel
    
    Args:
        xml_file_path (str): Chemin vers le fichier XML source
        excel_file_path (str): Chemin de sortie pour le fichier Excel (optionnel)
    
    Returns:
        str: Chemin du fichier Excel créé
    """
    
    # Si aucun chemin de sortie n'est spécifié, créer un nom basé sur le fichier XML
    if excel_file_path is None:
        base_name = os.path.splitext(xml_file_path)[0]
        excel_file_path = f"{base_name}_converted.xlsx"
    
    try:
        # Parser le fichier XML
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        # Liste pour stocker toutes les données
        data_list = []
        
        # Parcourir tous les éléments RalWebDataTable
        for table in root.findall('RalWebDataTable'):
            # Dictionnaire pour une ligne de données
            row_data = {}
            
            # Extraire toutes les données de chaque élément
            for child in table:
                # Nettoyer le nom de la colonne et la valeur
                column_name = child.tag.strip()
                value = child.text.strip() if child.text else ""
                row_data[column_name] = value
            
            data_list.append(row_data)
        
        # Créer un DataFrame pandas
        df = pd.DataFrame(data_list)
        
        # Nettoyer et formater les données
        df = clean_and_format_dataframe(df)
        
        # Sauvegarder en Excel avec formatage
        with pd.ExcelWriter(excel_file_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Aircraft_Data', index=False)
            
            # Obtenir la feuille de calcul pour le formatage
            worksheet = writer.sheets['Aircraft_Data']
            
            # Ajuster la largeur des colonnes
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                
                # Définir une largeur maximale raisonnable
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"✅ Conversion réussie!")
        print(f"📁 Fichier Excel créé: {excel_file_path}")
        print(f"📊 Nombre de lignes: {len(df)}")
        print(f"📋 Nombre de colonnes: {len(df.columns)}")
        
        return excel_file_path
        
    except ET.ParseError as e:
        print(f"❌ Erreur lors du parsing XML: {e}")
        return None
    except Exception as e:
        print(f"❌ Erreur générale: {e}")
        return None

def clean_and_format_dataframe(df):
    """
    Nettoie et formate le DataFrame
    
    Args:
        df (pandas.DataFrame): DataFrame à nettoyer
    
    Returns:
        pandas.DataFrame: DataFrame nettoyé
    """
    
    # Colonnes de dates à traiter
    date_columns = ['ManufactureDate', 'InstallationDate', 'FirstInstallationDate', 'ExpiryDate']
    
    for col in date_columns:
        if col in df.columns:
            # Convertir les dates au format datetime
            df[col] = pd.to_datetime(df[col], format='%d.%m.%Y', errors='coerce')
    
    # Colonnes numériques à traiter
    numeric_columns = [
        'AircraftSerialNumber', 'ModelTreeLevel', 'ATAChapter',
        'HigherAssemblyAgeingAtFitInCycles', 'ComponentAgeingatInstallationinCycles',
        'HigherAssemblyCurrentCycles', 'ComponentCurrentCycles'
    ]
    
    for col in numeric_columns:
        if col in df.columns:
            # Convertir en numérique, remplacer les erreurs par NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Remplacer les chaînes vides par NaN pour une meilleure lisibilité
    df = df.replace('', pd.NA)
    
    return df

def analyze_xml_structure(xml_file_path):
    """
    Analyse la structure du fichier XML et affiche des informations utiles
    
    Args:
        xml_file_path (str): Chemin vers le fichier XML
    """
    
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        print("🔍 Analyse de la structure XML:")
        print(f"Élément racine: {root.tag}")
        
        # Compter les tables
        tables = root.findall('RalWebDataTable')
        print(f"Nombre de RalWebDataTable: {len(tables)}")
        
        # Analyser la première table pour voir la structure
        if tables:
            first_table = tables[0]
            print(f"\n📋 Colonnes disponibles ({len(first_table)} au total):")
            
            for i, child in enumerate(first_table, 1):
                value = child.text if child.text else "(vide)"
                print(f"  {i:2d}. {child.tag:35} = {value}")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'analyse: {e}")

# Fonction principale pour utilisation en script
def main():
    """
    Fonction principale pour exécution en tant que script
    """
    
    # Chemin vers votre fichier XML
    xml_file = "/Users/sebastienbatty/Documents/1_Wingleet/2_DEV/THC/INPUT_DOCS/xml/H160-MIS-DATA-PACK-1054-Applied Configuration.xml"  # Remplacez par le chemin de votre fichier
    
    # Vérifier si le fichier existe
    if not os.path.exists(xml_file):
        print(f"❌ Fichier non trouvé: {xml_file}")
        print("💡 Modifiez la variable 'xml_file' avec le bon chemin")
        return
    
    # Analyser la structure (optionnel)
    print("=" * 60)
    analyze_xml_structure(xml_file)
    print("=" * 60)
    
    # Convertir en Excel
    result = xml_to_excel(xml_file)
    
    if result:
        print(f"\n🎉 Conversion terminée avec succès!")
    else:
        print(f"\n❌ Échec de la conversion")

# Exécuter si le script est lancé directement
if __name__ == "__main__":
    main()

# Exemple d'utilisation alternative:
# xml_to_excel("mon_fichier.xml", "sortie_personnalisee.xlsx")