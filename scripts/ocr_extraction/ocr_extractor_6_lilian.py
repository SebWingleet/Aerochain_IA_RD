#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
#!/usr/bin/env python3
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
import statistics
from math import inf
from itertools import groupby

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
                use_angle_cls=True,
                lang=lang,

                # Astuces pour docs scannés pâles:
                det_db_box_thresh=0.3,     # accepte des boîtes plus "faibles"
                det_db_thresh=0.25,        # seuil binarisation du det
                det_db_unclip_ratio=1.8,   # un peu plus d'air autour des boîtes
                rec_batch_num=32
            )
            print("✅ PaddleOCR initialisé avec succès")
            
        except Exception as e:
            print(f"❌ Erreur lors de l'initialisation de PaddleOCR: {e}")
            # Fallback avec configuration minimale
            try:
                self.ocr = PaddleOCR(lang=lang)#, use_gpu=False)
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
    

    def _render_pdf_bytes_to_images(self, pdf_bytes, dpi=200):
        # Try pypdfium2 first (no external exe)
        try:
            import pypdfium2 as pdfium
            import numpy as np
            import PIL.Image
            pdf = pdfium.PdfDocument(pdf_bytes)
            images = []
            # Render all pages at scale = dpi/72
            scale = dpi / 72.0
            for i in range(len(pdf)):
                page = pdf[i]
                bitmap = page.render(scale=scale).to_pil()
                images.append(bitmap.convert("RGB"))
            return images
        except Exception as e_pdfium:
            print(f"⚠️ pypdfium2 indisponible ({e_pdfium}), fallback pdf2image...")

        # Fallback: pdf2image (requires Poppler)
        from pdf2image import convert_from_bytes
        import os
        poppler_path = os.environ.get("POPPLER_PATH", None)  # ex: C:\poppler\Library\bin
        return convert_from_bytes(pdf_bytes, dpi=dpi, fmt='RGB',
                                poppler_path=poppler_path if poppler_path else None)


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
                #images = self._render_pdf_bytes_to_images(
                #    segment['data'],
                #    dpi=200,  # Résolution adaptée pour OCR
                #    #fmt='RGB'  # Format explicite
                #)
                images = convert_from_bytes(
                    segment['data'],
                    dpi=200,  # Résolution adaptée pour OCR
                    #fmt='RGB'  # Format explicite
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
                            print(result)
                            
                    except Exception as ocr_error:
                        print(f"    ⚠️ Tentative alternative OCR: {ocr_error}")
                        # Tentative sans paramètres
                        # OCR
                        result = self.ocr.ocr(img_array)

                        # --- Récupération du JSON "officiel" avec rec_texts/rec_scores/rec_boxes ---
                        page_json = None
                        json_out = os.path.join(self.temp_dir, f"segment_{segment_index:03d}_p{i+1:02d}_paddle.json")

                        try:
                            # Si la lib renvoie un objet enrichi compatible .save_to_json()
                            if result and hasattr(result[0], "save_to_json"):
                                result[0].save_to_json(json_out)
                                with open(json_out, "r", encoding="utf-8") as fj:
                                    page_json = json.load(fj)
                            else:
                                # Sinon on recompose le même schéma à partir de la sortie liste
                                page_json = self._paddle_list_to_json_like(result)
                                with open(json_out, "w", encoding="utf-8") as fj:
                                    json.dump(page_json, fj, ensure_ascii=False, indent=2)
                        except Exception:
                            # Fallback robuste
                            page_json = self._paddle_list_to_json_like(result)

                    # --- Markdown depuis le JSON ---
                    markdown_text = self._paddle_result_to_markdown(page_json)
                    actual_page_num = segment['pages'][i]
                    ocr_results.append({
                        'page_number': actual_page_num,
                        'markdown': markdown_text,
                        'raw_result_json': page_json,     # on garde le JSON structuré
                        'paddle_json_path': json_out
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
                #self._save_segment_result(segment_index, mock_response, segment)
                
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
    
    def _paddle_list_to_json_like(self, paddle_list):
        """
        Convertit la sortie liste [[box, (text, score)], ...] en un dict
        {'rec_texts': [...], 'rec_scores': [...], 'rec_boxes': [...]}
        """
        rec_texts, rec_scores, rec_boxes = [], [], []
        if not paddle_list or not paddle_list[0]:
            return {"rec_texts": [], "rec_scores": [], "rec_boxes": []}
        for item in paddle_list[0]:
            try:
                box = item[0]
                text, score = item[1][0], float(item[1][1])
                rec_boxes.append(box)
                rec_texts.append(text)
                rec_scores.append(score)
            except Exception:
                continue
        return {"rec_texts": rec_texts, "rec_scores": rec_scores, "rec_boxes": rec_boxes}




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
                 'file': segment_file_md,
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



    def _tokens_from_seg(self,seg, conf_thresh=0.30):
        texts  = seg.get("rec_texts")  or []
        scores = seg.get("rec_scores") or []
        boxes  = seg.get("rec_boxes")
        polys  = seg.get("rec_polys") or seg.get("dt_polys")

        toks = []
        if boxes and len(boxes) == len(texts):
            for t, sc, b in zip(texts, scores, boxes):
                sc = float(sc or 0.0)
                if not t or sc < conf_thresh: 
                    continue
                xmin,ymin,xmax,ymax = map(float, b)
                toks.append({
                    "text": t.strip(),
                    "cx": 0.5*(xmin+xmax), "cy": 0.5*(ymin+ymax),
                    "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax,
                    "h": max(1.0, ymax-ymin)
                })
        elif polys and len(polys) == len(texts):
            for t, sc, poly in zip(texts, scores, polys):
                sc = float(sc or 0.0)
                if not t or sc < conf_thresh:
                    continue
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                xmin,ymin,xmax,ymax = min(xs),min(ys),max(xs),max(ys)
                toks.append({
                    "text": t.strip(),
                    "cx": sum(xs)/len(xs), "cy": sum(ys)/len(ys),
                    "xmin": xmin, "xmax": xmax, "ymin": ymin, "ymax": ymax,
                    "h": max(1.0, ymax-ymin)
                })
        toks.sort(key=lambda d: (d["cy"], d["cx"]))
        return toks

    def _bucket_rows_by_y(self,toks):
        """ regroupe les tokens par lignes (tolérance basée sur médiane des hauteurs) """
        if not toks: return []
        med_h = statistics.median(t["h"] for t in toks)
        tol = max(8.0, 0.6*med_h)
        rows = []
        cur = []
        cur_y = None
        for t in toks:
            if cur_y is None or abs(t["cy"] - cur_y) <= tol:
                if cur_y is None:
                    cur_y = t["cy"]
                cur.append(t)
            else:
                rows.append(sorted(cur, key=lambda d: d["cx"]))
                cur = [t]; cur_y = t["cy"]
        if cur: rows.append(sorted(cur, key=lambda d: d["cx"]))
        return rows

    def _split_row_into_columns(self,row, min_gap_ratio=0.35):
        """
        découpe une ligne en colonnes en détectant les 'grands gaps' horizontaux.
        min_gap_ratio: fraction de la largeur moyenne d’un mot pour décider un saut de colonne.
        """
        if not row: return [row]
        # largeur moyenne
        widths = [(t["xmax"]-t["xmin"]) for t in row]
        avg_w = max(1.0, sum(widths)/len(widths))

        cols = [[]]
        prev = None
        for t in row:
            if prev is None:
                cols[-1].append(t)
                prev = t
                continue
            gap = t["xmin"] - prev["xmax"]
            if gap > min_gap_ratio * avg_w:
                cols.append([t])
            else:
                cols[-1].append(t)
            prev = t
        return cols


    def _rows_to_markdown_table(self,rows, min_cols=2, max_cols=6):
        """
        Convertit des lignes -> table Markdown.
        On harmonise le nombre de colonnes sur l’ensemble (max observé borné).
        """
        # transformer chaque ligne en liste de cellules (chaque cellule = concat des tokens)
        line_cells = []
        maxc = 0
        for row in rows:
            cols =self._split_row_into_columns(row)
            cells = [" ".join(t["text"] for t in c).strip() for c in cols]
            maxc = max(maxc, len(cells))
            line_cells.append(cells)
        maxc = max(min_cols, min(maxc, max_cols))

        # normaliser la largeur (ajouter cellules vides à droite si besoin)
        line_cells = [c + [""]*(maxc-len(c)) if len(c)<maxc else c[:maxc] for c in line_cells]

        # construire markdown
        header = "| " + " | ".join(f"Col {i+1}" for i in range(maxc)) + " |"
        sep    = "| " + " | ".join("---" for _ in range(maxc)) + " |"
        body   = "\n".join("| " + " | ".join(c.replace("|","/") for c in cells) + " |" for cells in line_cells)
        return header + "\n" + sep + "\n" + body


    def _paddle_segment_to_markdown_table(self, seg: dict, conf_thresh: float = 0.30,
                                        min_cols: int = 2, max_cols: int = 6) -> str:
        toks = self._tokens_from_seg(seg, conf_thresh=conf_thresh)
        if not toks:
            return ""
        rows = self._bucket_rows_by_y(toks)
        if not rows:
            return ""
        return self._rows_to_markdown_table(rows, min_cols=min_cols, max_cols=max_cols)


    def _paddle_segment_to_markdown(self, seg: dict, conf_thresh: float = 0.30) -> str:
        """
        Construit un markdown lisible à partir d'un segment OCR au format:
        { 'rec_texts': [...], 'rec_scores': [...],
        'rec_boxes': [[xmin,ymin,xmax,ymax], ...] } ou 'rec_polys' (4 points).
        """
        texts  = seg.get("rec_texts")  or []
        scores = seg.get("rec_scores") or []
        boxes  = seg.get("rec_boxes")  # [xmin,ymin,xmax,ymax]
        polys  = seg.get("rec_polys")  # [[x,y],...]*4

        items = []
        if boxes and len(boxes) == len(texts):
            for txt, sc, b in zip(texts, scores, boxes):
                try: sc = float(sc)
                except: sc = 0.0
                if not txt or sc < conf_thresh: 
                    continue
                xmin, ymin, xmax, ymax = map(float, b)
                cx = 0.5 * (xmin + xmax)
                cy = 0.5 * (ymin + ymax)
                h  = max(1.0, ymax - ymin)
                items.append((cy, cx, h, txt.strip()))
        elif polys and len(polys) == len(texts):
            for txt, sc, poly in zip(texts, scores, polys):
                try: sc = float(sc)
                except: sc = 0.0
                if not txt or sc < conf_thresh: 
                    continue
                xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
                cx = sum(xs)/len(xs); cy = sum(ys)/len(ys)
                h  = max(1.0, (max(ys)-min(ys)))
                items.append((cy, cx, h, txt.strip()))
        else:
            return ""

        if not items:
            return ""

        # Tri haut→bas puis gauche→droite + regroupement par lignes
        items.sort(key=lambda t: (t[0], t[1]))
        try:
            import statistics
            med_h = statistics.median([t[2] for t in items])
        except Exception:
            med_h = 12.0
        tol = max(8.0, 0.6 * med_h)

        lines, current_line, current_y = [], [], None
        for cy, cx, h, txt in items:
            if current_y is None or abs(cy - current_y) <= tol:
                current_y = cy if current_y is None else current_y
                current_line.append((cx, txt))
            else:
                current_line.sort(key=lambda t: t[0])
                lines.append(" ".join([t[1] for t in current_line]))
                current_y = cy
                current_line = [(cx, txt)]
        if current_line:
            current_line.sort(key=lambda t: t[0])
            lines.append(" ".join([t[1] for t in current_line]))
        return "\n".join(lines)


    def _paddle_result_to_markdown(self, phase1_json: dict, conf_thresh: float = 0.30) -> str:
        """
        Construit le markdown global à partir du JSON final de la Phase 1
        (clé 'segments' contenant des dicts avec rec_texts/rec_scores/rec_boxes|rec_polys).
        """
        if not phase1_json: 
            return ""
        segs = phase1_json.get("segments") or []
        md_chunks = []
        for idx, seg in enumerate(segs, 1):
            # Assurer un type par défaut pour la phase 2
            si = seg.get("segment_info") or {}
            si.setdefault("type", "logcard")
            seg["segment_info"] = si

            md = self._paddle_segment_to_markdown(seg, conf_thresh=conf_thresh)
            if not md:
                continue

            # (Optionnel) titre par segment avec pages si dispo
            header = f"## Segment {idx}"
            if si.get("pages"):
                header += f" (pages {si['pages'][0]}-{si['pages'][-1]})"
            md_chunks.append(f"{header}\n\n{md}")
        return "\n\n".join(md_chunks)


    def _get_segment_markdown(self,seg: dict) -> str:

        md = self._paddle_segment_to_markdown(seg, conf_thresh=0.30)
        return md or ""

    def _get_segment_pages(seg: dict):
        si = seg.get("segment_info") or {}
        pages = si.get("pages")
        if isinstance(pages, list) and pages:
            return pages
        # fallback éventuel
        start = si.get("start_page"); end = si.get("end_page")
        if start and end:
            return list(range(int(start), int(end)+1))
        return []


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




        def _ingest_segment_paths(file_md, file_json):
            # Priorité au .md si présent
            if file_md and os.path.exists(file_md):
                with open(file_md, "r", encoding="utf-8") as f:
                    consolidated_content_md.append(f.read())
            # Toujours tenter d’ajouter le JSON (alimente la clé "segments")
            if file_json and os.path.exists(file_json):
                with open(file_json, "r", encoding="utf-8") as f:
                    sj = json.load(f)
                    consolidated_json_data["segments"].append(sj)
                # Si on n’a pas de .md, on peut reconstruire depuis le JSON
                if (not file_md or not os.path.exists(file_md)) and "content" in sj:
                    fm = sj["content"].get("full_markdown", "")
                    if fm:
                        consolidated_content_md.append(
                            f"<!-- reconstruit depuis JSON -->\n{fm}"
                        )

        # 2.a) Parcours normal via progress['chunk_files']
        had_any = False
        for _, seg in sorted(self.progress.get("chunk_files", {}).items(), key=lambda x: x[0] if isinstance(x[0], int) else 0):
            had_any = True
            file_md = seg.get("file_md") or seg.get("file")  # compat
            file_json = seg.get("file_json")
            _ingest_segment_paths(file_md, file_json)

        # 2.b) Fallback : anciens noms "segment_XXX_pYY_paddle.json"
        if not had_any or (not consolidated_content_md and not consolidated_json_data["segments"]):
            import glob, re
            pattern = os.path.join(self.temp_dir, "segment_*_p??_paddle.json")
            for p in sorted(glob.glob(pattern)):
                # Essaie un .md du même index s’il existe
                m = re.search(r"segment_(\d+)_p\d+_paddle\.json$", os.path.basename(p))
                file_md = None
                if m:
                    idx = int(m.group(1))
                    cand_md = os.path.join(self.temp_dir, f"segment_{idx:03d}.md")
                    file_md = cand_md if os.path.exists(cand_md) else None
                _ingest_segment_paths(file_md, p)

        # En-tête + merge
        metadata_header_md = f"""<!-- OCR METADATA
        Fichier source: {self.pdf_info['filename']}
        Date d'extraction: {datetime.now().isoformat()}
        Nombre de pages: {self.pdf_info['num_pages']}
        Segments traités: {self.progress['completed_chunks']}/{self.progress['total_segments']}
        Mode: Segmentation intelligente LogCard
        OCR Engine: PaddleOCR 3.1.0
        -->"""

        # 1) Markdown reconstruit depuis les segments rec_* (nouveau schéma)
        md_from_segments = self._paddle_result_to_markdown(consolidated_json_data, conf_thresh=0.30)

        # 2) (Optionnel) concaténer avec tout éventuel MD déjà lu (si tu conserves le support .md)
        final_content_md = "\n\n".join([t for t in (md_from_segments, "\n\n".join(consolidated_content_md)) if t])

        final_content_with_metadata = metadata_header_md + "\n\n" + (final_content_md or "")

        # Sauvegarde MD
        with open(self.final_markdown_path, "w", encoding="utf-8") as f:
            f.write(final_content_with_metadata)

        # Sauvegarde JSON (inchangé)
        self.final_json_path = os.path.join(
            self.output_dir,
            f"{os.path.splitext(os.path.basename(self.final_markdown_path))[0]}.json"
        )
        with open(self.final_json_path, "w", encoding="utf-8") as f:
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

                #extractor.cleanup_temp_files()
                pass
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