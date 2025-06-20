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
import uuid
import tempfile


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
    return render(request, "downloader/download_page.html")


# Store download info in memory (since we removed the model)
download_cache = {}


@csrf_exempt
@require_http_methods(["POST"])
def get_video_info(request):
    try:
        data = json.loads(request.body)
        url = data.get("url")

        if not url:
            return JsonResponse({"error": "URL is required"}, status=400)

        platform = detect_platform(url)
        download_id = str(uuid.uuid4())
        
        # Store initial download info
        download_cache[download_id] = {
            'original_url': url,
            'platform': platform,
            'quality': data.get("quality", "best"),
            'status': 'processing',
            'title': '',
            'thumbnail_url': '',
            'duration': '',
            'error_message': '',
            'file_path': '',
            'file_size': 0
        }

        # Get video info using yt-dlp
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
        }

        def process_video():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)

                    download_cache[download_id].update({
                        'title': info.get("title", "Unknown Title"),
                        'thumbnail_url': info.get("thumbnail", ""),
                        'duration': str(info.get("duration", 0)),
                        'status': 'completed'
                    })

            except Exception as e:
                download_cache[download_id].update({
                    'status': 'failed',
                    'error_message': str(e)
                })

        # Start processing in background
        thread = threading.Thread(target=process_video)
        thread.daemon = True
        thread.start()

        return JsonResponse({"download_id": download_id, "status": "processing"})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def check_status(request, download_id):
    try:
        download_info = download_cache.get(download_id)
        
        if not download_info:
            return JsonResponse({"error": "Download not found"}, status=404)

        return JsonResponse({
            "status": download_info['status'],
            "title": download_info['title'],
            "thumbnail_url": download_info['thumbnail_url'],
            "duration": download_info['duration'],
            "error_message": download_info['error_message'],
            "download_url": f"/download/{download_id}/" if download_info['status'] == 'completed' else None,
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def download_video(request, download_id):
    try:
        download_info = download_cache.get(download_id)
        
        if not download_info:
            return JsonResponse({"error": "Download not found"}, status=404)

        if download_info['status'] != 'completed':
            return JsonResponse({"error": "Video not ready for download"}, status=400)

        # Setup download directory
        download_dir = os.path.join(tempfile.gettempdir(), 'downloads', download_id)
        os.makedirs(download_dir, exist_ok=True)

        # Configure yt-dlp options
        quality = download_info['quality']
        ydl_opts = {
            "format": quality if quality != "best" else "best",
            "outtmpl": os.path.join(download_dir, "%(title)s.%(ext)s"),
        }

        # Handle audio-only downloads
        if quality == "audio":
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
                download_cache[download_id]['status'] = 'downloading'

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(download_info['original_url'], download=True)

                    # Find the downloaded file
                    filename = ydl.prepare_filename(info)
                    if quality == "audio":
                        filename = filename.rsplit(".", 1)[0] + ".mp3"

                    if os.path.exists(filename):
                        download_cache[download_id].update({
                            'file_path': filename,
                            'file_size': os.path.getsize(filename),
                            'status': 'ready'
                        })
                    else:
                        download_cache[download_id].update({
                            'status': 'failed',
                            'error_message': "File not found after download"
                        })

            except Exception as e:
                download_cache[download_id].update({
                    'status': 'failed',
                    'error_message': str(e)
                })

        # Start download in background
        thread = threading.Thread(target=download_video_file)
        thread.daemon = True
        thread.start()

        return JsonResponse({"status": "downloading", "download_id": download_id})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@require_http_methods(["GET"])
def serve_download(request, download_id):
    try:
        download_info = download_cache.get(download_id)
        
        if not download_info or not download_info.get('file_path'):
            raise Http404("File not found")

        file_path = download_info['file_path']
        
        if not os.path.exists(file_path):
            raise Http404("File not found")

        # Serve the file
        with open(file_path, "rb") as f:
            response = HttpResponse(f.read(), content_type="application/octet-stream")
            filename = os.path.basename(file_path)
            response["Content-Disposition"] = f'attachment; filename="{filename}"'
            return response

    except Exception as e:
        raise Http404("File not found")