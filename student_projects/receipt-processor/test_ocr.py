import asyncio
import os
from pathlib import Path

import pytesseract
from PIL import Image, ImageDraw, ImageFont

from noa.app import perform_ocr, ROOT_DIR


def create_test_receipt_image():
    """Create a test receipt image for OCR testing."""
    # Create a new image with white background
    width, height = 600, 800
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)

    # Try to use a default font
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 20)
    except IOError:
        # Fallback to default
        font = ImageFont.load_default()

    # Draw receipt content
    receipt_text = [
        "GROCERY STORE",
        "123 Main Street",
        "City, State 12345",
        "Tel: (123) 456-7890",
        "",
        "Date: 2023-12-15  Time: 14:30",
        "Receipt #: 1234567890",
        "",
        "ITEMS:",
        "--------------------------------",
        "Milk                    $3.99",
        "Bread                   $2.49",
        "Eggs (dozen)            $4.29",
        "Apples (1lb)            $2.99",
        "Bananas (1lb)           $1.29",
        "Chicken Breast (2lb)   $12.99",
        "Pasta                   $1.79",
        "Tomato Sauce            $2.29",
        "--------------------------------",
        "Subtotal:              $32.12",
        "Tax (8%):               $2.57",
        "--------------------------------",
        "TOTAL:                 $34.69",
        "",
        "Payment Method: Credit Card",
        "Card #: XXXX-XXXX-XXXX-1234",
        "",
        "Thank you for shopping with us!",
        "Please come again."
    ]

    y_position = 50
    for line in receipt_text:
        draw.text((50, y_position), line, fill='black', font=font)
        y_position += 25

    # Save the image
    ROOT_DIR.mkdir(exist_ok=True, parents=True)

    image_path = ROOT_DIR / "test_receipt.jpg"
    image.save(image_path)

    print(f"Test receipt image created at: {image_path}")
    return image_path


async def test_ocr():
    """Test the OCR functionality."""
    # Create a test receipt image
    image_path = create_test_receipt_image()

    # Perform OCR on the image
    print("\nPerforming OCR on test receipt image...")
    ocr_text = perform_ocr(str(image_path))

    # Print the OCR results
    print("\nOCR Results:")
    print("-" * 40)
    print(ocr_text)
    print("-" * 40)

    # Check if key elements were extracted
    key_elements = ["GROCERY STORE", "Date", "TOTAL", "34.69", "Credit Card"]
    found_elements = [element for element in key_elements if element in ocr_text]

    print(f"\nFound {len(found_elements)}/{len(key_elements)} key elements")
    print(f"OCR accuracy: {len(found_elements)/len(key_elements)*100:.1f}%")


if __name__ == "__main__":
    asyncio.run(test_ocr())
