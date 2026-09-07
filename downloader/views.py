import json
import os
import threading
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse, unquote

import pandas as pd
import requests
from django.conf import settings
from django.http import FileResponse, JsonResponse, Http404
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

# In-memory job store: no database is used.
JOBS = {}
JOBS_LOCK = threading.Lock()


def index(request):
    return render(request, "index.html")


def safe_filename_from_url(url):
    path = urlparse(url).path
    name = unquote(os.path.basename(path)).strip()
    if not name:
        name = "download.pdf"

    # Windows-invalid filename characters
    for ch in '<>:"/\\|?*':
        name = name.replace(ch, "_")

    if not name.lower().endswith(".pdf"):
        name += ".pdf"

    # Avoid hidden/odd names
    if name in (".pdf", ""):
        name = "download.pdf"

    return name


def unique_filename(name, used):
    base = Path(name).stem
    ext = Path(name).suffix or ".pdf"
    candidate = name
    n = 2
    while candidate.lower() in used:
        candidate = f"{base}_{n}{ext}"
        n += 1
    used.add(candidate.lower())
    return candidate


def create_job(rows):
    job_id = uuid.uuid4().hex
    job_dir = Path(settings.MEDIA_ROOT) / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    used = set()
    pdfs = []
    for i, url in enumerate(rows, start=1):
        filename = unique_filename(safe_filename_from_url(url), used)
        pdfs.append({
            "id": i,
            "url": url,
            "filename": filename,
            "status": "pending",
            "progress": 0,
            "error": "",
        })

    job = {
        "id": job_id,
        "dir": str(job_dir),
        "pdfs": pdfs,
        "status": "ready",
        "stop_event": threading.Event(),
        "thread": None,
        "zip_path": None,
    }

    with JOBS_LOCK:
        JOBS[job_id] = job
    return job


def get_job(job_id):
    with JOBS_LOCK:
        return JOBS.get(job_id)


def update_pdf(job, pdf_id, **kwargs):
    with JOBS_LOCK:
        for pdf in job["pdfs"]:
            if pdf["id"] == pdf_id:
                pdf.update(kwargs)
                return


def download_one(job, pdf):
    if job["stop_event"].is_set():
        return

    file_path = Path(job["dir"]) / pdf["filename"]
    tmp_path = file_path.with_suffix(file_path.suffix + ".part")

    # Resume logic: completed existing files are skipped.
    if file_path.exists() and file_path.stat().st_size > 0:
        update_pdf(job, pdf["id"], status="success", progress=100, error="")
        return

    headers = {"User-Agent": "Mozilla/5.0 PDF Downloader/1.0"}

    for attempt in range(1, settings.DOWNLOAD_RETRIES + 1):
        if job["stop_event"].is_set():
            update_pdf(job, pdf["id"], status="pending")
            return

        try:
            update_pdf(job, pdf["id"], status="downloading", progress=0, error="")
            with requests.get(
                pdf["url"],
                headers=headers,
                timeout=settings.DOWNLOAD_TIMEOUT,
                stream=True,
                allow_redirects=True,
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if job["stop_event"].is_set():
                            f.close()
                            try:
                                tmp_path.unlink()
                            except FileNotFoundError:
                                pass
                            update_pdf(job, pdf["id"], status="pending", progress=0)
                            return

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            progress = int(downloaded * 100 / total) if total else 0
                            update_pdf(job, pdf["id"], progress=progress)

            if tmp_path.exists():
                tmp_path.replace(file_path)
            update_pdf(job, pdf["id"], status="success", progress=100, error="")
            return

        except Exception as exc:
            try:
                tmp_path.unlink()
            except FileNotFoundError:
                pass

            if attempt == settings.DOWNLOAD_RETRIES:
                update_pdf(
                    job,
                    pdf["id"],
                    status="failed",
                    progress=0,
                    error=str(exc)[:500],
                )
            else:
                update_pdf(job, pdf["id"], status="retrying", progress=0, error=str(exc)[:500])


def build_zip(job):
    zip_path = Path(job["dir"]) / f"pdf_downloads_{job['id'][:8]}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for pdf in job["pdfs"]:
            if pdf["status"] == "success":
                file_path = Path(job["dir"]) / pdf["filename"]
                if file_path.exists():
                    zf.write(file_path, arcname=pdf["filename"])
    job["zip_path"] = str(zip_path)


def run_job(job):
    with JOBS_LOCK:
        job["status"] = "running"

    pending = [p for p in job["pdfs"] if p["status"] != "success"]

    with ThreadPoolExecutor(max_workers=settings.MAX_WORKERS) as executor:
        futures = [executor.submit(download_one, job, pdf) for pdf in pending]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception:
                pass
            if job["stop_event"].is_set():
                # Other workers see the event and stop at the next chunk.
                pass

    with JOBS_LOCK:
        stopped = job["stop_event"].is_set()
        success = sum(p["status"] == "success" for p in job["pdfs"])
        failed = sum(p["status"] == "failed" for p in job["pdfs"])

        if stopped:
            job["status"] = "stopped"
        elif success + failed == len(job["pdfs"]):
            job["status"] = "completed"
        else:
            job["status"] = "ready"

    if job["status"] == "completed":
        build_zip(job)


def launch_job(job):
    if job["thread"] and job["thread"].is_alive():
        return False

    job["stop_event"].clear()
    thread = threading.Thread(target=run_job, args=(job,), daemon=True)
    job["thread"] = thread
    thread.start()
    return True


@csrf_exempt
@require_POST
def upload_excel(request):
    excel = request.FILES.get("file")
    if not excel:
        return JsonResponse({"ok": False, "error": "Please upload an Excel file."}, status=400)

    if not excel.name.lower().endswith((".xlsx", ".xls")):
        return JsonResponse({"ok": False, "error": "Only .xlsx and .xls files are supported."}, status=400)

    try:
        df = pd.read_excel(excel)
    except Exception as exc:
        return JsonResponse({"ok": False, "error": f"Could not read Excel: {exc}"}, status=400)

    # Case-insensitive URL column detection.
    url_column = next((c for c in df.columns if str(c).strip().lower() == "url"), None)
    if url_column is None:
        return JsonResponse({
            "ok": False,
            "error": f"Missing 'URL' column. Found: {list(df.columns)}"
        }, status=400)

    rows = []
    for value in df[url_column].tolist():
        if pd.isna(value):
            continue
        url = str(value).strip()
        if url:
            rows.append(url)

    if not rows:
        return JsonResponse({"ok": False, "error": "No URLs found in the URL column."}, status=400)

    job = create_job(rows)
    return JsonResponse({
        "ok": True,
        "job_id": job["id"],
        "total": len(rows),
        "message": "Excel uploaded successfully."
    })


@csrf_exempt
@require_POST
def start_job(request, job_id):
    job = get_job(job_id)
    if not job:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)
    if job["status"] in ("running", "completed"):
        return JsonResponse({"ok": True, "status": job["status"]})
    launch_job(job)
    return JsonResponse({"ok": True, "status": "running"})


@csrf_exempt
@require_POST
def stop_job(request, job_id):
    job = get_job(job_id)
    if not job:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    job["stop_event"].set()
    return JsonResponse({"ok": True, "status": "stopping"})


@csrf_exempt
@require_POST
def resume_job(request, job_id):
    job = get_job(job_id)
    if not job:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    # Reset failed items to pending so resume retries them.
    with JOBS_LOCK:
        for pdf in job["pdfs"]:
            if pdf["status"] in ("failed", "retrying", "stopped"):
                pdf["status"] = "pending"
                pdf["progress"] = 0
                pdf["error"] = ""

    job["stop_event"].clear()
    launch_job(job)
    return JsonResponse({"ok": True, "status": "running"})


@require_GET
def job_status(request, job_id):
    job = get_job(job_id)
    if not job:
        return JsonResponse({"ok": False, "error": "Job not found."}, status=404)

    with JOBS_LOCK:
        pdfs = [dict(p) for p in job["pdfs"]]
        status = job["status"]

    total = len(pdfs)
    success = sum(p["status"] == "success" for p in pdfs)
    failed = sum(p["status"] == "failed" for p in pdfs)
    downloading = sum(p["status"] in ("downloading", "retrying") for p in pdfs)
    pending = total - success - failed - downloading

    return JsonResponse({
        "ok": True,
        "job_id": job_id,
        "status": status,
        "total": total,
        "success": success,
        "failed": failed,
        "downloading": downloading,
        "pending": max(0, pending),
        "zip_ready": bool(job.get("zip_path") and Path(job["zip_path"]).exists()),
        "pdfs": pdfs,
    })


@require_GET
def download_single_pdf(request, job_id, pdf_id):
    job = get_job(job_id)
    if not job:
        raise Http404("Job not found.")

    pdf = next((p for p in job["pdfs"] if p["id"] == pdf_id), None)
    if not pdf:
        raise Http404("PDF not found.")

    path = Path(job["dir"]) / pdf["filename"]
    if not path.exists():
        raise Http404("PDF has not been downloaded successfully yet.")

    return FileResponse(
        open(path, "rb"),
        as_attachment=True,
        filename=pdf["filename"],
        content_type="application/pdf",
    )


@require_GET
def download_zip(request, job_id):
    job = get_job(job_id)
    if not job:
        raise Http404("Job not found.")

    if not job.get("zip_path") or not Path(job["zip_path"]).exists():
        # Generate from currently successful PDFs if needed.
        if any(p["status"] == "success" for p in job["pdfs"]):
            build_zip(job)
        else:
            raise Http404("ZIP is not ready.")

    return FileResponse(
        open(job["zip_path"], "rb"),
        as_attachment=True,
        filename=Path(job["zip_path"]).name,
        content_type="application/zip",
    )
