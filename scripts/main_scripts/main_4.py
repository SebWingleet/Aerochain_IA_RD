#!/usr/bin/env python3
"""
main_4.py - Orchestrateur du workflow complet
Responsabilité : Coordonne les phases 1 et 2, interface utilisateur unifiée
Permet d'exécuter une phase spécifique ou le workflow complet
Version mise à jour avec support de configuration de structure
"""

import os
import json
import argparse
import sys
from datetime import datetime


# Importer les classes des deux phases

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ocr_extraction'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'logcard_analyzer'))

from ocr_extractor_3 import Phase1OCRExtractor
from logcard_analyzer_4 import Phase2LogCardAnalyzer

class WorkflowOrchestrator:
    def __init__(self, api_key, output_base_dir="WORKFLOW_RESULTS"):
        """
        Initialise l'orchestrateur de workflow
        
        Args:
            api_key (str): Clé API Mistral
            output_base_dir (str): Dossier de base pour tous les résultats
        """
        self.api_key = api_key
        self.output_base_dir = output_base_dir
        
        # Créer le dossier de base
        os.makedirs(self.output_base_dir, exist_ok=True)
        
        # États du workflow
        self.workflow_info = None
        self.workflow_dir = None
        self.phase1_extractor = None
        self.phase2_analyzer = None
    
    def run_full_workflow(self, pdf_path, structure_config_path=None, keep_temp=False):
        """
        Exécute le workflow complet : PDF → Markdown → JSON LogCards
        
        Args:
            pdf_path (str): Chemin vers le PDF
            structure_config_path (str): Chemin vers le fichier de configuration de structure (optionnel)
            keep_temp (bool): Conserver les fichiers temporaires
            
        Returns:
            dict: Résultats du workflow complet
        """
        
        print("🚀 WORKFLOW COMPLET : PDF → MARKDOWN → LOGCARDS")
        print("="*60)
        
        # Initialiser le workflow
        if not self._setup_workflow(pdf_path):
            return None
        
        print(f"📁 Dossier de workflow: {self.workflow_dir}")
        
        # Afficher la configuration si fournie
        if structure_config_path:
            print(f"📋 Configuration de structure: {structure_config_path}")
        
        # Phase 1: OCR
        phase1_result = self.run_phase1_only(pdf_path, structure_config_path)
        if not phase1_result or not phase1_result['success']:
            print("❌ Phase 1 (OCR) a échoué - arrêt du workflow")
            return {
                'success': False,
                'phase1_completed': False,
                'phase2_completed': False,
                'error': 'Phase 1 échouée',
                'workflow_directory': self.workflow_dir
            }
        
        print(f"\n✅ Phase 1 terminée - JSON: {phase1_result['json_file']}")
        
        # Phase 2: LogCard Analysis
        phase2_result = self.run_phase2_only(phase1_result['json_file'])
        if not phase2_result or not phase2_result['success']:
            print("❌ Phase 2 (LogCard) a échoué")
            return {
                'success': False,
                'phase1_completed': True,
                'phase2_completed': False,
                'phase1_result': phase1_result,
                'error': 'Phase 2 échouée',
                'workflow_directory': self.workflow_dir
            }
        
        print(f"\n✅ Phase 2 terminée - JSON: {phase2_result['json_file']}")
        
        # Créer le résumé final du workflow
        workflow_summary = self._create_workflow_summary(phase1_result, phase2_result)
        
        # Nettoyage optionnel
        if not keep_temp:
            self._cleanup_workflow_temp_files(phase1_result, phase2_result)
        
        return {
            'success': True,
            'phase1_completed': True,
            'phase2_completed': True,
            'phase1_result': phase1_result,
            'phase2_result': phase2_result,
            'workflow_summary': workflow_summary,
            'workflow_directory': self.workflow_dir,
            'final_files': {
                'json': phase1_result['json_file'],
                'logcards': phase2_result['json_file'],
                'summary': workflow_summary['summary_file']
            }
        }
    
    def run_phase1_only(self, pdf_path, structure_config_path=None):
        """
        Exécute seulement la Phase 1 : PDF → Markdown
        
        Args:
            pdf_path (str): Chemin vers le PDF
            structure_config_path (str): Chemin vers le fichier de configuration de structure (optionnel)
            
        Returns:
            dict: Résultats de la Phase 1
        """
        
        print("\n🔍 PHASE 1 SEULEMENT : PDF → MARKDOWN")
        print("-" * 40)
        
        # Initialiser le workflow si pas déjà fait
        if not self.workflow_dir:
            self._setup_workflow(pdf_path)
        
        # Créer l'extracteur Phase 1
        phase1_output_dir = os.path.join(self.workflow_dir, "phase1_ocr")
        self.phase1_extractor = Phase1OCRExtractor(self.api_key, phase1_output_dir)
        
        # Exécuter l'extraction avec configuration de structure
        result = self.phase1_extractor.extract_pdf_to_markdown(
            pdf_path=pdf_path,
            structure_config_path=structure_config_path,
            output_dir=phase1_output_dir
        )
        
        if result and result['success']:
            print(f"✅ Phase 1 réussie: {result['markdown_file']}")
        else:
            print(f"❌ Phase 1 échouée")
        
        return result
    
    def run_phase2_only(self, json_path):
        """
        Exécute seulement la Phase 2 : Markdown → JSON LogCards
        
        Args:
            markdown_path (str): Chemin vers le Markdown
            
        Returns:
            dict: Résultats de la Phase 2
        """
        
        print("\n🏷️ PHASE 2 SEULEMENT : MARKDOWN → LOGCARDS")
        print("-" * 40)
        
        # Initialiser le workflow si pas déjà fait
        if not self.workflow_dir:
            # Créer un workflow basé sur le fichier Markdown
            json_name = os.path.splitext(os.path.basename(json_path))[0]
            safe_name = "".join(c for c in json_name if c.isalnum() or c in ('-', '_')).rstrip()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.workflow_dir = os.path.join(self.output_base_dir, f"workflow_{safe_name}_{timestamp}")
            os.makedirs(self.workflow_dir, exist_ok=True)
        
        # Créer l'analyseur Phase 2
        phase2_output_dir = os.path.join(self.workflow_dir, "phase2_logcard")
        self.phase2_analyzer = Phase2LogCardAnalyzer(self.api_key, phase2_output_dir)
        
        # Exécuter l'analyse
        result = self.phase2_analyzer.analyze_markdown_to_logcards(
            json_path=json_path,
            output_dir=phase2_output_dir
        )
        
        if result and result['success']:
            print(f"✅ Phase 2 réussie: {result['json_file']}")
        else:
            print(f"❌ Phase 2 échouée")
        
        return result
    
    def _setup_workflow(self, pdf_path):
        """Configure l'environnement de workflow"""
        
        if not os.path.exists(pdf_path):
            print(f"❌ Fichier PDF non trouvé: {pdf_path}")
            return False
        
        # Créer le dossier de workflow
        pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
        safe_name = "".join(c for c in pdf_name if c.isalnum() or c in ('-', '_')).rstrip()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.workflow_dir = os.path.join(self.output_base_dir, f"workflow_{safe_name}_{timestamp}")
        os.makedirs(self.workflow_dir, exist_ok=True)
        
        # Informations du workflow
        self.workflow_info = {
            'workflow_name': f"workflow_{safe_name}_{timestamp}",
            'source_pdf': pdf_path,
            'start_time': datetime.now().isoformat(),
            'workflow_directory': self.workflow_dir
        }
        
        # Sauvegarder les infos du workflow
        workflow_info_file = os.path.join(self.workflow_dir, "workflow_info.json")
        with open(workflow_info_file, 'w', encoding='utf-8') as f:
            json.dump(self.workflow_info, f, indent=2, ensure_ascii=False)
        
        return True
    
    def _create_workflow_summary(self, phase1_result, phase2_result):
        """Crée un résumé complet du workflow"""
        
        # Lire les LogCards pour les statistiques
        logcard_stats = {}
        if phase2_result and phase2_result['success'] and os.path.exists(phase2_result['json_file']):
            try:
                with open(phase2_result['json_file'], 'r', encoding='utf-8') as f:
                    logcard_data = json.load(f)
                    logcard_stats = {
                        'total_logcards': len(logcard_data.get('logCards', [])),
                        'sample_logcards': []
                    }
                    
                    # Échantillon de LogCards pour l'aperçu
                    for logcard in logcard_data.get('logCards', [])[:5]:
                        logcard_info = logcard.get('logCardData', {})
                        logcard_stats['sample_logcards'].append({
                            'logcard_number': logcard.get('logCard'),
                            'name': logcard_info.get('Name', 'N/A'),
                            'serial': logcard_info.get('SN', 'N/A'),
                            'ata': logcard_info.get('ATA', 'N/A'),
                            'pages': logcard.get('pageNumbers', [])
                        })
            except:
                logcard_stats = {'error': 'Impossible de lire les statistiques LogCard'}
        
        # Créer le résumé
        summary = {
            'workflow_info': self.workflow_info,
            'completion_time': datetime.now().isoformat(),
            'phase1_summary': {
                'success': phase1_result['success'] if phase1_result else False,
                'markdown_file': phase1_result.get('markdown_file') if phase1_result else None,
                'segments_processed': phase1_result.get('segments_processed') if phase1_result else 0,
                'total_segments': phase1_result.get('total_segments') if phase1_result else 0
            },
            'phase2_summary': {
                'success': phase2_result['success'] if phase2_result else False,
                'json_file': phase2_result.get('json_file') if phase2_result else None,
                'logcards_processed': phase2_result.get('logcards_processed') if phase2_result else 0,
                'total_logcards': phase2_result.get('total_logcards') if phase2_result else 0
            },
            'logcard_statistics': logcard_stats,
            'final_files': {
                'markdown_result': phase1_result.get('markdown_file') if phase1_result else None,
                'json_result': phase2_result.get('json_file') if phase2_result else None
            }
        }
        
        # Sauvegarder le résumé
        summary_file = os.path.join(self.workflow_dir, "workflow_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        summary['summary_file'] = summary_file
        return summary
    
    def _cleanup_workflow_temp_files(self, phase1_result, phase2_result):
        """Nettoie les fichiers temporaires des deux phases"""
        
        print("🧹 Nettoyage des fichiers temporaires...")
        
        # Nettoyer Phase 1
        if self.phase1_extractor:
            try:
                self.phase1_extractor.cleanup_temp_files()
            except Exception as e:
                print(f"⚠️  Erreur nettoyage Phase 1: {e}")
        
        # Nettoyer Phase 2
        if self.phase2_analyzer:
            try:
                self.phase2_analyzer.cleanup_temp_files()
            except Exception as e:
                print(f"⚠️  Erreur nettoyage Phase 2: {e}")
        
        print("✅ Nettoyage terminé")
    
    def get_workflow_status(self):
        """Retourne le statut actuel du workflow"""
        return {
            'workflow_info': self.workflow_info,
            'workflow_directory': self.workflow_dir,
            'phase1_extractor': self.phase1_extractor is not None,
            'phase2_analyzer': self.phase2_analyzer is not None
        }

def main():
    """Interface CLI pour l'orchestrateur de workflow"""
    
    parser = argparse.ArgumentParser(description="Orchestrateur de workflow PDF → LogCards JSON")
    
    # Arguments principaux
    parser.add_argument('--pdf', help="Chemin vers le fichier PDF (requis pour --full ou --phase1-only)")
    parser.add_argument('--json', help="Chemin vers le fichier JSON (requis pour --phase2-only)")
    parser.add_argument('--api-key', help="Clé API Mistral (ou variable d'environnement MISTRAL_API_KEY)")
    parser.add_argument('--output-dir', help="Dossier de sortie de base (défaut: WORKFLOW_RESULTS)")
    
    # Modes d'exécution
    execution_group = parser.add_mutually_exclusive_group(required=True)
    execution_group.add_argument('--full', action='store_true', help="Workflow complet (Phase 1 + Phase 2)")
    execution_group.add_argument('--phase1-only', action='store_true', help="Seulement Phase 1 (PDF → Markdown)")
    execution_group.add_argument('--phase2-only', action='store_true', help="Seulement Phase 2 (Markdown → LogCards)")
    
    # Options supplémentaires (modifiées pour la nouvelle fonctionnalité)
    parser.add_argument('--structure-config', help="Chemin vers le fichier de configuration de structure JSON")
    parser.add_argument('--keep-temp', action='store_true', help="Conserver les fichiers temporaires")
    
    args = parser.parse_args()
    
    # Validation des arguments
    if args.full or args.phase1_only:
        if not args.pdf:
            print("❌ --pdf requis pour --full ou --phase1-only")
            return

    if args.phase2_only:
        if not args.json:
            print("❌ --json requis pour --phase2-only")
            return
    
    # Récupérer la clé API
    api_key = args.api_key or os.getenv('MISTRAL_API_KEY') or "siKCdUiCHdqVO0v7paXDqgcEhB6aefky"
    if not api_key:
        api_key = input("🔑 Entrez votre clé API Mistral: ").strip()
        if not api_key:
            print("❌ Clé API requise")
            return
    
    # Vérifier les fichiers d'entrée
    if args.pdf and not os.path.exists(args.pdf):
        print(f"❌ Fichier PDF non trouvé: {args.pdf}")
        return
    
    if args.json and not os.path.exists(args.json):
        print(f"❌ Fichier JSON non trouvé: {args.json}")
        return
    
    # Vérifier le fichier de configuration de structure si fourni
    if args.structure_config and not os.path.exists(args.structure_config):
        print(f"❌ Fichier de configuration de structure non trouvé: {args.structure_config}")
        return
    
    # Créer l'orchestrateur
    output_base_dir = args.output_dir or "WORKFLOW_RESULTS"
    orchestrator = WorkflowOrchestrator(api_key, output_base_dir)
    
    try:
        # Exécuter selon le mode choisi
        if args.full:
            print("🚀 MODE: Workflow complet (PDF → JSON → LogCards)")
            if args.structure_config:
                print(f"📋 Utilisation de la configuration: {args.structure_config}")
            
            result = orchestrator.run_full_workflow(
                pdf_path=args.pdf,
                structure_config_path=args.structure_config,
                keep_temp=args.keep_temp
            )
            
            if result and result['success']:
                print(f"\n🎉 WORKFLOW COMPLET RÉUSSI!")
                print(f"📁 Dossier: {result['workflow_directory']}")
                print(f"📄 Markdown: {result['final_files']['markdown']}")
                print(f"🏷️ JSON LogCards: {result['final_files']['json']}")
                print(f"📋 Résumé: {result['final_files']['summary']}")
                
                # Statistiques détaillées
                phase1 = result['phase1_result']
                phase2 = result['phase2_result']
                print(f"\n📊 STATISTIQUES:")
                print(f"   🔍 Phase 1: {phase1['segments_processed']}/{phase1['total_segments']} segments OCR")
                print(f"   🏷️  Phase 2: {phase2['logcards_processed']}/{phase2['total_logcards']} LogCards")
                
                # Aperçu des LogCards
                summary = result['workflow_summary']
                logcard_stats = summary.get('logcard_statistics', {})
                if 'sample_logcards' in logcard_stats:
                    print(f"\n📋 APERÇU DES LOGCARDS ({logcard_stats['total_logcards']} total):")
                    for lc in logcard_stats['sample_logcards']:
                        print(f"   🏷️  LogCard {lc['logcard_number']}: {lc['name']} (S/N: {lc['serial']}, ATA: {lc['ata']})")
            else:
                print(f"\n❌ Workflow échoué")
                if result:
                    print(f"Phase 1: {'✅' if result['phase1_completed'] else '❌'}")
                    print(f"Phase 2: {'✅' if result['phase2_completed'] else '❌'}")
                    if result.get('error'):
                        print(f"Erreur: {result['error']}")
        
        elif args.phase1_only:
            print("🔍 MODE: Phase 1 seulement (PDF → JSON)")
            if args.structure_config:
                print(f"📋 Utilisation de la configuration: {args.structure_config}")
            
            result = orchestrator.run_phase1_only(
                pdf_path=args.pdf,
                structure_config_path=args.structure_config
            )
            
            if result and result['success']:
                print(f"\n🎉 PHASE 1 RÉUSSIE!")
                print(f"📄 JSON: {result['json_file']}")
                print(f"📁 Dossier: {result['output_directory']}")
                print(f"📊 Segments: {result['segments_processed']}/{result['total_segments']}")
                
                if not args.keep_temp:
                    orchestrator.phase1_extractor.cleanup_temp_files()
            else:
                print(f"\n❌ Phase 1 échouée")
        
        elif args.phase2_only:
            print("🏷️ MODE: Phase 2 seulement (JSON → LogCards)")
            result = orchestrator.run_phase2_only(json_path=args.json)
            
            if result and result['success']:
                print(f"\n🎉 PHASE 2 RÉUSSIE!")
                print(f"🏷️ JSON LogCards: {result['json_file']}")
                print(f"📁 Dossier: {result['output_directory']}")
                print(f"📊 LogCards: {result['logcards_processed']}/{result['total_logcards']}")
                
                # Aperçu des LogCards
                if os.path.exists(result['json_file']):
                    with open(result['json_file'], 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        total = data['documentInfo']['totalLogCards']
                        print(f"\n📋 {total} LOGCARDS EXTRAITES:")
                        
                        for i, logcard in enumerate(data['logCards'][:3]):
                            lc_data = logcard.get('logCardData', {})
                            name = lc_data.get('Name', 'N/A')
                            serial = lc_data.get('SN', 'N/A')
                            print(f"   🏷️  LogCard {logcard['logCard']}: {name} (S/N: {serial})")
                        
                        if total > 3:
                            print(f"   ... et {total - 3} autres")
                
                if not args.keep_temp:
                    orchestrator.phase2_analyzer.cleanup_temp_files()
            else:
                print(f"\n❌ Phase 2 échouée")
        
        # Affichage final des fichiers créés
        status = orchestrator.get_workflow_status()
        if status['workflow_directory']:
            print(f"\n📁 FICHIERS DANS: {status['workflow_directory']}")
            
            # Lister les fichiers principaux
            if os.path.exists(status['workflow_directory']):
                files = []
                for root, dirs, filenames in os.walk(status['workflow_directory']):
                    for filename in filenames:
                        if filename.endswith(('.md', '.json')) and not filename.startswith('temp'):
                            rel_path = os.path.relpath(os.path.join(root, filename), status['workflow_directory'])
                            files.append(rel_path)
                
                if files:
                    print("📄 Fichiers principaux:")
                    for file in sorted(files):
                        icon = "📄" if file.endswith('.md') else "🏷️" if 'logcard' in file else "📋"
                        print(f"   {icon} {file}")
    
    except KeyboardInterrupt:
        print("\n⏹️  Workflow interrompu")
        status = orchestrator.get_workflow_status()
        if status['workflow_directory']:
            print(f"📁 Progression sauvegardée dans: {status['workflow_directory']}")
            print("🔄 Vous pouvez reprendre avec les phases individuelles")
    
    except Exception as e:
        print(f"\n💥 Erreur inattendue: {e}")
        status = orchestrator.get_workflow_status()
        if status['workflow_directory']:
            print(f"📁 Fichiers de débogage dans: {status['workflow_directory']}")
    
    print("\n👋 Au revoir!")

def demonstrate_usage():
    """Affiche des exemples d'utilisation"""
    
    print("🏷️ EXEMPLES D'UTILISATION DU WORKFLOW")
    print("="*50)
    print()
    
    print("1️⃣  WORKFLOW COMPLET (recommandé):")
    print("   python main_4.py --full --pdf document.pdf")
    print()
    
    print("2️⃣  WORKFLOW AVEC CONFIGURATION DE STRUCTURE:")
    print("   python main_4.py --full --pdf document.pdf --structure-config structure.json")
    print()
    
    print("3️⃣  PHASE 1 SEULEMENT (PDF → Markdown):")
    print("   python main_4.py --phase1-only --pdf document.pdf")
    print("   python main_4.py --phase1-only --pdf document.pdf --structure-config structure.json")
    print()
    
    print("4️⃣  PHASE 2 SEULEMENT (Markdown → LogCards):")
    print("   python main_4.py --phase2-only --json document_ocr.json")
    print()
    
    print("5️⃣  AVEC OPTIONS:")
    print("   python main_4.py --full --pdf doc.pdf --structure-config config.json --keep-temp")
    print("   python main_4.py --full --pdf doc.pdf --output-dir /mon/dossier")
    print()
    
    print("🔑 CONFIGURATION API:")
    print("   export MISTRAL_API_KEY='votre_clé'")
    print("   # ou utilisez --api-key votre_clé")
    print()
    
    print("📋 FICHIER DE CONFIGURATION STRUCTURE (structure.json):")
    print('   {')
    print('     "document_structure": {')
    print('       "title_pages": [1, 2],')
    print('       "logcard_start_page": 3,')
    print('       "default_logcard_size": 2,')
    print('       "isolated_logcards": [')
    print('         {"page": 31, "size": 1}')
    print('       ],')
    print('       "non_logcard_pages": [103, 104, 105]')
    print('     }')
    print('   }')
    print()
    
    print("📁 STRUCTURE DE SORTIE:")
    print("   WORKFLOW_RESULTS/")
    print("   └─ workflow_nom_timestamp/")
    print("      ├─ phase1_ocr/")
    print("      │  └─ nom_ocr_result.json")
    print("      ├─ phase2_logcard/")
    print("      │  └─ nom_logcards.json")
    print("      ├─ workflow_info.json")
    print("      └─ workflow_summary.json")

if __name__ == "__main__":
    # Si aucun argument, afficher les exemples
    if len(sys.argv) == 1:
        demonstrate_usage()
    else:
        main()

# python3 main_3.py --full --pdf "/Users/sebastienbatty/Documents/1_Wingleet/2_DEV/THC/INPUT_DOCS/LOG CARDS - INVENTORY LOG BOOK.pdf" --structure-config "/Users/sebastienbatty/Documents/1_Wingleet/2_DEV/THC/scripts/config_extraction.json" --output-dir "/Users/sebastienbatty/Documents/1_Wingleet/2_DEV/THC/TEST/" --keep-temp