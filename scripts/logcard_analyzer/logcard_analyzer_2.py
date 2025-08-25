#!/usr/bin/env python3
"""
logcard_analyzer_2.py - Analyseur LogCard spécialisé
Responsabilité : Analyse Markdown → JSON LogCards structurés
Spécialisé pour les documents aéronautiques avec LogCards
"""

import os
import json
import time
import re
import argparse
from datetime import datetime
from mistralai import Mistral
import sys

class Phase2LogCardAnalyzer:
    def __init__(self, api_key, output_dir=None):
        """
        Initialise l'analyseur LogCard
        
        Args:
            api_key (str): Clé API Mistral
            output_dir (str): Dossier de sortie (optionnel, sinon créé automatiquement)
        """
        self.client = Mistral(api_key=api_key)
        self.api_key = api_key
        self.output_dir = output_dir
        
        # États
        self.markdown_path = None
        self.document_info = None
        self.progress = None
        self.progress_file = None
        self.temp_dir = None
        self.final_json_path = None
        
    def analyze_markdown_to_logcards(self, markdown_path, output_dir=None):
        """
        Interface principale : analyse un Markdown vers LogCards JSON
        
        Args:
            markdown_path (str): Chemin vers le fichier Markdown à analyser
            output_dir (str): Dossier de sortie spécifique
            
        Returns:
            dict: Résultats de l'analyse
        """
        
        print("🏷️ PHASE 2: ANALYSE LOGCARD MARKDOWN → JSON")
        print("="*50)
        
        # Initialiser pour ce Markdown
        if not self._setup_for_markdown(markdown_path, output_dir):
            return None
        
        # Analyser le Markdown
        if not self._analyze_markdown_structure():
            return None
            
        print(f"📄 Fichier: {self.document_info['filename']}")
        print(f"📑 Pages: {self.document_info['total_pages']}")
        
        # Identifier les LogCards
        logcard_pairs = self._identify_logcard_pairs()
        if not logcard_pairs:
            print("❌ Aucune LogCard identifiée dans le document")
            return {
                'success': False,
                'error': 'Aucune LogCard trouvée',
                'output_directory': self.output_dir
            }
            
        print(f"🏷️ {len(logcard_pairs)} LogCards identifiées")
        
        # Traiter chaque LogCard
        successful_logcards = 0
        for logcard_info in logcard_pairs:
            if self._process_logcard_with_llm(logcard_info):
                successful_logcards += 1
            time.sleep(1)  # Délai entre LogCards
        
        print(f"\n✅ Analyse LogCard terminée: {successful_logcards}/{len(logcard_pairs)} LogCards réussies")
        
        if successful_logcards > 0:
            # Consolider les résultats
            final_json = self._consolidate_logcard_results()
            if final_json:
                self.progress['completed'] = True
                self._save_progress()
                
                return {
                    'success': True,
                    'json_file': self.final_json_path,
                    'temp_directory': self.temp_dir,
                    'output_directory': self.output_dir,
                    'document_info': self.document_info,
                    'logcards_processed': successful_logcards,
                    'total_logcards': len(logcard_pairs),
                    'progress_file': self.progress_file
                }
        
        return {
            'success': False,
            'error': f"Seulement {successful_logcards}/{len(logcard_pairs)} LogCards réussies",
            'temp_directory': self.temp_dir
        }
    
    def _setup_for_markdown(self, markdown_path, output_dir=None):
        """Configure l'environnement pour un Markdown spécifique"""
        
        if not os.path.exists(markdown_path):
            print(f"❌ Fichier Markdown non trouvé: {markdown_path}")
            return False
            
        self.markdown_path = markdown_path
        
        # Créer la structure de dossiers
        if output_dir:
            self.output_dir = output_dir
        else:
            # Nom basé sur le Markdown et timestamp
            md_name = os.path.splitext(os.path.basename(markdown_path))[0]
            safe_name = "".join(c for c in md_name if c.isalnum() or c in ('-', '_')).rstrip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = f"LOGCARD_RESULTS/{safe_name}_{timestamp}"
        
        # Créer les dossiers
        self.temp_dir = os.path.join(self.output_dir, "temp_logcards")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Fichiers de résultats
        md_basename = os.path.splitext(os.path.basename(markdown_path))[0]
        safe_basename = "".join(c for c in md_basename if c.isalnum() or c in ('-', '_')).rstrip()
        
        self.final_json_path = os.path.join(self.output_dir, f"{safe_basename}_logcards.json")
        self.progress_file = os.path.join(self.output_dir, "logcard_progress.json")
        
        # Charger ou initialiser la progression
        self._load_progress()
        
        print(f"📁 Dossier de travail: {self.output_dir}")
        return True
    
    def _load_progress(self):
        """Charge la progression existante"""
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r') as f:
                    self.progress = json.load(f)
                print(f"📂 Progression existante: {self.progress['completed_logcards']}/{self.progress['total_logcards']} LogCards")
                return
            except:
                pass
        
        # Progression par défaut
        self.progress = {
            'markdown_path': self.markdown_path,
            'start_time': datetime.now().isoformat(),
            'total_logcards': 0,
            'completed_logcards': 0,
            'failed_logcards': [],
            'logcard_files': {},
            'completed': False
        }
    
    def _save_progress(self):
        """Sauvegarde la progression"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def _analyze_markdown_structure(self):
        """Analyse la structure du Markdown"""
        try:
            with open(self.markdown_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extraire les métadonnées si présentes
            metadata = {}
            if content.startswith('<!--'):
                metadata_end = content.find('-->')
                if metadata_end != -1:
                    metadata_text = content[4:metadata_end]
                    # Parser les métadonnées basiques
                    for line in metadata_text.split('\n'):
                        if ':' in line:
                            key, value = line.split(':', 1)
                            metadata[key.strip()] = value.strip()
            
            # Compter les pages
            page_pattern = r'# Page (\d+)'
            page_matches = re.findall(page_pattern, content)
            total_pages = len(page_matches)
            
            self.document_info = {
                'filename': os.path.basename(self.markdown_path),
                'total_pages': total_pages,
                'content_length': len(content),
                'metadata': metadata,
                'analysis_date': datetime.now().isoformat()
            }
            
            # Sauvegarder les infos du document
            doc_info_file = os.path.join(self.output_dir, "document_info.json")
            with open(doc_info_file, 'w') as f:
                json.dump(self.document_info, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse du Markdown: {e}")
            return False
    
    def _identify_logcard_pairs(self):
        """Identifie les paires de pages constituant les LogCards"""
        
        # Extraire les pages du Markdown
        pages = self._extract_pages_from_markdown()
        if not pages:
            return []
        
        # Identifier les pages contenant des LogCards
        logcard_start_pages = []
        
        for page_num, page_content in pages.items():
            # Rechercher les indicateurs de début de LogCard
            if re.search(r'LOG CARD.*FICHE MATRICULE', page_content, re.IGNORECASE) or \
               re.search(r'Follow-up Sheet for new equipment.*Fiche suiveuse', page_content, re.IGNORECASE) or \
               re.search(r'Materiel identification.*Identification du matériel', page_content, re.IGNORECASE):
                logcard_start_pages.append(page_num)
        
        print(f"🔍 Pages de début de LogCard identifiées: {logcard_start_pages}")
        
        # Créer les paires LogCard (page N et page N+1)
        logcard_pairs = []
        for i, start_page in enumerate(logcard_start_pages):
            end_page = start_page + 1
            
            # Vérifier que la page suivante existe
            if end_page in pages:
                logcard_pairs.append({
                    'logcard_number': i + 1,
                    'start_page': start_page,
                    'end_page': end_page,
                    'page_numbers': [start_page, end_page],
                    'start_content': pages[start_page],
                    'end_content': pages[end_page]
                })
        
        print(f"🏷️ {len(logcard_pairs)} paires LogCard créées")
        
        # Mettre à jour la progression
        self.progress['total_logcards'] = len(logcard_pairs)
        self._save_progress()
        
        return logcard_pairs
    
    def _extract_pages_from_markdown(self):
        """Extrait les pages individuelles du fichier Markdown"""
        
        with open(self.markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Diviser par les pages (# Page X)
        page_pattern = r'# Page (\d+)\n\n(.*?)(?=# Page \d+|$)'
        matches = re.findall(page_pattern, content, re.DOTALL)
        
        pages = {}
        for page_num_str, page_content in matches:
            page_num = int(page_num_str)
            pages[page_num] = page_content.strip()
        
        print(f"📋 {len(pages)} pages extraites du Markdown")
        return pages
    
    def _process_logcard_with_llm(self, logcard_info):
        """Traite une LogCard avec le LLM"""
        
        logcard_number = logcard_info['logcard_number']
        
        # Vérifier si déjà traitée
        if logcard_number in self.progress['logcard_files']:
            print(f"⏭️  LogCard {logcard_number} déjà analysée")
            return True
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🏷️ Analyse LogCard {logcard_number} ({self.progress['completed_logcards']+1}/{self.progress['total_logcards']}) - Pages {logcard_info['start_page']}-{logcard_info['end_page']}...")
                
                # Combiner le contenu des deux pages
                combined_content = f"""# LogCard {logcard_number} - Page {logcard_info['start_page']} (Parties 1-6)

{logcard_info['start_content']}

# LogCard {logcard_number} - Page {logcard_info['end_page']} (Partie 7)

{logcard_info['end_content']}"""
                
                # Prompt pour l'analyse LogCard
                analysis_prompt = f"""
{self._get_logcard_analysis_prompt()}

CONTENU DE LA LOGCARD {logcard_number} À ANALYSER (PAGES {logcard_info['start_page']}-{logcard_info['end_page']}) :

{combined_content}
"""
                
                # Appel au LLM
                response = self.client.chat.complete(
                    model="mistral-large-latest",
                    messages=[
                        {
                            "role": "user", 
                            "content": analysis_prompt
                        }
                    ],
                    temperature=0.1
                )
                
                # Extraire et sauvegarder le résultat
                self._save_logcard_result(logcard_number, response, logcard_info, combined_content)
                
                print(f"✅ LogCard {logcard_number} analysée!")
                return True
                
            except Exception as e:
                print(f"❌ Tentative {attempt+1}/{max_retries} échouée pour LogCard {logcard_number}: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"⏳ Attente de {wait_time}s...")
                    time.sleep(wait_time)
        
        # Marquer comme échouée
        self.progress['failed_logcards'].append(logcard_number)
        self._save_progress()
        print(f"💥 LogCard {logcard_number} a échoué définitivement")
        return False
    
    def _save_logcard_result(self, logcard_number, llm_response, logcard_info, combined_content):
        """Sauvegarde le résultat LLM d'une LogCard"""
        
        logcard_file = os.path.join(self.temp_dir, f"logcard_{logcard_number:03d}.json")
        
        try:
            # Extraire le JSON de la réponse
            response_content = llm_response.choices[0].message.content
            
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            
            if json_start != -1 and json_end > json_start:
                json_content = response_content[json_start:json_end]
                structured_data = json.loads(json_content)
                
                # Assurer la structure attendue
                structured_data['logCard'] = logcard_number
                structured_data['pageNumbers'] = logcard_info['page_numbers']
                structured_data['originalMarkdown'] = combined_content
                
                # Vérifier la présence des données LogCard
                if 'logCardData' not in structured_data:
                    structured_data['logCardData'] = {}
                
                # Extraire le nom pour le logging
                name = structured_data.get('logCardData', {}).get('Name', 'N/A')
                print(f"🏷️  LogCard {logcard_number} - Données extraites: {name}")
                
            else:
                # Fallback
                structured_data = {
                    "logCard": logcard_number,
                    "pageNumbers": logcard_info['page_numbers'],
                    "logCardData": {
                        "extraction_error": "JSON extraction failed"
                    },
                    "originalMarkdown": combined_content,
                    "rawLlmResponse": response_content
                }
                
        except json.JSONDecodeError as e:
            # Fallback en cas d'erreur JSON
            structured_data = {
                "logCard": logcard_number,
                "pageNumbers": logcard_info['page_numbers'],
                "logCardData": {
                    "extraction_error": f"JSON decode error: {str(e)}"
                },
                "originalMarkdown": combined_content,
                "rawLlmResponse": llm_response.choices[0].message.content
            }
        
        # Sauvegarder
        with open(logcard_file, 'w', encoding='utf-8') as f:
            json.dump(structured_data, f, indent=2, ensure_ascii=False)
        
        # Mettre à jour la progression
        self.progress['logcard_files'][logcard_number] = {
            'file': logcard_file,
            'page_numbers': logcard_info['page_numbers'],
            'completed_at': datetime.now().isoformat()
        }
        self.progress['completed_logcards'] += 1
        self._save_progress()
    
    def _consolidate_logcard_results(self):
        """Consolide tous les résultats LogCard en un fichier JSON final"""
        
        print("🔄 Consolidation des résultats LogCard...")
        
        all_logcards = []
        
        # Trier par numéro de LogCard
        sorted_logcards = sorted(
            self.progress['logcard_files'].items(),
            key=lambda x: x[0]
        )
        
        for logcard_number, logcard_info in sorted_logcards:
            logcard_file = logcard_info['file']
            if os.path.exists(logcard_file):
                with open(logcard_file, 'r', encoding='utf-8') as f:
                    logcard_data = json.load(f)
                    all_logcards.append(logcard_data)
        
        # Créer le fichier JSON final
        final_data = {
            "documentInfo": {
                "sourceMarkdown": os.path.basename(self.markdown_path),
                "totalLogCards": len(all_logcards),
                "analysisDate": self.progress.get('start_time'),
                "consolidationDate": datetime.now().isoformat(),
                "documentMetadata": self.document_info.get('metadata', {})
            },
            "logCards": all_logcards
        }
        
        with open(self.final_json_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)
        
        print(f"📊 JSON LogCard final: {self.final_json_path}")
        print(f"🏷️  {len(all_logcards)} LogCards consolidées")
        
        return self.final_json_path
    
    def _get_logcard_analysis_prompt(self):
        """Retourne le prompt pour l'analyse LogCard"""
        return """
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
    "Name": "[nom de la pièce/équipement, ex: VERIN SEMA, SEMA ACTUATOR]",
    "Manufacturer_PN": "[Part Number du fabricant, ex: 261087183-8002]",
    "SN": "[Serial Number, ex: 1202, 1223]",
    "install_Date_AC": "[date d'installation sur l'aéronef, format DD/MM/YYYY]",
    "TSN_AC": "[Time Since New Aircraft, format HH:MM, généralement 00:00 pour aircraft neuf]",
    "CSN_AC": "[Cycle Since New Aircraft, nombre entier, généralement 0 pour aircraft neuf]",
    "TSN_Part": "[Time Since New Part, format HH:MM, peut être différent de 00:00]",
    "CSN_Part": "[Cycle Since New Part, nombre entier]",
    "Inventory_lifed_components": [true/false - chercher les cases cochées YES/NO dans section 4]
  }
}

INSTRUCTIONS CRITIQUES :
1. Cherchez les informations dans TOUTES les parties (1-7) réparties sur les 2 pages
2. L'ATA se trouve généralement dans la page de début ou dans les références
3. Les dates sont souvent au format DD/MM/YYYY
4. TSN = Time Since New (format heures:minutes)
5. CSN = Cycle Since New (nombre entier)
6. Pour Inventory_lifed_components, cherchez les cases cochées YES ☑ ou NO ☑ dans la section 4
7. Mettez null pour les valeurs non trouvées
8. Soyez précis dans l'extraction des numéros de série et part numbers

RÉPONDEZ UNIQUEMENT EN JSON VALIDE.
"""
    
    def cleanup_temp_files(self):
        """Nettoie les fichiers temporaires"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            os.remove(self.progress_file)
            print("🧹 Fichiers temporaires supprimés")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer les fichiers temporaires: {e}")
    
    def get_analysis_summary(self):
        """Retourne un résumé de l'analyse"""
        return {
            'document_info': self.document_info,
            'progress': self.progress,
            'output_files': {
                'json': self.final_json_path,
                'progress': self.progress_file,
                'output_directory': self.output_dir
            }
        }

def main():
    """Interface CLI pour l'analyseur LogCard"""
    
    parser = argparse.ArgumentParser(description="Analyseur LogCard Markdown vers JSON")
    parser.add_argument('--markdown', required=True, help="Chemin vers le fichier Markdown")
    parser.add_argument('--api-key', help="Clé API Mistral (ou variable d'environnement MISTRAL_API_KEY)")
    parser.add_argument('--output-dir', help="Dossier de sortie (optionnel)")
    parser.add_argument('--keep-temp', action='store_true', help="Conserver les fichiers temporaires")
    
    args = parser.parse_args()
    
    # Récupérer la clé API
    api_key = args.api_key or os.getenv('MISTRAL_API_KEY')
    if not api_key:
        api_key = input("🔑 Entrez votre clé API Mistral: ").strip()
        if not api_key:
            print("❌ Clé API requise")
            return
    
    # Vérifier le fichier Markdown
    if not os.path.exists(args.markdown):
        print(f"❌ Fichier Markdown non trouvé: {args.markdown}")
        return
    
    # Lancer l'analyse
    analyzer = Phase2LogCardAnalyzer(api_key)
    
    try:
        result = analyzer.analyze_markdown_to_logcards(
            markdown_path=args.markdown,
            output_dir=args.output_dir
        )
        
        if result and result['success']:
            print(f"\n🎉 ANALYSE LOGCARD RÉUSSIE!")
            print(f"🏷️ Fichier JSON: {result['json_file']}")
            print(f"📁 Dossier: {result['output_directory']}")
            print(f"📊 LogCards traitées: {result['logcards_processed']}/{result['total_logcards']}")
            
            # Afficher un aperçu des LogCards
            if os.path.exists(result['json_file']):
                with open(result['json_file'], 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                total_logcards = data['documentInfo']['totalLogCards']
                print(f"🏷️  {total_logcards} LogCards extraites")
                
                if total_logcards > 0:
                    print(f"\n📋 APERÇU DES LOGCARDS:")
                    for i, logcard in enumerate(data['logCards'][:3]):  # Afficher max 3
                        logcard_data = logcard.get('logCardData', {})
                        name = logcard_data.get('Name', 'N/A')
                        serial = logcard_data.get('SN', 'N/A')
                        ata = logcard_data.get('ATA', 'N/A')
                        pages = logcard.get('pageNumbers', [])
                        
                        print(f"  🏷️  LogCard {logcard['logCard']}: {name}")
                        print(f"      📄 Pages: {pages} | ATA: {ata} | S/N: {serial}")
                    
                    if total_logcards > 3:
                        remaining = total_logcards - 3
                        print(f"  ... et {remaining} autres LogCards")
            
            # Nettoyage
            if not args.keep_temp:
                analyzer.cleanup_temp_files()
            else:
                print(f"📁 Fichiers temporaires conservés dans: {result['temp_directory']}")
                
        else:
            print(f"\n❌ Analyse échouée")
            if result:
                print(f"Erreur: {result.get('error', 'Erreur inconnue')}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Analyse interrompue")
        print(f"📁 Progression sauvegardée dans: {analyzer.output_dir}")
        print("🔄 Vous pouvez reprendre l'analyse plus tard")
        
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")
        if analyzer.output_dir:
            print(f"📁 Fichiers de débogage dans: {analyzer.output_dir}")

if __name__ == "__main__":
    main()