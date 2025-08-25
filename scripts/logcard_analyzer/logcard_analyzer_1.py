#!/usr/bin/env python3
"""
phase2_logcard_analyzer.py - Analyseur LogCard spécialisé
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
        
        pages