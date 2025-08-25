#!/usr/bin/env python3
"""
ocr_extractor_paddleocr_v3.py - Extracteur OCR avec PaddleOCR 3.1.0
Compatible avec les dernières versions PaddlePaddle 3.1.0 et PaddleOCR 3.1.0
"""

import os
import json
import time
import argparse
from datetime import datetime
import PyPDF2
from io import BytesIO
import sys

# Imports PaddleOCR v3.1.0
from paddleocr import PaddleOCR
from pdf2image import convert_from_bytes
from PIL import Image
import io
import numpy as np

class DocumentStructureManager:
    """Gestionnaire de la structure des documents avec LogCards"""
    
    def __init__(self, structure_config=None):
        self.config = structure_config or {}
    
    def generate_segments(self, total_pages):
        document_structure = self.config.get('document_structure', {})
        
        if document_structure.get('manual_segmentation', {}).get('enabled'):
            return self._manual_segmentation()
        else:
            return self._automatic_segmentation(total_pages)
    
    def _manual_segmentation(self):
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
            if current_page in title_pages or current_page in non_logcard_pages:
                current_page += 1
                continue
            
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
    def __init__(self, api_key=None, output_dir=None, lang='fr'):
        """
        Initialise l'extracteur OCR avec PaddleOCR 3.1.0
        
        Args:
            api_key (str): Non utilisé avec PaddleOCR (gardé pour compatibilité)
            output_dir (str): Dossier de sortie (optionnel, sinon créé automatiquement)
            lang (str): Langue pour PaddleOCR ('fr', 'en', 'chinese_cht', etc.)
        """
        # Configuration PaddleOCR 3.1.0 - Syntaxe mise à jour
        print("🔧 Initialisation de PaddleOCR 3.1.0...")
        
        try:
            # Nouvelle syntaxe pour PaddleOCR 3.1.0
            self.ocr = PaddleOCR(
                use_angle_cls=True,  # Correction de l'angle des images
                lang=lang,           # Langue (fr, en, etc.)
                use_gpu=False,       # GPU désactivé sur macOS
                show_log=False       # Réduire les logs verbeux
            )
            print("✅ PaddleOCR initialisé avec succès")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation de PaddleOCR: {e}")
            # Fallback avec configuration minimale
            try:
                self.ocr = PaddleOCR(lang=lang, use_gpu=False)
                print("✅ PaddleOCR initialisé en mode fallback")
            except Exception as e2:
                print(f"❌ Impossible d'initialiser PaddleOCR: {e2}")
                raise
        
        self.api_key = api_key
        self.output_dir = output_dir
        
        # États
        self.pdf_path = None
        self.pdf_info = None
        self.progress = None
        self.progress_file = None
        self.temp_dir = None
        self.final_markdown_path = None
        self.structure_manager = DocumentStructureManager()

    def extract_pdf_to_markdown(self, pdf_path, structure_config_path=None, output_dir=None):
        print("🔍 PHASE 1: EXTRACTION OCR PDF → MARKDOWN (PaddleOCR 3.1.0)")
        print("="*60)
        
        if not self._setup_for_pdf(pdf_path, output_dir):
            return None
        
        if not self._analyze_pdf():
            return None
            
        print(f"📄 Fichier: {self.pdf_info['filename']}")
        print(f"📑 Pages: {self.pdf_info['num_pages']}")
        print(f"📁 Taille: {self.pdf_info['file_size_mb']:.2f} MB")
        
        if structure_config_path and os.path.exists(structure_config_path):
            with open(structure_config_path, 'r') as f:
                structure_config = json.load(f)
            self.structure_manager = DocumentStructureManager(structure_config)
            print(f"📋 Configuration de structure chargée: {structure_config_path}")
        
        segments = self.structure_manager.generate_segments(self.pdf_info['num_pages'])
        
        if not segments:
            print("❌ Aucun segment généré")
            return None
            
        print(f"🎯 {len(segments)} segments LogCard identifiés")
        
        chunks = self._split_pdf_by_segments(segments)
        if not chunks:
            return None
        
        successful_segments = 0
        for chunk in chunks:
            if self._process_segment_ocr(chunk):
                successful_segments += 1
            time.sleep(1)
        
        print(f"\n✅ Extraction OCR terminée: {successful_segments}/{len(segments)} segments réussis")
        
        if successful_segments > 0:
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
        if not os.path.exists(pdf_path):
            print(f"❌ Fichier PDF non trouvé: {pdf_path}")
            return False
            
        self.pdf_path = pdf_path
        
        if output_dir:
            self.output_dir = output_dir
        else:
            pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
            safe_name = "".join(c for c in pdf_name if c.isalnum() or c in ('-', '_')).rstrip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_dir = f"OCR_RESULTS/{safe_name}_{timestamp}"
        
        self.temp_dir = os.path.join(self.output_dir, "temp_segments")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        safe_basename = "".join(c for c in pdf_basename if c.isalnum() or c in ('-', '_')).rstrip()
        
        self.final_markdown_path = os.path.join(self.output_dir, f"{safe_basename}_ocr_result.md")
        self.final_json_path = os.path.join(self.output_dir, f"{safe_basename}_ocr_result.json")
        self.progress_file = os.path.join(self.output_dir, "ocr_progress.json")
        
        self._load_progress()
        
        print(f"📁 Dossier de travail: {self.output_dir}")
        return True
    
    def _load_progress(self):
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
        with open(self.progress_file, 'w') as f:
            json.dump(self.progress, f, indent=2)
    
    def _analyze_pdf(self):
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
            
            pdf_info_file = os.path.join(self.output_dir, "pdf_info.json")
            with open(pdf_info_file, 'w') as f:
                json.dump(self.pdf_info, f, indent=2, ensure_ascii=False)
            
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors de l'analyse du PDF: {e}")
            return False
    
    def _split_pdf_by_segments(self, segments):
        try:
            chunks = []
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                
                for segment_index, segment in enumerate(segments):
                    pdf_writer = PyPDF2.PdfWriter()
                    pages_in_segment = segment['pages']
                    
                    for page_num in pages_in_segment:
                        if 0 <= page_num - 1 < len(pdf_reader.pages):
                            pdf_writer.add_page(pdf_reader.pages[page_num - 1])
                    
                    chunk_buffer = BytesIO()
                    pdf_writer.write(chunk_buffer)
                    chunk_buffer.seek(0)
                    
                    chunks.append({
                        'data': chunk_buffer.getvalue(),
                        'start_page': segment['start_page'],
                        'end_page': segment['end_page'],
                        'pages': pages_in_segment,
                        'index': segment_index,
                        'type': segment.get('type', 'logcard'),
                        'segment_info': segment
                    })
            
            self.progress['total_chunks'] = len(chunks)
            self.progress['total_segments'] = len(chunks)
            self._save_progress()
            
            return chunks
            
        except Exception as e:
            print(f"❌ Erreur lors de la division du PDF par segments: {e}")
            return None
    
    def _process_segment_ocr(self, segment):
        """
        Traite un segment avec PaddleOCR 3.1.0 - Version stable
        """
        segment_index = segment['index']
        segment_type = segment.get('type', 'logcard')
        
        if segment_index in self.progress['chunk_files']:
            print(f"⏭️  Segment {segment_index+1} ({segment_type}) déjà traité")
            return True
        
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
                
                # Convertir le PDF en images avec pdf2image
                print(f"  📸 Conversion PDF en images...")
                images = convert_from_bytes(
                    segment['data'],
                    dpi=200,  # Résolution adaptée pour OCR
                    fmt='RGB'  # Format explicite
                )
                
                print(f"  🔤 Traitement OCR avec PaddleOCR 3.1.0...")
                
                ocr_results = []
                for i, image in enumerate(images):
                    # Convertir PIL Image en array numpy
                    img_array = np.array(image)
                    
                    print(f"    📄 Page {segment['pages'][i]} - Analyse OCR...")
                    
                    # OCR avec PaddleOCR 3.1.0 - Nouvelle syntaxe stable
                    try:
                        # Version simplifiée sans paramètres problématiques
                        result = self.ocr.ocr(img_array, cls=False)
                        
                        # Alternative si cls=False ne marche pas
                        if result is None:
                            result = self.ocr.ocr(img_array)
                            
                    except Exception as ocr_error:
                        print(f"    ⚠️ Tentative alternative OCR: {ocr_error}")
                        # Tentative sans paramètres
                        result = self.ocr.ocr(img_array)
                    
                    # Convertir le résultat en markdown
                    markdown_text = self._paddle_result_to_markdown(result)
                    
                    actual_page_num = segment['pages'][i]
                    ocr_results.append({
                        'page_number': actual_page_num,
                        'markdown': markdown_text,
                        'raw_result': result
                    })
                    
                    print(f"    ✅ Page {actual_page_num} - {len(markdown_text)} caractères extraits")
                
                # Créer un objet response compatible
                class MockResponse:
                    def __init__(self, pages):
                        self.pages = pages
                        self.usage_info = None
                
                class MockPage:
                    def __init__(self, markdown, text=None):
                        self.markdown = markdown
                        self.text = text or markdown
                
                mock_pages = [MockPage(page['markdown']) for page in ocr_results]
                mock_response = MockResponse(mock_pages)
                
                print(f"✅ OCR PaddleOCR 3.1.0 terminé pour segment {segment_index+1}")
                
                # Sauvegarder le résultat du segment
                self._save_segment_result(segment_index, mock_response, segment)
                
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
    
    def _paddle_result_to_markdown(self, paddle_result):
        """
        Convertit le résultat PaddleOCR 3.1.0 en markdown
        Format de retour PaddleOCR 3.1.0: [[[bbox], (text, confidence)], ...]
        """
        if not paddle_result or not paddle_result[0]:
            return ""
        
        lines = []
        try:
            for line_info in paddle_result[0]:
                if len(line_info) >= 2:
                    # line_info[0] = bbox (coordonnées)
                    # line_info[1] = (text, confidence)
                    text_info = line_info[1]
                    
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                        text = text_info[0].strip()
                        confidence = text_info[1]
                    else:
                        # Format alternatif
                        text = str(text_info).strip()
                        confidence = 1.0
                    
                    # Filtrer les textes avec une confiance trop faible
                    if confidence > 0.3 and text:  # Seuil plus permissif
                        lines.append(text)
                        
        except Exception as e:
            print(f"⚠️ Erreur parsing résultat OCR: {e}")
            # Fallback simple
            return str(paddle_result)
        
        return '\n'.join(lines)
    
    def _save_segment_result(self, segment_index, ocr_response, segment_info):
        segment_file_md = os.path.join(self.temp_dir, f"segment_{segment_index:03d}.md")
        segment_file_json = os.path.join(self.temp_dir, f"segment_{segment_index:03d}.json")

        markdown_content = []
        json_pages = []

        for i, page in enumerate(ocr_response.pages):
            actual_page_num = segment_info['pages'][i]
            markdown_content.append(f"# Page {actual_page_num}\n\n{page.markdown}")

            json_pages.append({
                "page_number": actual_page_num,
                "content": page.markdown,
                "raw_text": getattr(page, 'text', page.markdown)
            })
            
        segment_content_md = "\n\n---\n\n".join(markdown_content)
        
        segment_header_md = f"""<!-- SEGMENT {segment_index + 1} INFO
Type: {segment_info.get('type', 'logcard')}
Pages: {segment_info['pages']}
Start Page: {segment_info['start_page']}
End Page: {segment_info['end_page']}
LogCard Pages: {len(segment_info['pages'])}
Special: {segment_info.get('special', 'normal')}
OCR Engine: PaddleOCR 3.1.0
-->

"""
        
        final_content_md = segment_header_md + segment_content_md

        segment_json_data = {
            "segment_info": {
                "index": segment_index + 1,
                "type": segment_info.get('type', 'logcard'),
                "pages": segment_info['pages'],
                "start_page": segment_info['start_page'],
                "end_page": segment_info['end_page'],
                "total_pages": len(segment_info['pages']),
                "special": segment_info.get('special', 'normal'),
                "processed_at": datetime.now().isoformat(),
                "ocr_engine": "PaddleOCR 3.1.0"
            },
            "content": {
                "pages": json_pages,
                "full_markdown": segment_content_md
            }
        }
        
        with open(segment_file_md, 'w', encoding='utf-8') as f:
            f.write(final_content_md)

        with open(segment_file_json, 'w', encoding='utf-8') as f:
            json.dump(segment_json_data, f, indent=2, ensure_ascii=False)
        
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
                "extraction_mode": "Segmentation intelligente LogCard",
                "ocr_engine": "PaddleOCR 3.1.0"
            },
            "segments": []
        }
            
        sorted_segments = sorted(
            self.progress['chunk_files'].items(),
            key=lambda x: x[0]
        )
        
        for segment_index, segment_info in sorted_segments:
            segment_file_md = segment_info.get('file_md', segment_info.get('file'))
            if segment_file_md and os.path.exists(segment_file_md):
                with open(segment_file_md, 'r', encoding='utf-8') as f:
                    content = f.read()
                    consolidated_content_md.append(content)
            
            segment_file_json = segment_info.get('file_json')
            if segment_file_json and os.path.exists(segment_file_json):
                with open(segment_file_json, 'r', encoding='utf-8') as f:
                    segment_json = json.load(f)
                    consolidated_json_data["segments"].append(segment_json)
        
        final_content_md = "\n\n".join(consolidated_content_md)
        
        metadata_header_md = f"""<!-- OCR METADATA
Fichier source: {self.pdf_info['filename']}
Date d'extraction: {datetime.now().isoformat()}
Nombre de pages: {self.pdf_info['num_pages']}
Segments traités: {self.progress['completed_chunks']}/{self.progress['total_segments']}
Mode: Segmentation intelligente LogCard
OCR Engine: PaddleOCR 3.1.0
-->

"""
        
        final_content_with_metadata = metadata_header_md + final_content_md
        
        with open(self.final_markdown_path, 'w', encoding='utf-8') as f:
            f.write(final_content_with_metadata)

        self.final_json_path = os.path.join(self.output_dir, f"{os.path.splitext(os.path.basename(self.final_markdown_path))[0]}.json")
        
        with open(self.final_json_path, 'w', encoding='utf-8') as f:
            json.dump(consolidated_json_data, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Markdown final: {self.final_markdown_path}")
        print(f"📄 JSON final: {self.final_json_path}")
        print(f"📊 {len(final_content_md)} caractères extraits")
        
        return self.final_markdown_path
    
    def cleanup_temp_files(self):
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            os.remove(self.progress_file)
            print("🧹 Fichiers temporaires supprimés")
        except Exception as e:
            print(f"⚠️  Impossible de supprimer les fichiers temporaires: {e}")
    
    def get_extraction_summary(self):
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
    parser = argparse.ArgumentParser(description="Extracteur OCR PDF vers Markdown avec PaddleOCR 3.1.0")
    parser.add_argument('--pdf', required=True, help="Chemin vers le fichier PDF")
    parser.add_argument('--api-key', help="Clé API (compatibilité)")
    parser.add_argument('--output-dir', help="Dossier de sortie (optionnel)")
    parser.add_argument('--structure-config', help="Chemin vers le fichier de configuration de structure JSON")
    parser.add_argument('--keep-temp', action='store_true', help="Conserver les fichiers temporaires")
    
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv('MISTRAL_API_KEY')
    
    if not os.path.exists(args.pdf):
        print(f"❌ Fichier PDF non trouvé: {args.pdf}")
        return
    
    extractor = Phase1OCRExtractor(api_key)
    
    try:
        result = extractor.extract_pdf_to_markdown(
            pdf_path=args.pdf,
            structure_config_path=args.structure_config,
            output_dir=args.output_dir
        )
        
        if result and result['success']:
            print(f"\n🎉 EXTRACTION OCR RÉUSSIE avec PaddleOCR 3.1.0!")
            print(f"📄 Fichier Markdown: {result['markdown_file']}")
            print(f"📄 Fichier JSON: {result['json_file']}")
            print(f"📁 Dossier: {result['output_directory']}")
            print(f"📊 Segments traités: {result['segments_processed']}/{result['total_segments']}")
            
            if os.path.exists(result['markdown_file']):
                with open(result['markdown_file'], 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"📝 {len(content)} caractères extraits")
            
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
        
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")
        import traceback
        traceback.print_exc()
        if hasattr(extractor, 'output_dir') and extractor.output_dir:
            print(f"📁 Fichiers de débogage dans: {extractor.output_dir}")

if __name__ == "__main__":
    main()