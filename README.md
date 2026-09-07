# PDF Downloader - Django

A database-free Django web application that:

- Uploads `.xlsx` / `.xls` files through a Dropzone-style frontend.
- Reads the `URL` column.
- Downloads all PDF URLs.
- Shows live Success / Failed / Downloading / Pending counts.
- Shows per-PDF progress.
- Supports Stop and Resume during the running server process.
- Skips already completed PDFs when resumed.
- Allows individual PDF downloads.
- Creates a ZIP containing all successfully downloaded PDFs.
- Uses no database.

## 1. Install

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If PowerShell blocks activation, use:

```powershell
venv\Scripts\activate.bat
```

## 2. Run

```powershell
python manage.py runserver
```

Open:

http://127.0.0.1:8000/

## Excel format

The Excel file must contain a column named:

```text
URL
```

Example:

| URL |
|---|
| https://example.com/file1.pdf |
| https://example.com/file2.pdf?abc=123 |

The filename is taken from the final URL path segment. Query strings are ignored.

## Important limitation

This version intentionally uses no database. Job information is kept in server memory, and downloaded files are kept in the local `downloads/` directory.

Therefore:

- Stop/Resume works while the same Django process is running.
- Restarting the Django server loses the job list/state.
- On serverless hosting such as Vercel, local files and long-running background downloads are not reliable/persistent.

For a production deployment that needs hundreds/thousands of PDFs, persistent storage and a background worker/server are recommended.

## Configuration

Edit `pdf_downloader/settings.py`:

```python
DOWNLOAD_TIMEOUT = 45
DOWNLOAD_RETRIES = 3
MAX_WORKERS = 4
```

`MAX_WORKERS` controls how many PDFs download simultaneously.

## Security / production

Before production:

- Change `SECRET_KEY`.
- Set `DEBUG = False`.
- Set proper `ALLOWED_HOSTS`.
- Put the app behind a production WSGI/ASGI server.
- Use persistent object/file storage if downloads must survive restarts.
