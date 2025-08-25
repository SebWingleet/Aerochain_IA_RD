# AerochainIAR-D

## Lancer l'environnement
-aller a la base du projet et lancer la commande suivante : **pip install -r requirements.txt**
Cela devrait installer toutes les dépendances necessaires.



## Processus Complet
-Se rendre dans "scripts/main_scripts" :
- Entrer cette commande : **python3 main_6_paddleocr.py --full --pdf "[chemindu du pdf contenant les logscards]" --structure-config "[chemin vers le json contenant les configs d'exctraction]"**
Cela va creer un dossier dans "main_scripts/WORKFLOW_RESULTS/"
Le résultats sera dans ce dossier de workflow, dans **"phase2_logcards/LOGCARDS-INVENTORYLOGBOOKDataSet_ocr_result_logcards.json"**

## Verification
-Se rendre dans "scripts/truth_scripts"
-Entrer la commande suivante : **python verification_results_2.py --extracted "[chemin vers le workflow a analyser]\phase2_logcard\LOGCARDS-INVENTORYLOGBOOKDataSet_ocr_result_logcards.json" --ground-truth "[chemin vers le ground_truth.json]"**
Un excel sera creer dans ce meme workflow dans "/phase2_logcards/validation_results"


## Processus Phase par Phase
Pour pouvoir tester des modifications sans avoir a relancer tout le process, on peut executer chaque phase unitairement.
-Premièrement, aller dans "scripts/main_scripts/".
**Phase 1** : 
**Phase 2** (impossible sans phase 1 au préalable): python main_6_paddleocr.py --phase2-only  --json "[chemin vers le workflow déjà commencé]\phase1_ocr\LOGCARDS-INVENTORYLOGBOOKDataSet_ocr_result.json"