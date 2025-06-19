from django.shortcuts import render

# Create your views here.


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import json
import yt_dlp
import os
import threading
from urllib.parse import urlparse
from .models import UserSession, VideoDownload
import uuid


def get_or_create_session(request):
    session_id = request.session.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session["session_id"] = session_id

    ip_address = request.META.get(
        "HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "127.0.0.1")
    )
    if ip_address:
        ip_address = ip_address.split(",")[0].strip()

    session, created = UserSession.objects.get_or_create(
        session_id=session_id, defaults={"ip_address": ip_address}
    )
    return session


def detect_platform(url):
    domain = urlparse(url).netloc.lower()
    if "youtube.com" in domain or "youtu.be" in domain:
        return "youtube"
    elif "instagram.com" in domain:
        return "instagram"
    elif "tiktok.com" in domain:
        return "tiktok"
    elif "twitter.com" in domain or "x.com" in domain:
        return "twitter"
    elif "facebook.com" in domain or "fb.com" in domain:
        return "facebook"
    elif "vimeo.com" in domain:
        return "vimeo"
    else:
        return "other"


def index(request):
    session = get_or_create_session(request)
    recent_downloads = VideoDownload.objects.filter(session=session)[:10]
    return render(
        request, "downloader/download_page.html", {"recent_downloads": recent_downloads}
    )


@csrf_exempt
@require_http_methods(["POST"])
def get_video_info(request):
    try:
        data = json.loads(request.body)
        url = data.get("url")

        if not url:
            return JsonResponse({"error": "URL is required"}, status=400)

        session = get_or_create_session(request)
        platform = detect_platform(url)

        # Create download record
        download = VideoDownload.objects.create(
            session=session,
            original_url=url,
            platform=platform,
            quality=data.get("quality", "best"),
        )

        # Get video info using yt-dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }

        def process_video():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    download.title = info.get("title", "Unknown Title")
                    download.description = info.get("description", "")[:500]
                    download.thumbnail_url = info.get("thumbnail", "")
                    download.duration = str(info.get("duration", 0))
                    download.status = "completed"
                    download.save()

            except Exception as e:
                download.status = "failed"
                download.error_message = str(e)
                download.save()

        # Start processing in background
        thread = threading.Thread(target=process_video)
        thread.start()

        return JsonResponse({"download_id": str(download.id), "status": "processing"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def check_status(request, download_id):
    try:
        download = get_object_or_404(VideoDownload, id=download_id)

        return JsonResponse(
            {
                "status": download.status,
                "title": download.title,
                "thumbnail_url": download.thumbnail_url,
                "duration": download.duration,
                "error_message": download.error_message,
                "download_url": (
                    f"/download/{download_id}/"
                    if download.status == "completed"
                    else None
                ),
            }
        )

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def download_video(request, download_id):
    try:
        download = get_object_or_404(VideoDownload, id=download_id)

        if download.status != "completed":
            return JsonResponse({"error": "Video not ready for download"}, status=400)

        # Update download count
        download.download_count += 1
        download.save()

        # Setup download directory
        download_dir = os.path.join(
            settings.DOWNLOAD_DIR, str(download.session.session_id)
        )
        os.makedirs(download_dir, exist_ok=True)

        # Configure yt-dlp options
        ydl_opts = {
            "format": download.quality if download.quality != "best" else "best",
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
        }

        # Handle audio-only downloads
        if download.quality == "audio":
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]

        def download_video_file():
            try:
                download.status = "processing"
                download.save()

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(download.original_url, download=True)

                    # Find the downloaded file
                    filename = ydl.prepare_filename(info)
                    if download.quality == "audio":
                        filename = filename.rsplit(".", 1)[0] + ".mp3"

                    if os.path.exists(filename):
                        download.file_path = filename
                        download.file_size = os.path.getsize(filename)
                        download.status = "completed"
                    else:
                        download.status = "failed"
                        download.error_message = "File not found after download"

                    download.save()

            except Exception as e:
                download.status = "failed"
                download.error_message = str(e)
                download.save()

        # Start download in background
        thread = threading.Thread(target=download_video_file)
        thread.start()

        return JsonResponse({"status": "processing", "download_id": str(download.id)})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def serve_download(request, download_id):
    try:
        download = get_object_or_404(VideoDownload, id=download_id)

        if not download.file_path or not os.path.exists(download.file_path):
            raise Http404("File not found")

        # Serve the file
        with open(download.file_path, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/octet-stream")
            filename = os.path.basename(download.file_path)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

    except Exception as e:
        raise Http404("File not found")


@require_http_methods(["GET"])
def download_history(request):
    session = get_or_create_session(request)
    downloads = VideoDownload.objects.filter(session=session)

    downloads_data = []
    for download in downloads:
        downloads_data.append(
            {
                "id": str(download.id),
                "title": download.title,
                "platform": download.platform,
                "status": download.status,
                "created_at": download.created_at.isoformat(),
                "download_count": download.download_count,
                "thumbnail_url": download.thumbnail_url,
                "original_url": download.original_url,
            }
        )

    return JsonResponse({"downloads": downloads_data})
