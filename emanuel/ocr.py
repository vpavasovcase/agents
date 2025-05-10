import pytesseract
from pdf2image import convert_from_path

# Pretvori PDF u slike
images = convert_from_path("/app/emanuel/docs/ocr/FileDownloadServlet.pdf")

# Ekstraktaj tekst OCR-om
text_content = ""
for img in images:
    text_content += pytesseract.image_to_string(img, lang='hrv') + "\n\n"

# Spremi tekst u novi dokument
with open("/app/emanuel/docs/sources/9919479387/ocr_output.txt", "w", encoding="utf-8") as f:
    f.write(text_content)