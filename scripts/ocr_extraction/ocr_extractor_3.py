#!/usr/bin/env python3
"""
ocr_extractor_3.py - Extracteur OCR PDF vers Markdown avec gestion des segments LogCard
Responsabilité : Conversion PDF → Markdown via OCR par segments intelligents
Peut être utilisé indépendamment pour n'importe quel PDF avec configuration de structure
"""

import os
import base64
import json
import time
import argparse
from datetime import datetime
from mistralai import Mistral
import PyPDF2
from io import BytesIO
import sys

class DocumentStructureManager:
    """Gestionnaire de la structure des documents avec LogCards"""
    
    def __init__(self, structure_config=None):
        """
        Initialise le gestionnaire de structure
        
        Args:
            structure_config (dict): Configuration de structure du document
        """
        self.config = structure_config or {}
    
    def generate_segments(self, total_pages):
        """
        Génère les segments basés sur la configuration
        
        Args:
            total_pages (int): Nombre total de pages dans le document
            
        Returns:
            list: Liste des segments à traiter
        """
        document_structure = self.config.get('document_structure', {})
        
        if document_structure.get('manual_segmentation', {}).get('enabled'):
            return self._manual_segmentation()
        else:
            return self._automatic_segmentation(total_pages)
    
    def _manual_segmentation(self):
        """Segmentation manuelle basée sur la configuration"""
        segments = []
        manual_segments = self.config['document_structure']['manual_segmentation']['segments']
        
        for i, segment in enumerate(manual_segments):
            if segment['type'] == 'logcard':
                segments.append({
                    'pages': segment['pages'],
                    'type': 'logcard',
                    'start_page': segment['pages'][0],
                    'end_page': segment['pages'][-1],
                    'index': i
                })
        
        print(f"📋 Segmentation manuelle: {len(segments)} segments LogCard")
        return segments
    
    def _automatic_segmentation(self, total_pages):
        """Segmentation automatique avec gestion des cas spéciaux"""
        segments = []
        document_structure = self.config.get('document_structure', {})
        
        title_pages = set(document_structure.get('title_pages', []))
        non_logcard_pages = set(document_structure.get('non_logcard_pages', []))
        isolated_logcards = {item['page']: item['size'] for item in document_structure.get('isolated_logcards', [])}
        
        start_page = document_structure.get('logcard_start_page', 1)
        default_size = document_structure.get('default_logcard_size', 2)
        
        current_page = start_page
        segment_index = 0
        
        print(f"🎯 Configuration automatique:")
        print(f"   📄 Pages de titre: {sorted(title_pages) if title_pages else 'Aucune'}")
        print(f"   🏷️  Début LogCards: page {start_page}")
        print(f"   📏 Taille par défaut: {default_size} pages")
        print(f"   🔸 LogCards isolées: {len(isolated_logcards)}")
        print(f"   ❌ Pages non-LogCard: {sorted(non_logcard_pages) if non_logcard_pages else 'Aucune'}")
        
        while current_page <= total_pages:
            # Ignorer les pages de titre et non-logcard
            if current_page in title_pages or current_page in non_logcard_pages:
                current_page += 1
                continue
            
            # Gérer les LogCards isolées
            if current_page in isolated_logcards:
                size = isolated_logcards[current_page]
                end_page = min(current_page + size - 1, total_pages)
                pages = list(range(current_page, end_page + 1))
                
                segments.append({
                    'pages': pages,
                    'type': 'logcard',
                    'start_page': current_page,
                    'end_page': end_page,
                    'index': segment_index,
                    'special': 'isolated'
                })
                
                print(f"   🔸 LogCard isolée: pages {current_page}-{end_page} ({size} page{'s' if size > 1 else ''})")
                current_page += size
            else:
                # LogCard normale
                end_page = min(current_page + default_size - 1, total_pages)
                pages = list(range(current_page, end_page + 1))
                
                segments.append({
                    'pages': pages,
                    'type': 'logcard',
                    'start_page': current_page,
                    'end_page': end_page,
                    'index': segment_index
                })
                
                current_page += default_size
            
            segment_index += 1
        
        print(f"📦 Segmentation automatique: {len(segments)} segments LogCard générés")
        return segments

class Phase1OCRExtractor:
    def __init__(self, api_key, output_dir=None):
        """
        Initialise l'extracteur OCR
        
        Args:
            api_key (str): Clé API Mistral
            output_dir (str): Dossier de sortie (optionnel, sinon créé automatiquement)
        """
        self.client = Mistral(api_key=api_key)
        self.api_key = api_key
        self.output_dir = output_dir
        
        # États
        self.pdf_path = None
        self.pdf_info = None
        self.progress = None
        self.progress_file = None
        self.temp_dir = None
        self.final_markdown_path = None
        self.structure_manager = DocumentStructureManager()  # Configuration par défaut
        
    def extract_pdf_to_markdown(self, pdf_path, structure_config_path=None, output_dir=None):
        """
        Interface principale : extrait un PDF vers Markdown avec segments intelligents
        
        Args:
            pdf_path (str): Chemin vers le PDF à traiter
            structure_config_path (str): Chemin vers le fichier de configuration de structure (optionnel)
            output_dir (str): Dossier de sortie spécifique
            
        Returns:
            dict: Résultats de l'extraction
        """
        
        print("🔍 PHASE 1: EXTRACTION OCR PDF → MARKDOWN")
        print("="*50)
        
        # Initialiser pour ce PDF
        if not self._setup_for_pdf(pdf_path, output_dir):
            return None
        
        # Analyser le PDF d'abord pour obtenir le nombre de pages
        if not self._analyze_pdf():
            return None
            
        print(f"📄 Fichier: {self.pdf_info['filename']}")
        print(f"📑 Pages: {self.pdf_info['num_pages']}")
        print(f"📁 Taille: {self.pdf_info['file_size_mb']:.2f} MB")
        
        # Charger la configuration si fournie
        if structure_config_path and os.path.exists(structure_config_path):
            with open(structure_config_path, 'r') as f:
                structure_config = json.load(f)
            self.structure_manager = DocumentStructureManager(structure_config)
            print(f"📋 Configuration de structure chargée: {structure_config_path}")
        
        # Générer les segments intelligents (maintenant qu'on connaît le nombre de pages)
        segments = self.structure_manager.generate_segments(self.pdf_info['num_pages'])
        
        if not segments:
            print("❌ Aucun segment généré")
            return None
            
        print(f"🎯 {len(segments)} segments LogCard identifiés")
        
        # Diviser le PDF selon les segments
        chunks = self._split_pdf_by_segments(segments)
        if not chunks:
            return None
        
        # Traiter chaque segment OCR
        successful_segments = 0
        for chunk in chunks:
            if self._process_segment_ocr(chunk):
                successful_segments += 1
            time.sleep(1)  # Délai entre segments
        
        print(f"\n✅ Extraction OCR terminée: {successful_segments}/{len(segments)} segments réussis")
        
        if successful_segments > 0:
            # Consolider les résultats
            final_markdown = self._consolidate_markdown_results()
            if final_markdown:
                self.progress['completed'] = True
                self._save_progress()
                
                return {
                    'success': True,
                    'markdown_file': self.final_markdown_path,
                    'json_file': self.final_json_path,
                    'temp_directory': self.temp_dir,
                    'output_directory': self.output_dir,
                    'pdf_info': self.pdf_info,
                    'segments_processed': successful_segments,
                    'total_segments': len(segments),
                    'progress_file': self.progress_file
                }
        
        return {
            'success': False,
            'error': f"Seulement {successful_segments}/{len(segments)} segments réussis",
            'temp_directory': self.temp_dir
        }
    
    def _setup_for_pdf(self, pdf_path, output_dir=None):
        """Configure l'environnement pour un PDF spécifique"""
        
        if not os.path.exists(pdf_path):
            print(f"❌ Fichier PDF non trouvé: {pdf_path}")
            return False
            
        self.pdf_path = pdf_path
        
        # Créer la structure de dossiers
        if output_dir:
            self.output_dir = output_dir
        else:
            # Nom basé sur le PDF et timestamp
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            safe_name = "".join(c for c in pdf_name if c.isalnum() or c in ('-', '_')).rstrip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = f"OCR_RESULTS/{safe_name}_{timestamp}"
        
        # Créer les dossiers
        self.temp_dir = os.path.join(self.output_dir, "temp_segments")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Fichiers de résultats
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        safe_basename = "".join(c for c in pdf_basename if c.isalnum() or c in ('-', '_')).rstrip()
        
        self.final_markdown_path = os.path.join(self.output_dir, f"{safe_basename}_ocr_result.md")
        self.final_json_path = os.path.join(self.output_dir, f"{safe_basename}_ocr_result.json")
        self.progress_file = os.path.join(self.output_dir, "ocr_progress.json")
        
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
                completed = self.progress.get('completed_chunks', 0)
                total = self.progress.get('total_chunks', 0)
                print(f"📂 Progression existante: {completed}/{total} segments")
                return
            except:
                pass
        
        # Progression par défaut
        self.progress = {
            'pdf_path': self.pdf_path,
            'start_time': datetime.now().isoformat(),
            'total_chunks': 0,
            'total_segments': 0,
            'completed_chunks': 0,
            'failed_chunks': [],
            'chunk_files': {},
            'completed': False
        }
    
    def _save_progress(self):
        """Sauvegarde la progression"""
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def _analyze_pdf(self):
        """Analyse les informations du PDF"""
        try:
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                num_pages = len(pdf_reader.pages)
            
            file_size = os.path.getsize(self.pdf_path)
            
            self.pdf_info = {
                'filename': os.path.basename(self.pdf_path),
                'num_pages': num_pages,
                'file_size': file_size,
                'file_size_mb': file_size / (1024 * 1024)
            }
            
            # Sauvegarder les infos PDF
            pdf_info_file = os.path.join(self.output_dir, "pdf_info.json")
            with open(pdf_info_file, 'w') as f:
                json.dump(self.pdf_info, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse du PDF: {e}")
            return False
    
    def _split_pdf_by_segments(self, segments):
        """
        Divise le PDF selon les segments définis
        
        Args:
            segments (list): Liste des segments avec leurs pages
            
        Returns:
            list: Liste des chunks PDF créés selon les segments
        """
        try:
            chunks = []
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for segment_index, segment in enumerate(segments):
                    pdf_writer = PyPDF2.PdfWriter()
                    pages_in_segment = segment['pages']
                    
                    # Ajouter chaque page du segment au writer
                    for page_num in pages_in_segment:
                        # PyPDF2 utilise un index basé sur 0, donc page_num - 1
                        if 0 <= page_num - 1 < len(pdf_reader.pages):
                            pdf_writer.add_page(pdf_reader.pages[page_num - 1])
                    
                    # Créer le buffer pour ce segment
                    chunk_buffer = BytesIO()
                    pdf_writer.write(chunk_buffer)
                    chunk_buffer.seek(0)
                    
                    # Créer l'objet chunk avec les informations du segment
                    chunks.append({
                        'data': chunk_buffer.getvalue(),
                        'start_page': segment['start_page'],
                        'end_page': segment['end_page'],
                        'pages': pages_in_segment,
                        'index': segment_index,
                        'type': segment.get('type', 'logcard'),
                        'segment_info': segment
                    })
            
            # Mettre à jour la progression avec le nombre de segments
            self.progress['total_chunks'] = len(chunks)
            self.progress['total_segments'] = len(chunks)
            self._save_progress()
            
            return chunks
            
        except Exception as e:
            print(f"❌ Erreur lors de la division du PDF par segments: {e}")
            return None
    
    def _process_segment_ocr(self, segment):
        """
        Traite un segment avec OCR
        
        Args:
            segment (dict): Informations du segment à traiter
            
        Returns:
            bool: True si le traitement a réussi, False sinon
        """
        
        segment_index = segment['index']
        segment_type = segment.get('type', 'logcard')
        
        # Vérifier si déjà traité
        if segment_index in self.progress['chunk_files']:
            print(f"⏭️  Segment {segment_index+1} ({segment_type}) déjà traité")
            return True
        
        # Ignorer les segments qui ne sont pas des LogCards
        if segment_type != 'logcard':
            print(f"⏩ Segment {segment_index+1} ignoré (type: {segment_type})")
            return True
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                pages_range = f"{segment['start_page']}-{segment['end_page']}"
                pages_count = len(segment['pages'])
                
                print(f"🔍 OCR segment {segment_index+1}/{self.progress['total_segments']} "
                      f"(pages {pages_range}, {pages_count} page{'s' if pages_count > 1 else ''})...")
                
                # Encoder le segment en base64
                base64_pdf = base64.b64encode(segment['data']).decode('utf-8')
                
                # Traitement OCR avec Mistral
                response = self.client.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": "document_url",
                        "document_url": f"data:application/pdf;base64,{base64_pdf}"
                    },
                    include_image_base64=False
                )

                print(f"usage info : {response.usage_info}")


                # Capturer les informations d'usage des tokens
                usage_info = getattr(response, 'usage', None)
                if usage_info:
                    print(f"🪙 Tokens utilisés - Segment {segment_index+1}: {usage_info.total_tokens} "
                        f"(entrée: {usage_info.prompt_tokens}, sortie: {usage_info.completion_tokens})")
                
                # Sauvegarder le résultat du segment
                self._save_segment_result(segment_index, response, segment)
                
                print(f"✅ Segment {segment_index+1} terminé!")
                return True
                
            except Exception as e:
                print(f"❌ Tentative {attempt+1}/{max_retries} échouée pour segment {segment_index+1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏳ Attente de {wait_time}s...")
                    time.sleep(wait_time)
        
        # Marquer comme échoué
        self.progress['failed_chunks'].append(segment_index)
        self._save_progress()
        print(f"💥 Segment {segment_index+1} a échoué définitivement")
        return False
    
    def _save_segment_result(self, segment_index, ocr_response, segment_info):
        """
        Sauvegarde le résultat OCR d'un segment
        
        Args:
            segment_index (int): Index du segment
            ocr_response: Réponse de l'API OCR Mistral
            segment_info (dict): Informations sur le segment
        """
        
        segment_file_md = os.path.join(self.temp_dir, f"segment_{segment_index:03d}.md")
        segment_file_json = os.path.join(self.temp_dir, f"segment_{segment_index:03d}.json")


        # Créer le contenu Markdown pour ce segment
        markdown_content = []
        json_pages = []

        for i, page in enumerate(ocr_response.pages):
            actual_page_num = segment_info['pages'][i]
            markdown_content.append(f"# Page {actual_page_num}\n\n{page.markdown}")

            # Préparer les données JSON pour cette page
            json_pages.append({
                "page_number": actual_page_num,
                "content": page.markdown,
                "raw_text": getattr(page, 'text', page.markdown)  # Utiliser le texte brut si disponible
            })
            
        segment_content_md = "\n\n---\n\n".join(markdown_content)
        
        # Ajouter un en-tête avec les informations du segment
        segment_header_md = f"""<!-- SEGMENT {segment_index + 1} INFO
Type: {segment_info.get('type', 'logcard')}
Pages: {segment_info['pages']}
Start Page: {segment_info['start_page']}
End Page: {segment_info['end_page']}
LogCard Pages: {len(segment_info['pages'])}
Special: {segment_info.get('special', 'normal')}
-->

"""
        
        final_content_md = segment_header_md + segment_content_md

        # Créer le contenu JSON pour ce segment
        segment_json_data = {
            "segment_info": {
                "index": segment_index + 1,
                "type": segment_info.get('type', 'logcard'),
                "pages": segment_info['pages'],
                "start_page": segment_info['start_page'],
                "end_page": segment_info['end_page'],
                "total_pages": len(segment_info['pages']),
                "special": segment_info.get('special', 'normal'),
                "processed_at": datetime.now().isoformat()
            },
            "content": {
                "pages": json_pages,
                "full_markdown": segment_content_md
            }
        }
        
        # Sauvegarder le fichier Markdown
        with open(segment_file_md, 'w', encoding='utf-8') as f:
            f.write(final_content_md)

        # Sauvegarder le fichier JSON
        with open(segment_file_json, 'w', encoding='utf-8') as f:
            json.dump(segment_json_data, f, indent=2, ensure_ascii=False)
        
        # Mettre à jour la progression
        self.progress['chunk_files'][segment_index] = {
            'file_md': segment_file_md,
            'file_json': segment_file_json,
            'pages': segment_info['pages'],
            'start_page': segment_info['start_page'],
            'end_page': segment_info['end_page'],
            'segment_type': segment_info.get('type', 'logcard'),
            'completed_at': datetime.now().isoformat(),
            'characters': len(final_content_md)
        }
        self.progress['completed_chunks'] += 1
        self._save_progress()
        
        print(f"💾 Segment {segment_index+1} sauvegardé ({len(final_content_md)} caractères)")
    
    def _consolidate_markdown_results(self):
        """Consolide tous les segments en un fichier Markdown  et JSON finaux"""
        
        print("🔄 Consolidation des résultats Markdown et JSON")
        
        consolidated_content_md = []
        consolidated_json_data = {
            "metadata": {
                "source_file": self.pdf_info['filename'],
                "extraction_date": datetime.now().isoformat(),
                "total_pages": self.pdf_info['num_pages'],
                "file_size_mb": self.pdf_info['file_size_mb'],
                "segments_processed": self.progress['completed_chunks'],
                "total_segments": self.progress['total_segments'],
                "extraction_mode": "Segmentation intelligente LogCard"
            },
            "segments": []
        }
            
        # Trier par index de segment
        sorted_segments = sorted(
            self.progress['chunk_files'].items(),
            key=lambda x: x[0]
        )
        
        for segment_index, segment_info in sorted_segments:

            # Traiter le Markdown : 
            segment_file_md = segment_info.get('file_md', segment_info.get('file'))  # Compatibilité
            if segment_file_md and os.path.exists(segment_file_md):
                with open(segment_file_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                    consolidated_content_md.append(content)
            
            # Traiter le JSON
            segment_file_json = segment_info.get('file_json')
            if segment_file_json and os.path.exists(segment_file_json):
                with open(segment_file_json, 'r', encoding='utf-8') as f:
                    segment_json = json.load(f)
                    consolidated_json_data["segments"].append(segment_json)
        
        # Sauvegarder le fichier final
        final_content_md = "\n\n".join(consolidated_content_md)
        
        # Ajouter les métadonnées en début de fichier
        metadata_header_md = f"""<!-- OCR METADATA
Fichier source: {self.pdf_info['filename']}
Date d'extraction: {datetime.now().isoformat()}
Nombre de pages: {self.pdf_info['num_pages']}
Segments traités: {self.progress['completed_chunks']}/{self.progress['total_segments']}
Mode: Segmentation intelligente LogCard
-->

"""
        
        final_content_with_metadata = metadata_header_md + final_content_md
        
        with open(self.final_markdown_path, 'w', encoding='utf-8') as f:
            f.write(final_content_with_metadata)

        # Sauvegarder le fichier JSON final
        self.final_json_path = os.path.join(self.output_dir, f"{os.path.splitext(os.path.basename(self.final_markdown_path))[0]}.json")
        
        with open(self.final_json_path, 'w', encoding='utf-8') as f:
            json.dump(consolidated_json_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Markdown final: {self.final_markdown_path}")
        print(f"📄 JSON final: {self.final_json_path}")
        print(f"📊 {len(final_content_md)} caractères extraits")
        
        return self.final_markdown_path
    
    def cleanup_temp_files(self):
        """Nettoie les fichiers temporaires"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            os.remove(self.progress_file)
            print("🧹 Fichiers temporaires supprimés")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer les fichiers temporaires: {e}")
    
    def get_extraction_summary(self):
        """Retourne un résumé de l'extraction"""
        return {
            'pdf_info': self.pdf_info,
            'progress': self.progress,
            'output_files': {
                'markdown': self.final_markdown_path,
                'json': getattr(self, 'final_json_path', None),
                'progress': self.progress_file,
                'output_directory': self.output_dir
            }
        }

def main():
    """Interface CLI pour l'extracteur OCR avec segments LogCard"""
    
    parser = argparse.ArgumentParser(description="Extracteur OCR PDF vers Markdown avec gestion des segments LogCard")
    parser.add_argument('--pdf', required=True, help="Chemin vers le fichier PDF")
    parser.add_argument('--api-key', help="Clé API Mistral (ou variable d'environnement MISTRAL_API_KEY)")
    parser.add_argument('--output-dir', help="Dossier de sortie (optionnel)")
    parser.add_argument('--structure-config', help="Chemin vers le fichier de configuration de structure JSON")
    parser.add_argument('--keep-temp', action='store_true', help="Conserver les fichiers temporaires")
    
    args = parser.parse_args()
    
    # Récupérer la clé API
    api_key = args.api_key or os.getenv('MISTRAL_API_KEY')
    if not api_key:
        api_key = input("🔑 Entrez votre clé API Mistral: ").strip()
        if not api_key:
            print("❌ Clé API requise")
            return
    
    # Vérifier le fichier PDF
    if not os.path.exists(args.pdf):
        print(f"❌ Fichier PDF non trouvé: {args.pdf}")
        return
    
    # Lancer l'extraction
    extractor = Phase1OCRExtractor(api_key)
    
    try:
        result = extractor.extract_pdf_to_markdown(
            pdf_path=args.pdf,
            structure_config_path=args.structure_config,
            output_dir=args.output_dir
        )
        
        if result and result['success']:
            print(f"\n🎉 EXTRACTION OCR RÉUSSIE!")
            print(f"📄 Fichier Markdown: {result['markdown_file']}")
            print(f"📄 Fichier JSON: {result['json_file']}")
            print(f"📁 Dossier: {result['output_directory']}")
            print(f"📊 Segments traités: {result['segments_processed']}/{result['total_segments']}")
            
            # Statistiques
            if os.path.exists(result['markdown_file']):
                with open(result['markdown_file'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"📝 {len(content)} caractères extraits")
            
            # Nettoyage
            if not args.keep_temp:
                extractor.cleanup_temp_files()
            else:
                print(f"📁 Fichiers temporaires conservés dans: {result['temp_directory']}")
                
        else:
            print(f"\n❌ Extraction échouée")
            if result:
                print(f"Erreur: {result.get('error', 'Erreur inconnue')}")
            
    except KeyboardInterrupt:
        print("\n⏹️  Extraction interrompue")
        print(f"📁 Progression sauvegardée dans: {extractor.output_dir}")
        print("🔄 Vous pouvez reprendre l'extraction plus tard")
        
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")
        if extractor.output_dir:
            print(f"📁 Fichiers de débogage dans: {extractor.output_dir}")

if __name__ == "__main__":
    main()