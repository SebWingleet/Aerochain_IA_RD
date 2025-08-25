import glob
import json
import os

def rebuild_final_json(temp_dir, out_json):
    data = {"segments": []}
    for f in sorted(glob.glob(os.path.join(temp_dir, "*.json"))):
        with open(f, "r", encoding="utf-8") as fh:
            seg = json.load(f)
        data["segments"].append(seg)
    with open(out_json, "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
    print(f"✅ JSON reconstruit: {out_json}")

rebuild_final_json(
    r"C:\Users\lilia\Desktop\freelance\clients\Wingleet\Projet_DEV_Lilian\scripts\main_scripts\WORKFLOW_RESULTS\workflow_LOGCARDS-INVENTORYLOGBOOKDataSet_20250818_192037\phase1_ocr\temp_segments",
    r"C:\Users\lilia\Desktop\freelance\clients\Wingleet\Projet_DEV_Lilian\scripts\main_scripts\WORKFLOW_RESULTS\workflow_LOGCARDS-INVENTORYLOGBOOKDataSet_20250818_192037\phase1_ocr\LOGCARDS-INVENTORYLOGBOOKDataSet_ocr_result.json"
)

