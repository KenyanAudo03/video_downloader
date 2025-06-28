from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import logging
import re
from youtubesearchpython import VideosSearch, Suggestions

logger = logging.getLogger(__name__)


def extract_video_id(url):
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|music\.youtube\.com\/watch\?v=|youtube\.com\/shorts\/)([^&\n?#]+)",
        r"(?:localhost|127\.0\.0\.1).*?\/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def home(request):
    return render(request, "audio/home.html")


@require_http_methods(["POST"])
@csrf_exempt
def search_youtube(request):
    if request.method == "POST":
        query = request.POST.get("query", "").strip()
        if not query:
            return JsonResponse({"error": "Query parameter is required"}, status=400)

        search_query = query
        if query.startswith(
            (
                "http://",
                "https://",
                "www.",
                "youtube.com",
                "youtu.be",
                "music.youtube.com",
                "localhost",
                "127.0.0.1",
            )
        ):
            video_id = extract_video_id(query)
            if video_id:
                search_query = video_id
            else:
                return JsonResponse(
                    {"error": "Invalid URL, Use YouTube's URL or Localhost's URL"},
                    status=400,
                )

        try:
            videos_search = VideosSearch(
                search_query, limit=20, language="en", region="US"
            )
            results = videos_search.result()

            if not results or "result" not in results or not results["result"]:
                return JsonResponse(
                    {"error": "No available videos to play as audio"}, status=404
                )

            videos = []
            for item in results["result"]:
                try:
                    description = "No description available"
                    if item.get("descriptionSnippet"):
                        desc_parts = [
                            snippet.get("text", "")
                            for snippet in item["descriptionSnippet"]
                        ]
                        description = " ".join(desc_parts).strip()

                    thumbnail_url = ""
                    if item.get("thumbnails"):
                        thumbnail_url = item["thumbnails"][-1].get("url", "")

                    channel_name = "Unknown Channel"
                    if item.get("channel") and item["channel"].get("name"):
                        channel_name = item["channel"]["name"]

                    duration = item.get("duration", "")
                    view_count = item.get("viewCount", {}).get("text", "")

                    video = {
                        "id": item.get("id", ""),
                        "title": item.get("title", "Unknown Title"),
                        "description": description,
                        "thumbnail": thumbnail_url,
                        "channel": channel_name,
                        "published": item.get("publishedTime", ""),
                        "duration": duration,
                        "viewCount": view_count,
                        "url": item.get(
                            "link",
                            f"https://www.youtube.com/watch?v={item.get('id', '')}",
                        ),
                    }
                    videos.append(video)

                except Exception as item_error:
                    logger.warning(f"Error processing video item: {item_error}")
                    continue

            if videos:
                return JsonResponse({"videos": videos, "total": len(videos)})
            else:
                return JsonResponse({"error": "No valid videos found"}, status=404)

        except Exception as e:
            logger.error(f"Search error: {e}")
            return JsonResponse({"error": f"Search failed: {str(e)}"}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=405)


@require_http_methods(["GET"])
def get_suggestions(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"suggestions": []})

    try:
        suggestions = Suggestions(language="en", region="US")
        result = suggestions.get(query, mode=1)

        if result and "result" in result:
            return JsonResponse({"suggestions": result["result"]})
        else:
            return JsonResponse({"suggestions": []})

    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        return JsonResponse({"suggestions": []})
