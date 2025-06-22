from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from youtubesearchpython import VideosSearch, Suggestions
import re
import json
from django.views.decorators.csrf import csrf_exempt
from .models import PlayedVideo
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
import os
import tempfile
import logging
from django.views.decorators.http import require_GET
import yt_dlp
from django.utils.text import slugify
from urllib.parse import unquote
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.conf import settings
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from urllib.parse import urlparse
import requests


def format_view_count(view_count_text):
    """Format view count to show K, M notation"""
    if not view_count_text:
        return ""

    # Extract numbers from view count text
    numbers = re.findall(r"[\d,]+", str(view_count_text))
    if not numbers:
        return ""

    try:
        count = int(numbers[0].replace(",", ""))
        if count >= 1000000:
            return f"{count / 1000000:.1f}M"
        elif count >= 1000:
            return f"{count / 1000:.1f}K"
        else:
            return str(count)
    except (ValueError, IndexError):
        return ""


def process_video_data(video):
    """Process and enhance video data"""
    processed_video = video.copy()

    # Ensure view count is properly formatted
    if "viewCount" in video and video["viewCount"]:
        if isinstance(video["viewCount"], dict):
            view_text = video["viewCount"].get("simpleText", "") or video[
                "viewCount"
            ].get("text", "")
        else:
            view_text = str(video["viewCount"])

        processed_video["shortViews"] = format_view_count(view_text)
    else:
        processed_video["shortViews"] = ""

    # Ensure duration is available
    if "duration" not in processed_video or not processed_video["duration"]:
        processed_video["duration"] = ""

    # Ensure channel info is available
    if "channel" not in processed_video or not processed_video["channel"]:
        processed_video["channel"] = {"name": "Unknown Channel"}

    return processed_video


def extract_youtube_id(url):
    """Extract YouTube video ID from various YouTube URL formats"""
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|music\.youtube\.com\/watch\?v=)([^&\n?#]+)",
        r"(?:localhost|127\.0\.0\.1).*?\/([a-zA-Z0-9_-]{11})",  # For localhost URLs with video ID
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_video_metadata(video_id):
    """Get video metadata using multiple fallback methods"""
    try:
        # Method 1: Try using YouTube oEmbed API
        import json

        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url, timeout=5)

        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", f"Video {video_id}"),
                "published": "Unknown Date",  # oEmbed doesn't provide this
                "duration": "Unknown Duration",  # oEmbed doesn't provide this
                "views": "Unknown Views",  # oEmbed doesn't provide this
                "channel": data.get("author_name", "Unknown Channel"),
                "thumbnail": data.get(
                    "thumbnail_url",
                    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                ),
            }
    except Exception as e:
        print(f"oEmbed method failed: {e}")

    try:
        # Method 2: Try searching for a similar video using the video ID
        search = VideosSearch(video_id, limit=5)
        results = search.result().get("result", [])

        # Look for exact match by checking if video ID is in the URL
        for video in results:
            video_url = video.get("link", "")
            if video_id in video_url:
                return {
                    "title": video.get("title", f"Video {video_id}"),
                    "published": video.get("publishedTime", "Unknown Date"),
                    "duration": video.get("duration", "Unknown Duration"),
                    "views": video.get("viewCount", {}).get("text", "Unknown Views"),
                    "channel": video.get("channel", {}).get("name", "Unknown Channel"),
                    "thumbnail": video.get("thumbnails", [{}])[-1].get("url", ""),
                }
    except Exception as e:
        print(f"Search method failed: {e}")

    # Method 3: Fallback metadata with video ID
    return {
        "title": f"Video {video_id}",
        "published": "Unknown Date",
        "duration": "Unknown Duration",
        "views": "Unknown Views",
        "channel": "Unknown Channel",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
    }


def detect_platform(url):
    """Detect the platform from URL"""
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "music.youtube.com" in url:
        return "youtube_music"
    elif "localhost" in url or "127.0.0.1" in url:
        return "localhost"
    else:
        return "unknown"


def search_results(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return render(
            request,
            "search/search_results.html",
            {"error": "No search query provided", "query": query},
        )

    is_url = False
    validator = URLValidator()
    try:
        validator(query)
        is_url = True
    except ValidationError:
        p = urlparse(query)
        if p.scheme and p.netloc:
            is_url = True

    if is_url:
        # Process URL
        platform = detect_platform(query)
        video_id = extract_youtube_id(query)

        context = {
            "raw_url": query,
            "platform": platform,
            "video_id": video_id,
            "is_supported_platform": platform
            in ["youtube", "youtube_music", "localhost"],
        }

        # Get video metadata if we have a video ID
        if video_id and context["is_supported_platform"]:
            try:
                context["video_metadata"] = get_video_metadata(video_id)
            except Exception as e:
                print(f"Error getting video metadata: {e}")
                context["metadata_error"] = f"Could not fetch video metadata: {str(e)}"

        return render(request, "search/url_input.html", context)

    # Otherwise, treat as text search
    context = {"query": query}
    try:
        videos = VideosSearch(query, limit=20).result().get("result", [])
        processed = [
            process_video_data(v) for v in videos if v
        ]  # Filter out None values
        context.update(
            {
                "type": "search",
                "results": processed,
                "results_count": len(processed),
                "platform": "youtube",
            }
        )
    except Exception as e:
        context["error"] = f"Search failed: {str(e)}"

    return render(request, "search/search_results.html", context)


def process_video_data_url(video):
    """Process video data from search results with safe extraction"""
    if not video:
        return None

    try:
        return {
            "id": video.get("id", ""),
            "title": video.get("title", "Unknown Title"),
            "channel": (
                video.get("channel", {}).get("name", "Unknown Channel")
                if isinstance(video.get("channel"), dict)
                else str(video.get("channel", "Unknown Channel"))
            ),
            "duration": video.get("duration", "Unknown Duration"),
            "views": (
                video.get("viewCount", {}).get("text", "Unknown Views")
                if isinstance(video.get("viewCount"), dict)
                else str(video.get("viewCount", "Unknown Views"))
            ),
            "published": video.get("publishedTime", "Unknown Date"),
            "thumbnail": (
                video.get("thumbnails", [{}])[-1].get("url", "")
                if video.get("thumbnails")
                else ""
            ),
            "url": video.get("link", ""),
        }
    except Exception as e:
        print(f"Error processing video data: {e}")
        return None


def search_video(request):
    """API endpoint for AJAX requests with pagination support"""
    if request.method == "GET":
        query = request.GET.get("q", "").strip()
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 20))

        if not query:
            return JsonResponse({"error": "No query provided"}, status=400)

        try:
            videosSearch = VideosSearch(query, limit=limit)

            # Navigate to the requested page
            for _ in range(page - 1):
                try:
                    videosSearch.next()
                except Exception as e:
                    # Handle case where there are no more pages
                    return JsonResponse(
                        {
                            "type": "search",
                            "results": [],
                            "platform": "youtube",
                            "page": page,
                            "has_more": False,
                            "error": "No more pages available",
                        }
                    )

            search_result = videosSearch.result()
            results = search_result.get("result", [])

            processed_results = [process_video_data_url(video) for video in results]

            # Check if there are more pages available
            has_more = False
            try:
                # Try to peek at the next page to see if it exists
                temp_search = VideosSearch(query, limit=limit)
                for _ in range(page):
                    temp_search.next()
                next_result = temp_search.result()
                has_more = len(next_result.get("result", [])) > 0
            except:
                has_more = False

            return JsonResponse(
                {
                    "type": "search",
                    "results": processed_results,
                    "platform": "youtube",
                    "page": page,
                    "has_more": has_more,
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


def get_video_metadata(request):
    """Get additional metadata for a specific video"""
    if request.method == "GET":
        video_id = request.GET.get("id", "")

        if not video_id:
            return JsonResponse({"error": "No video ID provided"}, status=400)

        try:
            metadata = {
                "id": video_id,
                "thumbnail_hq": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                "thumbnail_mq": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg",
                "thumbnail_default": f"https://img.youtube.com/vi/{video_id}/default.jpg",
                "watch_url": f"https://www.youtube.com/watch?v={video_id}",
                "embed_url": f"https://www.youtube.com/embed/{video_id}",
            }

            return JsonResponse({"success": True, "metadata": metadata})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


@csrf_exempt
def suggest_videos(request):
    query = request.GET.get("q", "").strip()

    if not query:
        return JsonResponse({"suggestions": []})

    try:
        suggestions = Suggestions(language="en", region="US").get(query)
        return JsonResponse({"suggestions": suggestions})
    except Exception as e:
        return JsonResponse({"error": str(e), "suggestions": []}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def track_video_play(request):
    """
    Track when a video is played
    Expected JSON payload: {
        "video_id": "youtube_video_id",
        "title": "Video Title",
        "channel": "Channel Name" (optional)
    }
    """
    try:
        data = json.loads(request.body)
        video_id = data.get("video_id")
        title = data.get("title")
        channel = data.get("channel")

        if not video_id or not title:
            return JsonResponse(
                {"success": False, "error": "video_id and title are required"},
                status=400,
            )

        # Increment play count
        video = PlayedVideo.increment_play_count(
            video_id=video_id, title=title, channel=channel
        )

        return JsonResponse(
            {
                "success": True,
                "play_count": video.play_count,
                "video_id": video.video_id,
            }
        )

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)
