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
from datetime import datetime, timedelta


def format_view_count(view_count_text):
    if not view_count_text:
        return ""

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


def format_duration(duration):
    if not duration:
        return "Unknown Duration"

    try:
        if isinstance(duration, str):
            if "seconds" in duration:
                duration = int(duration.replace(" seconds", ""))
            elif ":" in duration:
                return duration
            else:
                duration = int(duration)

        duration = int(duration)
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except (ValueError, TypeError):
        return "Unknown Duration"


def format_publish_date(date_str):
    if not date_str or date_str == "Unknown Date":
        return "Unknown Date"

    try:
        date_obj = None

        if isinstance(date_str, str) and len(date_str) == 8 and date_str.isdigit():
            year = int(date_str[:4])
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            date_obj = datetime(year, month, day)

        elif isinstance(date_str, str):
            if any(
                word in date_str.lower()
                for word in ["ago", "yesterday", "today", "hour", "minute", "second"]
            ):
                return date_str

            date_str = date_str.strip()

            date_formats = [
                "%b %d, %Y",
                "%B %d, %Y",
                "%d %b %Y",
                "%d %B %Y",
                "%Y-%m-%d",
                "%m/%d/%Y",
                "%d/%m/%Y",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S.%fZ",
            ]

            if "T" in date_str and ("+" in date_str or date_str.endswith("Z")):
                try:
                    if date_str.endswith("Z"):
                        clean_date = date_str[:-1]
                    elif "+" in date_str:
                        clean_date = date_str.split("+")[0]
                    elif "-" in date_str[-6:]:
                        clean_date = date_str[:-6]
                    else:
                        clean_date = date_str

                    if "." in clean_date:
                        date_obj = datetime.strptime(clean_date, "%Y-%m-%dT%H:%M:%S.%f")
                    else:
                        date_obj = datetime.strptime(clean_date, "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    pass

            if not date_obj:
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue

        if date_obj:
            return get_relative_time(date_obj)
        else:
            print(f"Could not parse date: '{date_str}'")

    except (ValueError, TypeError) as e:
        print(f"Error parsing date '{date_str}': {e}")

    return str(date_str) if date_str else "Unknown Date"


def get_relative_time(date_obj):
    now = datetime.now()

    if date_obj.tzinfo is not None:
        date_obj = date_obj.replace(tzinfo=None)

    if date_obj > now:
        return "Recently published"

    diff = now - date_obj
    total_seconds = int(diff.total_seconds())

    if total_seconds < 60:
        return "Just now"
    elif total_seconds < 3600:
        minutes = total_seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif total_seconds < 604800:
        days = total_seconds // 86400
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif total_seconds < 2629746:
        weeks = total_seconds // 604800
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    elif total_seconds < 31556952:
        months = total_seconds // 2629746
        return f"{months} month{'s' if months != 1 else ''} ago"
    else:
        years = total_seconds // 31556952
        return f"{years} year{'s' if years != 1 else ''} ago"


def format_view_count_full(view_count):
    if not view_count:
        return "Unknown Views"

    try:
        if isinstance(view_count, str):
            numbers = re.findall(r"[\d,]+", view_count)
            if numbers:
                count = int(numbers[0].replace(",", ""))
                return f"{count:,} views"
        elif isinstance(view_count, int):
            return f"{view_count:,} views"
    except (ValueError, TypeError):
        pass

    return str(view_count) if view_count else "Unknown Views"


def process_video_data(video):
    processed_video = video.copy()

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

    if "duration" not in processed_video or not processed_video["duration"]:
        processed_video["duration"] = ""

    if "channel" not in processed_video or not processed_video["channel"]:
        processed_video["channel"] = {"name": "Unknown Channel"}

    return processed_video


def extract_youtube_id(url):
    patterns = [
        r"(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/|youtube\.com\/v\/|music\.youtube\.com\/watch\?v=|youtube\.com\/shorts\/)([^&\n?#]+)",
        r"(?:localhost|127\.0\.0\.1).*?\/([a-zA-Z0-9_-]{11})",
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_video_metadata_by_id(video_id):
    try:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )

            duration = format_duration(info.get("duration"))
            upload_date = info.get("upload_date")
            published = (
                format_publish_date(upload_date) if upload_date else "Unknown Date"
            )
            views = format_view_count_full(info.get("view_count"))

            return {
                "title": info.get("title", f"Video {video_id}"),
                "published": published,
                "duration": duration,
                "views": views,
                "channel": info.get("uploader", "Unknown Channel"),
                "thumbnail": info.get(
                    "thumbnail",
                    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                ),
            }
    except Exception as e:
        print(f"yt-dlp method failed: {e}")

    try:
        search = VideosSearch(f"site:youtube.com {video_id}", limit=20)
        results = search.result().get("result", [])

        for video in results:
            video_url = video.get("link", "")
            if video_id in video_url:
                duration = format_duration(video.get("duration"))
                published = format_publish_date(video.get("publishedTime"))

                view_count = video.get("viewCount", {})
                if isinstance(view_count, dict):
                    views = view_count.get("text", "Unknown Views")
                else:
                    views = format_view_count_full(view_count)

                channel = video.get("channel", {})
                if isinstance(channel, dict):
                    channel_name = channel.get("name", "Unknown Channel")
                else:
                    channel_name = str(channel) if channel else "Unknown Channel"

                return {
                    "title": video.get("title", f"Video {video_id}"),
                    "published": published,
                    "duration": duration,
                    "views": views,
                    "channel": channel_name,
                    "thumbnail": (
                        video.get("thumbnails", [{}])[-1].get(
                            "url",
                            f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                        )
                        if video.get("thumbnails")
                        else f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                    ),
                }
    except Exception as e:
        print(f"Search method failed: {e}")

    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        response = requests.get(oembed_url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return {
                "title": data.get("title", f"Video {video_id}"),
                "published": "Unknown Date",
                "duration": "Unknown Duration",
                "views": "Unknown Views",
                "channel": data.get("author_name", "Unknown Channel"),
                "thumbnail": data.get(
                    "thumbnail_url",
                    f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                ),
            }
    except Exception as e:
        print(f"oEmbed method failed: {e}")

    try:
        api_key = getattr(settings, "YOUTUBE_API_KEY", None)
        if api_key:
            api_url = f"https://www.googleapis.com/youtube/v3/videos"
            params = {
                "part": "snippet,statistics,contentDetails",
                "id": video_id,
                "key": api_key,
            }

            response = requests.get(api_url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data.get("items"):
                    item = data["items"][0]
                    snippet = item.get("snippet", {})
                    statistics = item.get("statistics", {})
                    content_details = item.get("contentDetails", {})

                    published_at = snippet.get("publishedAt")
                    published = (
                        format_publish_date(published_at)
                        if published_at
                        else "Unknown Date"
                    )

                    duration_iso = content_details.get("duration")
                    duration = (
                        parse_iso_duration(duration_iso)
                        if duration_iso
                        else "Unknown Duration"
                    )

                    view_count = statistics.get("viewCount")
                    views = (
                        format_view_count_full(view_count)
                        if view_count
                        else "Unknown Views"
                    )

                    return {
                        "title": snippet.get("title", f"Video {video_id}"),
                        "published": published,
                        "duration": duration,
                        "views": views,
                        "channel": snippet.get("channelTitle", "Unknown Channel"),
                        "thumbnail": snippet.get("thumbnails", {})
                        .get("maxresdefault", {})
                        .get(
                            "url",
                            f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                        ),
                    }
    except Exception as e:
        print(f"YouTube API method failed: {e}")

    return {
        "title": f"Video {video_id}",
        "published": "Unknown Date",
        "duration": "Unknown Duration",
        "views": "Unknown Views",
        "channel": "Unknown Channel",
        "thumbnail": f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
    }


def parse_iso_duration(duration_str):
    if not duration_str:
        return "Unknown Duration"

    try:
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str)
        if not match:
            return "Unknown Duration"

        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return "Unknown Duration"


def detect_platform(url):
    if "music.youtube.com" in url:
        return "youtube_music"
    elif "youtube.com/shorts" in url:
        return "youtube_shorts"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
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
        audio_url_pattern = r'http://127\.0\.0\.1:8000/audio/([a-zA-Z0-9_-]+)/?'
        audio_match = re.match(audio_url_pattern, query)
        
        if audio_match:
            video_id = audio_match.group(1)
            from django.shortcuts import redirect
            from django.urls import reverse
            return redirect(reverse('audio:video_detail', args=[video_id]))

        platform = detect_platform(query)
        video_id = extract_youtube_id(query)

        social_platforms = {
            "tiktok.com": "tiktok",
            "vm.tiktok.com": "tiktok",
            "t.tiktok.com": "tiktok",
            "twitter.com": "twitter",
            "x.com": "twitter",
            "t.co": "twitter",
            "instagram.com": "instagram",
            "instagr.am": "instagram",
            "facebook.com": "facebook",
            "fb.com": "facebook",
            "fb.watch": "facebook",
        }

        detected_social_platform = None
        for domain, platform_name in social_platforms.items():
            if domain in query.lower():
                detected_social_platform = platform_name
                break

        if detected_social_platform:
            from django.shortcuts import redirect
            from urllib.parse import urlencode

            params = {"url": query, "platform": detected_social_platform}
            return redirect(f"/media/?{urlencode(params)}")

        if platform == "unknown":
            return render(
                request,
                "search/search_results.html",
                {
                    "error": "Unsupported URL. Please provide a YouTube, YouTube Music, or localhost URL.",
                    "query": query,
                    "url_error": True,
                },
            )

        if not video_id:
            return render(
                request,
                "search/search_results.html",
                {
                    "error": "Invalid video URL. Could not extract video ID from the provided link.",
                    "query": query,
                    "url_error": True,
                },
            )

        context = {
            "raw_url": query,
            "platform": platform,
            "video_id": video_id,
            "is_supported_platform": platform
            in ["youtube", "youtube_music", "localhost"],
        }

        try:
            context["video_metadata"] = get_video_metadata_by_id(video_id)
        except Exception as e:
            print(f"Error getting video metadata: {e}")
            context["metadata_error"] = f"Could not fetch video metadata: {str(e)}"

        return render(request, "search/url_input.html", context)

    context = {"query": query}
    try:
        videos = VideosSearch(query, limit=20).result().get("result", [])
        processed = [process_video_data(v) for v in videos if v]
        context.update(
            {
                "type": "search",
                "results": processed,
                "results_count": len(processed),
                "platform": "youtube",
            }
        )
    except Exception as e:
        context["error"] = f"Search Failed"

    return render(request, "search/search_results.html", context)


def process_video_data_url(video):
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
            "duration": format_duration(video.get("duration", "Unknown Duration")),
            "views": (
                video.get("viewCount", {}).get("text", "Unknown Views")
                if isinstance(video.get("viewCount"), dict)
                else format_view_count_full(video.get("viewCount", "Unknown Views"))
            ),
            "published": format_publish_date(
                video.get("publishedTime", "Unknown Date")
            ),
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
    if request.method == "GET":
        query = request.GET.get("q", "").strip()
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 20))

        if not query:
            return JsonResponse({"error": "No query provided"}, status=400)

        try:
            videosSearch = VideosSearch(query, limit=limit)

            for _ in range(page - 1):
                try:
                    videosSearch.next()
                except Exception as e:
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
            processed_results = [
                process_video_data_url(video) for video in results if video
            ]

            has_more = len(results) >= limit

            return JsonResponse(
                {
                    "type": "search",
                    "results": processed_results,
                    "platform": "youtube",
                    "page": page,
                    "has_more": has_more,
                    "total_results": len(processed_results),
                }
            )

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Method not allowed"}, status=405)


def get_video_metadata(request):
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
        suggestions = []
        try:
            video_search = VideosSearch(query, limit=4)
            video_results = video_search.result()

            if video_results and "result" in video_results:
                for video in video_results["result"]:
                    thumbnail_url = ""
                    if video.get("thumbnails") and len(video["thumbnails"]) > 0:
                        thumbnails = video["thumbnails"]
                        if len(thumbnails) > 1:
                            thumbnail_url = thumbnails[1].get("url", "")
                        else:
                            thumbnail_url = thumbnails[0].get("url", "")

                    suggestions.append(
                        {
                            "type": "video",
                            "title": video.get("title", ""),
                            "channel": (
                                video.get("channel", {}).get("name", "")
                                if video.get("channel")
                                else ""
                            ),
                            "views": (
                                video.get("viewCount", {}).get("text", "")
                                if video.get("viewCount")
                                else ""
                            ),
                            "thumbnail": thumbnail_url,
                            "duration": video.get("duration", ""),
                            "url": video.get("link", ""),
                        }
                    )
        except Exception as video_error:
            print(f"Video search error: {video_error}")

        try:
            text_suggestions = Suggestions(language="en", region="US").get(query)

            if text_suggestions and "result" in text_suggestions:
                for suggestion in text_suggestions["result"][:4]:
                    suggestions.append({"type": "text", "text": suggestion})
        except Exception as text_error:
            print(f"Text suggestions error: {text_error}")

        if not suggestions:
            suggestions.append({"type": "text", "text": query})

        return JsonResponse(
            {"suggestions": suggestions, "query": query, "count": len(suggestions)}
        )

    except Exception as e:
        print(f"General error in suggest_videos: {str(e)}")
        return JsonResponse(
            {"error": str(e), "suggestions": [], "query": query}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def track_video_play(request):
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
