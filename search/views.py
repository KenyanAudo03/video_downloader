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


def search_results(request):
    """Handle search results and render results page"""
    query = request.GET.get("q", "").strip()

    if not query:
        context = {"error": "No search query provided", "query": query}
        return render(request, "search/search_results.html", context)

    context = {"query": query}

    try:
        # Search YouTube videos
        videosSearch = VideosSearch(query, limit=20)
        search_result = videosSearch.result()
        results = search_result.get("result", [])

        # Process video data to ensure proper formatting
        processed_results = [process_video_data(video) for video in results]

        context.update(
            {
                "type": "search",
                "results": processed_results,
                "results_count": len(processed_results),
                "platform": "youtube",
            }
        )

    except Exception as e:
        context["error"] = f"Search failed: {str(e)}"

    return render(request, "search/search_results.html", context)


def search_video(request):
    """API endpoint for AJAX requests with pagination support"""
    if request.method == "GET":
        query = request.GET.get("q", "").strip()
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 20))  # bump it up, default to 20

        if not query:
            return JsonResponse({"error": "No query provided"}, status=400)

        try:
            videosSearch = VideosSearch(query, limit=limit)

            for _ in range(page - 1):
                videosSearch.next()

            search_result = videosSearch.result()
            results = search_result.get("result", [])

            processed_results = [process_video_data(video) for video in results]

            has_more = (
                len(results) == limit
                and videosSearch.result().get("nextPageToken") is not None
            )

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
