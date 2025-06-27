from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import subprocess
import re
import json
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


def media_grabber(request):
    return render(request, "media_grabber/index.html")


@csrf_exempt
@require_http_methods(["POST"])
def extract_video(request):
    try:
        try:
            data = json.loads(request.body)
            video_url = data.get("url", "").strip()
        except json.JSONDecodeError:
            video_url = request.POST.get("url", "").strip()

        if not video_url:
            return JsonResponse({"success": False, "message": "Video URL is required"})

        try:
            parsed_url = urlparse(video_url)
            if not parsed_url.scheme or not parsed_url.netloc:
                return JsonResponse({"success": False, "message": "Invalid URL"})
        except:
            return JsonResponse({"success": False, "message": "Invalid URL"})

        yt_dlp_command = [
            "yt-dlp",
            video_url,
            "--get-url",
            "--get-title",
            "--get-duration",
            "--get-thumbnail",
            "--format",
            "best[ext=mp4]/best",
            "--no-playlist",
            "--no-warnings",
            "--print-json",
        ]

        if "tiktok.com" in video_url.lower():
            yt_dlp_command.extend(["--extractor-args", "tiktok:watermark=none"])

        try:
            result = subprocess.run(
                yt_dlp_command, capture_output=True, text=True, check=True, timeout=45
            )

            output_lines = result.stdout.strip().split("\n")
            if not output_lines:
                return JsonResponse(
                    {"success": False, "message": "Couldn't get video info"}
                )

            video_info = None
            for line in output_lines:
                if line.strip().startswith("{"):
                    video_info = json.loads(line)
                    break

            if video_info:
                direct_url = video_info.get("url", "")
                video_title = video_info.get("title", "Unknown Video")
                duration = str(video_info.get("duration", ""))
                thumbnail = video_info.get("thumbnail", "")
            else:
                direct_url = output_lines[0] if len(output_lines) > 0 else ""
                video_title = (
                    output_lines[1] if len(output_lines) > 1 else "Unknown Video"
                )
                duration = output_lines[2] if len(output_lines) > 2 else ""
                thumbnail = output_lines[3] if len(output_lines) > 3 else ""

            if not direct_url:
                return JsonResponse(
                    {"success": False, "message": "Couldn't get download link"}
                )

        except subprocess.TimeoutExpired:
            return JsonResponse({"success": False, "message": "Request timed out"})
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else str(e)
            if (
                "Unsupported URL" in error_output
                or "No video formats found" in error_output
            ):
                return JsonResponse(
                    {"success": False, "message": "Video not supported or removed"}
                )
            elif "Sign in to confirm your age" in error_output:
                return JsonResponse(
                    {"success": False, "message": "Video requires age verification"}
                )
            elif "Private video" in error_output:
                return JsonResponse(
                    {"success": False, "message": "This video is private"}
                )
            else:
                return JsonResponse(
                    {"success": False, "message": "Failed to process video"}
                )

        clean_title = re.sub(r'[<>:"/\\|?*]', "", video_title)
        clean_title = clean_title[:50] if clean_title else "video"

        platform = "Unknown"
        if "tiktok.com" in video_url.lower():
            platform = "TikTok"
        elif "instagram.com" in video_url.lower():
            platform = "Instagram"
        elif "twitter.com" in video_url.lower() or "x.com" in video_url.lower():
            platform = "Twitter/X"
        elif "facebook.com" in video_url.lower():
            platform = "Facebook"

        return JsonResponse(
            {
                "success": True,
                "download_url": direct_url,
                "title": video_title,
                "platform": platform,
                "duration": duration,
                "thumbnail": thumbnail,
                "filename": f"{clean_title}.mp4",
            }
        )

    except Exception:
        return JsonResponse({"success": False, "message": "Something went wrong"})
