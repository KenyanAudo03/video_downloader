from django.shortcuts import render
from django.http import JsonResponse
from youtubesearchpython import VideosSearch
import re
import requests
from urllib.parse import urlparse, parse_qs


def detect_platform(url):
    """Detect which social media platform the URL belongs to"""
    url_lower = url.lower()

    if re.match(
        r"(https?://)?(www\.)?(youtube\.com|youtu\.be|music\.youtube\.com)/", url_lower
    ):
        return "youtube"
    elif re.match(r"(https?://)?(www\.)?(tiktok\.com|vm\.tiktok\.com)/", url_lower):
        return "tiktok"
    elif re.match(r"(https?://)?(www\.)?(instagram\.com|instagr\.am)/", url_lower):
        return "instagram"
    elif re.match(
        r"(https?://)?(www\.)?(facebook\.com|fb\.com|m\.facebook\.com)/", url_lower
    ):
        return "facebook"
    elif re.match(r"(https?://)?(www\.)?(twitter\.com|x\.com)/", url_lower):
        return "twitter"
    elif re.match(r"(https?://)?(www\.)?twitch\.tv/", url_lower):
        return "twitch"
    elif re.match(r"(https?://)?(www\.)?vimeo\.com/", url_lower):
        return "vimeo"

    return "unknown"


def is_social_media_url(query):
    """Check if the query is a social media URL"""
    return detect_platform(query) != "unknown"


def extract_youtube_id(url):
    """Extract video ID from YouTube URL (including YouTube Music)"""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",  # Standard YouTube URLs
        r"(?:embed\/)([0-9A-Za-z_-]{11})",  # Embed URLs
        r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",  # Short URLs
        r"(?:music\.youtube\.com.*[?&]v=)([0-9A-Za-z_-]{11})",  # YouTube Music
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_tiktok_id(url):
    """Extract TikTok video ID from URL"""
    patterns = [
        r"tiktok\.com.*\/video\/(\d+)",
        r"vm\.tiktok\.com\/([A-Za-z0-9]+)",
        r"tiktok\.com\/@[\w.-]+\/video\/(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_instagram_id(url):
    """Extract Instagram post ID from URL"""
    patterns = [
        r"instagram\.com\/p\/([A-Za-z0-9_-]+)",
        r"instagram\.com\/reel\/([A-Za-z0-9_-]+)",
        r"instagram\.com\/tv\/([A-Za-z0-9_-]+)",
        r"instagr\.am\/p\/([A-Za-z0-9_-]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_facebook_id(url):
    """Extract Facebook video/post ID from URL"""
    patterns = [
        r"facebook\.com.*\/videos\/(\d+)",
        r"facebook\.com.*\/posts\/(\d+)",
        r"fb\.com.*\/videos\/(\d+)",
        r"facebook\.com.*fbid=(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def extract_twitter_id(url):
    """Extract Twitter/X tweet ID from URL"""
    patterns = [
        r"(?:twitter\.com|x\.com)\/\w+\/status\/(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_platform_metadata(platform, url, content_id):
    """Get metadata for different platforms"""
    metadata = {
        "platform": platform,
        "url": url,
        "content_id": content_id,
        "thumbnail_url": None,
        "title": None,
        "description": None,
        "duration": None,
        "author": None,
    }

    if platform == "youtube":
        metadata.update(
            {
                "embed_url": f"https://www.youtube.com/embed/{content_id}",
                "thumbnail_url": f"https://img.youtube.com/vi/{content_id}/mqdefault.jpg",
                "watch_url": f"https://www.youtube.com/watch?v={content_id}",
            }
        )
    elif platform == "tiktok":
        metadata.update(
            {
                "embed_url": f"https://www.tiktok.com/embed/v2/{content_id}",
                "watch_url": url,
            }
        )
    elif platform == "instagram":
        metadata.update(
            {
                "embed_url": f"https://www.instagram.com/p/{content_id}/embed/",
                "watch_url": f"https://www.instagram.com/p/{content_id}/",
            }
        )
    elif platform == "facebook":
        metadata.update(
            {
                "watch_url": url,
                # Facebook embed requires app ID, so we'll just link to the post
            }
        )
    elif platform == "twitter":
        metadata.update(
            {
                "embed_url": f"https://platform.twitter.com/embed/Tweet.html?id={content_id}",
                "watch_url": url,
            }
        )

    return metadata


def search_form(request):
    """Render the main search form page"""
    return render(request, "search/search_form.html")


def search_results(request):
    """Handle search results and render results page"""
    query = request.GET.get("q", "").strip()

    if not query:
        context = {"error": "No search query provided", "query": query}
        return render(request, "search/search_results.html", context)

    context = {"query": query}

    try:
        if is_social_media_url(query):
            # Handle social media URL
            platform = detect_platform(query)
            content_id = None

            if platform == "youtube":
                content_id = extract_youtube_id(query)
            elif platform == "tiktok":
                content_id = extract_tiktok_id(query)
            elif platform == "instagram":
                content_id = extract_instagram_id(query)
            elif platform == "facebook":
                content_id = extract_facebook_id(query)
            elif platform == "twitter":
                content_id = extract_twitter_id(query)

            if content_id:
                metadata = get_platform_metadata(platform, query, content_id)
                context.update(
                    {
                        "type": "social_media",
                        "metadata": metadata,
                    }
                )
            else:
                context["error"] = (
                    f"Could not extract content ID from {platform.title()} URL"
                )
        else:
            # Handle search query - search YouTube by default
            try:
                videosSearch = VideosSearch(query, limit=10)
                results = videosSearch.result().get("result", [])
                context.update(
                    {
                        "type": "search",
                        "results": results,
                        "results_count": len(results),
                        "platform": "youtube",  # Default search platform
                    }
                )
            except Exception as e:
                context["error"] = f"Search failed: {str(e)}"

    except Exception as e:
        context["error"] = f"An error occurred: {str(e)}"

    return render(request, "search/search_results.html", context)


def search_video(request):
    """API endpoint for AJAX requests"""
    if request.method == "GET":
        query = request.GET.get("q", "")
        if not query:
            return JsonResponse({"error": "No query provided"}, status=400)

        if is_social_media_url(query):
            platform = detect_platform(query)
            content_id = None

            if platform == "youtube":
                content_id = extract_youtube_id(query)
            elif platform == "tiktok":
                content_id = extract_tiktok_id(query)
            elif platform == "instagram":
                content_id = extract_instagram_id(query)
            elif platform == "facebook":
                content_id = extract_facebook_id(query)
            elif platform == "twitter":
                content_id = extract_twitter_id(query)

            if content_id:
                metadata = get_platform_metadata(platform, query, content_id)
                return JsonResponse({"type": "social_media", "metadata": metadata})
            return JsonResponse(
                {"error": f"Invalid {platform.title()} URL"}, status=400
            )
        else:
            try:
                videosSearch = VideosSearch(query, limit=5)
                results = videosSearch.result().get("result", [])
                return JsonResponse(
                    {"type": "search", "results": results, "platform": "youtube"}
                )
            except Exception as e:
                return JsonResponse({"error": str(e)}, status=500)


def get_platform_info(request):
    """API endpoint to get platform information from URL"""
    if request.method == "GET":
        url = request.GET.get("url", "")
        if not url:
            return JsonResponse({"error": "No URL provided"}, status=400)

        platform = detect_platform(url)
        return JsonResponse(
            {"platform": platform, "is_supported": platform != "unknown", "url": url}
        )


# Additional utility functions for enhanced functionality


def get_url_title(url):
    """Fetch page title from URL (basic implementation)"""
    try:
        response = requests.get(
            url,
            timeout=5,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        if response.status_code == 200:
            import re

            title_match = re.search(
                r"<title>(.*?)</title>", response.text, re.IGNORECASE
            )
            if title_match:
                return title_match.group(1).strip()
    except:
        pass
    return None


def validate_social_url(url):
    """Validate if social media URL is accessible"""
    try:
        response = requests.head(
            url,
            timeout=5,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            },
        )
        return response.status_code == 200
    except:
        return False
