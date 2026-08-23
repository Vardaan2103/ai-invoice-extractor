# AI Invoice Extractor

A Django web app that extracts structured data from invoices and receipts using Google's Gemini vision model. Upload a photo, scan, or PDF of an invoice and get back clean, structured JSON — no manual data entry.

## How it works

1. User uploads an invoice image or PDF through the web UI
2. Multi-page PDFs are stitched into a single image so the whole document can be sent in one request
3. The image is sent to Gemini 2.0 Flash with a prompt instructing it to extract specific invoice fields
4. The model's response is parsed and validated as JSON
5. Results are saved to the database and shown to the user; a history of past uploads is browsable

## Fields extracted

- Invoice number
- Invoice date & due date
- Vendor name
- Discount
- Total amount
- Itemized list (item name, quantity, price, amount)

Missing fields are returned as `null` rather than causing a failure.

## Tech stack

- **Backend:** Django 5.1
- **AI:** Google Gemini 2.0 Flash (`google-genai`)
- **PDF handling:** PyMuPDF (multi-page → single image)
- **Database:** SQLite (swap for Postgres in production)

## Setup

```bash
git clone https://github.com/Vardaan2103/ai-invoice-extractor.git
cd ai-invoice-extractor

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# then edit .env and add your GOOGLE_API_KEY
# get a free key at https://aistudio.google.com/app/apikey

python manage.py migrate
python manage.py runserver
```

Visit `http://127.0.0.1:8000` and upload an invoice.

If you ever add your own CSS/JS or upgrade Django, refresh the collected static files with:

```bash
python manage.py collectstatic --noinput
```

## Project structure

```
ai-invoice-extractor/
├── invoice_extractor/            # Django project
│   ├── apps/
│   │   └── invoices/              # Core app — upload form, model, extraction logic
│   │       ├── views.py           # Gemini calls, PDF handling
│   │       ├── models.py          # Upload model — stores file + extracted JSON
│   │       ├── forms.py
│   │       ├── templates/
│   │       └── migrations/
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── media/                         # Uploaded files (gitignored, created at runtime)
├── static/                        # Your own static assets — empty for now.
│                                   # Add CSS/JS here when you need custom styling.
├── staticfiles/                   # Collected static files (django.contrib.admin's
│                                   # theme — icons, CSS, JS for the /admin/ panel).
│                                   # Generated via `python manage.py collectstatic`.
│                                   # Committed here for convenience; regenerate
│                                   # anytime with the same command if it drifts.
├── manage.py
├── requirements.txt
└── .env.example
```

## Notes on security

- `GOOGLE_API_KEY` and `DJANGO_SECRET_KEY` are loaded from environment variables — never hardcoded. Copy `.env.example` to `.env` and fill in your own.
- `CORS_ALLOW_ALL_ORIGINS` is enabled for local development convenience. Restrict this before deploying anywhere public.
- SQLite is fine for local use and demos; move to Postgres/MySQL for production.

## Possible next steps

- Add authentication so uploads are scoped per user
- Support batch upload of multiple invoices at once
- Export extracted data to CSV/Excel
- Add a confidence score or manual-correction step for extracted fields
