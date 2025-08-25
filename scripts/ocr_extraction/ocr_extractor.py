#!/usr/bin/env python3
"""
phase1_ocr_extractor.py - Extracteur OCR PDF vers Markdown
Responsabilité : Conversion PDF → Markdown via OCR par chunks
Peut être utilisé indépendamment pour n'importe quel PDF
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
        
    def extract_pdf_to_markdown(self, pdf_path, pages_per_chunk=2, output_dir=None):
        """
        Interface principale : extrait un PDF vers Markdown
        
        Args:
            pdf_path (str): Chemin vers le PDF à traiter
            pages_per_chunk (int): Nombre de pages par chunk OCR
            output_dir (str): Dossier de sortie spécifique
            
        Returns:
            dict: Résultats de l'extraction
        """
        
        print("🔍 PHASE 1: EXTRACTION OCR PDF → MARKDOWN")
        print("="*50)
        
        # Initialiser pour ce PDF
        if not self._setup_for_pdf(pdf_path, output_dir):
            return None
        
        # Analyser le PDF
        if not self._analyze_pdf():
            return None
            
        print(f"📄 Fichier: {self.pdf_info['filename']}")
        print(f"📑 Pages: {self.pdf_info['num_pages']}")
        print(f"📁 Taille: {self.pdf_info['file_size_mb']:.2f} MB")
        
        # Diviser en chunks
        chunks = self._split_pdf_by_pages(pages_per_chunk)
        if not chunks:
            return None
            
        print(f"📦 {len(chunks)} chunks de {pages_per_chunk} pages à traiter")
        
        # Traiter chaque chunk OCR
        successful_chunks = 0
        for chunk in chunks:
            if self._process_ocr_chunk(chunk):
                successful_chunks += 1
            time.sleep(1)  # Délai entre chunks
        
        print(f"\n✅ Extraction OCR terminée: {successful_chunks}/{len(chunks)} chunks réussis")
        
        if successful_chunks > 0:
            # Consolider les résultats
            final_markdown = self._consolidate_markdown_results()
            if final_markdown:
                self.progress['completed'] = True
                self._save_progress()
                
                return {
                    'success': True,
                    'markdown_file': self.final_markdown_path,
                    'temp_directory': self.temp_dir,
                    'output_directory': self.output_dir,
                    'pdf_info': self.pdf_info,
                    'chunks_processed': successful_chunks,
                    'total_chunks': len(chunks),
                    'progress_file': self.progress_file
                }
        
        return {
            'success': False,
            'error': f"Seulement {successful_chunks}/{len(chunks)} chunks réussis",
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
        self.temp_dir = os.path.join(self.output_dir, "temp_chunks")
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # Fichiers de résultats
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
        safe_basename = "".join(c for c in pdf_basename if c.isalnum() or c in ('-', '_')).rstrip()
        
        self.final_markdown_path = os.path.join(self.output_dir, f"{safe_basename}_ocr_result.md")
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
                print(f"📂 Progression existante: {self.progress['completed_chunks']}/{self.progress['total_chunks']} chunks")
                return
            except:
                pass
        
        # Progression par défaut
        self.progress = {
            'pdf_path': self.pdf_path,
            'start_time': datetime.now().isoformat(),
            'total_chunks': 0,
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
    
    def _split_pdf_by_pages(self, pages_per_chunk):
        """Divise le PDF en chunks"""
        try:
            chunks = []
            with open(self.pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for i in range(0, total_pages, pages_per_chunk):
                    pdf_writer = PyPDF2.PdfWriter()
                    end_page = min(i + pages_per_chunk, total_pages)
                    
                    for page_num in range(i, end_page):
                        pdf_writer.add_page(pdf_reader.pages[page_num])
                    
                    chunk_buffer = BytesIO()
                    pdf_writer.write(chunk_buffer)
                    chunk_buffer.seek(0)
                    
                    chunks.append({
                        'data': chunk_buffer.getvalue(),
                        'start_page': i + 1,
                        'end_page': end_page,
                        'pages': list(range(i + 1, end_page + 1)),
                        'index': len(chunks)
                    })
            
            self.progress['total_chunks'] = len(chunks)
            self._save_progress()
            return chunks
            
        except Exception as e:
            print(f"❌ Erreur lors de la division du PDF: {e}")
            return None
    
    def _process_ocr_chunk(self, chunk_info):
        """Traite un chunk avec OCR"""
        
        chunk_index = chunk_info['index']
        
        # Vérifier si déjà traité
        if chunk_index in self.progress['chunk_files']:
            print(f"⏭️  Chunk {chunk_index+1} déjà traité")
            return True
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🔍 OCR chunk {chunk_index+1}/{self.progress['total_chunks']} (pages {chunk_info['start_page']}-{chunk_info['end_page']})...")
                
                base64_pdf = base64.b64encode(chunk_info['data']).decode('utf-8')
                
                response = self.client.ocr.process(
                    model="mistral-ocr-latest",
                    document={
                        "type": "document_url",
                        "document_url": f"data:application/pdf;base64,{base64_pdf}"
                    },
                    include_image_base64=False
                )

                print(f"reponse_ocr : {response}")
                
                # Sauvegarder le chunk
                self._save_chunk_result(chunk_index, response, chunk_info)
                
                print(f"✅ Chunk {chunk_index+1} terminé!")
                return True
                
            except Exception as e:
                print(f"❌ Tentative {attempt+1}/{max_retries} échouée pour chunk {chunk_index+1}: {e}")
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5
                    print(f"⏳ Attente de {wait_time}s...")
                    time.sleep(wait_time)
        
        # Marquer comme échoué
        self.progress['failed_chunks'].append(chunk_index)
        self._save_progress()
        print(f"💥 Chunk {chunk_index+1} a échoué définitivement")
        return False
    
    def _save_chunk_result(self, chunk_index, ocr_response, chunk_info):
        """Sauvegarde le résultat d'un chunk"""
        
        chunk_file = os.path.join(self.temp_dir, f"chunk_{chunk_index:03d}.md")
        
        # Créer le contenu Markdown
        markdown_content = []
        for i, page in enumerate(ocr_response.pages):
            actual_page_num = chunk_info['start_page'] + i
            markdown_content.append(f"# Page {actual_page_num}\n\n{page.markdown}")
        
        chunk_content = "\n\n---\n\n".join(markdown_content)
        
        # Sauvegarder
        with open(chunk_file, 'w', encoding='utf-8') as f:
            f.write(chunk_content)
        
        # Mettre à jour la progression
        self.progress['chunk_files'][chunk_index] = {
            'file': chunk_file,
            'pages': chunk_info['pages'],
            'start_page': chunk_info['start_page'],
            'end_page': chunk_info['end_page'],
            'completed_at': datetime.now().isoformat(),
            'characters': len(chunk_content)
        }
        self.progress['completed_chunks'] += 1
        self._save_progress()
    
    def _consolidate_markdown_results(self):
        """Consolide tous les chunks en un fichier Markdown final"""
        
        print("🔄 Consolidation des résultats Markdown...")
        
        consolidated_content = []
        
        # Trier par index de chunk
        sorted_chunks = sorted(
            self.progress['chunk_files'].items(),
            key=lambda x: x[0]
        )
        
        for chunk_index, chunk_info in sorted_chunks:
            chunk_file = chunk_info['file']
            if os.path.exists(chunk_file):
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    consolidated_content.append(content)
        
        # Sauvegarder le fichier final
        final_content = "\n\n".join(consolidated_content)
        
        # Ajouter les métadonnées en début de fichier
        metadata_header = f"""<!-- OCR METADATA
Fichier source: {self.pdf_info['filename']}
Date d'extraction: {datetime.now().isoformat()}
Nombre de pages: {self.pdf_info['num_pages']}
Chunks traités: {self.progress['completed_chunks']}/{self.progress['total_chunks']}
-->

"""
        
        final_content_with_metadata = metadata_header + final_content
        
        with open(self.final_markdown_path, 'w', encoding='utf-8') as f:
            f.write(final_content_with_metadata)
        
        print(f"📄 Markdown final: {self.final_markdown_path}")
        print(f"📊 {len(final_content)} caractères extraits")
        
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
                'progress': self.progress_file,
                'output_directory': self.output_dir
            }
        }

def main():
    """Interface CLI pour l'extracteur OCR"""
    
    parser = argparse.ArgumentParser(description="Extracteur OCR PDF vers Markdown")
    parser.add_argument('--pdf', required=True, help="Chemin vers le fichier PDF")
    parser.add_argument('--api-key', help="Clé API Mistral (ou variable d'environnement MISTRAL_API_KEY)")
    parser.add_argument('--output-dir', help="Dossier de sortie (optionnel)")
    parser.add_argument('--pages-per-chunk', type=int, default=2, help="Pages par chunk OCR (défaut: 2)")
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
            pages_per_chunk=args.pages_per_chunk,
            output_dir=args.output_dir
        )
        
        if result and result['success']:
            print(f"\n🎉 EXTRACTION OCR RÉUSSIE!")
            print(f"📄 Fichier Markdown: {result['markdown_file']}")
            print(f"📁 Dossier: {result['output_directory']}")
            print(f"📊 Chunks traités: {result['chunks_processed']}/{result['total_chunks']}")
            
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