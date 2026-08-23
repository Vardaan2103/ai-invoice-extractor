import json
import os
import re
import time
from pathlib import Path

from google import genai
from google.genai import types
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from dotenv import load_dotenv
from PIL import Image

from .forms import UploadForm
from .models import Upload

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError(
        "GOOGLE_API_KEY not found. Copy .env.example to .env and add your key."
    )

client = genai.Client(api_key=GOOGLE_API_KEY)
MODEL_NAME = "gemini-2.0-flash"

GENERATE_CONFIG = types.GenerateContentConfig(
    temperature=0.2,
    top_p=1,
    top_k=32,
    max_output_tokens=4096,
    safety_settings=[
        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_MEDIUM_AND_ABOVE"),
    ],
)

SYSTEM_PROMPT = """
You are a specialist in comprehending receipts and invoices.
Input images in the form of receipts or invoices will be provided to you.
Your task is to extract specific fields from the invoice and return them in JSON format.
"""

USER_PROMPT = """
Extract the following fields from the invoice:
- Invoice Number
- Invoice Date
- Total Amount
- Vendor Name
- Itemized List (if applicable)

Return the data in JSON format with the following keys:
{
"invoice_number": "value",
"invoice_date": "value",
"invoice_due_date": "value",
"Discount": "value",
"total_amount": "value",
"vendor_name": "value",
"itemized_list": [
    {"item_name": "value", "item_quantity": "value", "item_price": "value", "item_amount": "value"}
]
}

If any field is missing or cannot be extracted, use "null" for that field.
"""


def image_format(image_path):
    """Read an image file from disk and package it as a Gemini content Part."""
    img = Path(image_path)
    if not img.exists():
        raise FileNotFoundError(f"Could not find image: {img}")

    ext = img.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }

    if ext not in mime_types:
        raise ValueError(f"Unsupported image format: {ext}")

    return types.Part.from_bytes(data=img.read_bytes(), mime_type=mime_types[ext])


def pdf_to_combined_image(pdf_path, output_image_path):
    """Render every page of a PDF into one stacked PNG so multi-page invoices
    can be sent to Gemini as a single image."""
    import fitz  # PyMuPDF, imported lazily since it's only needed for PDFs

    doc = fitz.open(pdf_path)
    images = []

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap()
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    width = max(img.width for img in images)
    height = sum(img.height for img in images)

    combined_image = Image.new("RGB", (width, height))
    y_offset = 0
    for img in images:
        combined_image.paste(img, (0, y_offset))
        y_offset += img.height

    combined_image.save(output_image_path)
    return output_image_path


def gemini_output(image_path, system_prompt, user_prompt):
    image_part = image_format(image_path)
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[system_prompt, image_part, user_prompt],
            config=GENERATE_CONFIG,
        )
        return response.text
    except Exception as e:
        raise ValueError(f"Error generating content from the model: {e}")


def process_invoice(invoice_path, system_prompt, user_prompt):
    output = gemini_output(invoice_path, system_prompt, user_prompt)
    if not output.strip():
        raise ValueError("The AI model returned an empty response.")
    return output


def retry_with_timeout(func, retries=3, delay=5):
    for attempt in range(retries):
        try:
            return func()
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
            else:
                raise


def home(request):
    return render(request, "Homepage.html")


def upload_file(request):
    if request.method == "POST" and request.FILES:
        form = UploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded_file = form.cleaned_data["uploaded_file"]
            file_path = os.path.join(settings.MEDIA_ROOT, uploaded_file.name)

            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            with open(file_path, "wb") as f:
                for chunk in uploaded_file.chunks():
                    f.write(chunk)

            if uploaded_file.name.lower().endswith(".pdf"):
                image_path = file_path.replace(".pdf", "_combined_image.png")
                pdf_to_combined_image(file_path, image_path)
            else:
                image_path = file_path

            try:
                output = retry_with_timeout(
                    lambda: process_invoice(image_path, SYSTEM_PROMPT, USER_PROMPT),
                    retries=3,
                    delay=5,
                )
                output_cleaned = re.sub(r"```json|```", "", output).strip()

                try:
                    upload_instance = Upload(
                        file_name=uploaded_file.name,
                        uploaded_file=uploaded_file,
                        json_data=json.loads(output_cleaned),
                    )
                    upload_instance.save()
                    return render(
                        request,
                        "success_message.html",
                        {"output_cleaned": output_cleaned},
                    )
                except json.JSONDecodeError:
                    return HttpResponse(
                        f"Failed to decode JSON from the model output: {output_cleaned}"
                    )
            except Exception as e:
                return HttpResponse(f"An error occurred: {e}")
    else:
        form = UploadForm()

    return render(request, "upload_file.html", {"form": form})


def file_list(request):
    files = Upload.objects.all().order_by("-uploaded_at")
    return render(request, "file_list.html", {"files": files})
