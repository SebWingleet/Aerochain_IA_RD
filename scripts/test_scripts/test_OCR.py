from pdf2image import convert_from_path
from paddleocr import PaddleOCR
from PIL import Image, ImageEnhance, ImageDraw, ImageFont
import numpy as np
import os

def debug_ocr_page(
    pdf_path: str,
    page_number: int,
    out_path: str = None,
    dpi: int = 300,
    lang: str = "fr",
    draw_text: bool = False,
    min_conf: float = 0.40,
):
    """
    Génère une image de la page avec zones OCR surlignées en rouge.

    Args:
        pdf_path: chemin du PDF
        page_number: numéro 1‑based de la page à analyser
        out_path: chemin du PNG/JPG de sortie (déduit si None)
        dpi: résolution de rendu PDF→image (300 recommandé)
        lang: langue du modèle PaddleOCR ("fr", "en", "fr_en" si mixte)
        draw_text: écrire le texte reconnu à côté des boîtes
        min_conf: confiance minimale pour afficher une boîte
    Returns:
        Chemin du fichier image généré
    """

    main_out_path = r"C:\Users\lilia\Desktop\freelance\clients\Wingleet\Projet_DEV_Lilian\scripts\test_scripts\OCR_Test_results"
    out_path = main_out_path +"/" + "LOG CARDS - INVENTORY LOG BOOK Data Set_p003_highlight.png"
    
    out_path_js = main_out_path +"/" + "LOG CARDS - INVENTORY LOG BOOK Data Set json.json"
    # 1) Charger la page demandée (1-based) en haute résolution
    images = convert_from_path(pdf_path, dpi=dpi, first_page=page_number, last_page=page_number)
    if not images:
        raise RuntimeError("Impossible de rendre la page demandée.")
    img = images[0].convert("RGB")

    # 2) Pré-traitement léger: niveaux/contraste/netteté
    #    (les fonds crème + trame fine bénéficient d’un petit boost)
    img_gray = img.convert("L")
    img_gray = ImageEnhance.Contrast(img_gray).enhance(1.5)   # contraste +50%
    img_gray = ImageEnhance.Sharpness(img_gray).enhance(1.2)  # légère netteté
    # Repasser en RGB pour dessin
    prep = img_gray.convert("RGB")

    # 3) OCR Paddle
    ocr = PaddleOCR(
        use_angle_cls=True,
        lang=lang,

        # Astuces pour docs scannés pâles:
        det_db_box_thresh=0.3,     # accepte des boîtes plus "faibles"
        det_db_thresh=0.25,        # seuil binarisation du det
        det_db_unclip_ratio=1.8,   # un peu plus d'air autour des boîtes
        rec_batch_num=32
    )
    result = ocr.ocr(np.array(prep))
    
    for res in result:  

        res.save_to_img(out_path) 
        res.save_to_json(out_path_js)
 
        print("DONE")






if __name__ == "__main__":
    # Exemple d'usage rapide
    pdf = r"C:\Users\lilia\Desktop\freelance\clients\Wingleet\Projet_DEV_Lilian\INPUT_DOCS\LOG CARDS - INVENTORY LOG BOOK Data Set.pdf"
    out = debug_ocr_page(pdf_path=pdf, page_number=3, draw_text=False)
    print("Image générée:", out)

