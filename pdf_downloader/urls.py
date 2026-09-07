from django.urls import path
from downloader import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/upload/", views.upload_excel, name="upload_excel"),
    path("api/job/<str:job_id>/start/", views.start_job, name="start_job"),
    path("api/job/<str:job_id>/stop/", views.stop_job, name="stop_job"),
    path("api/job/<str:job_id>/resume/", views.resume_job, name="resume_job"),
    path("api/job/<str:job_id>/status/", views.job_status, name="job_status"),
    path("api/job/<str:job_id>/zip/", views.download_zip, name="download_zip"),
    path("api/job/<str:job_id>/pdf/<int:pdf_id>/", views.download_single_pdf, name="download_single_pdf"),
]
