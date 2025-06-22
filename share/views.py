from django.shortcuts import render
from django.http import Http404
from django.conf import settings
import requests
import logging
import re
import json
from urllib.parse import urlparse
from datetime import datetime, timezone
from .models import CachedVideo

logger = logging.getLogger(__name__)

# Format duration before save
def format_duration(duration_str):
    if not duration_str or duration_str == "N/A":
        return "N/A"
    try:
        duration = duration_str.replace("PT", "")
        hours = 0
        minutes = 0
        seconds = 0
        if "H" in duration:
            hours = int(duration.split("H")[0])
            duration = duration.split("H")[1]
        if "M" in duration:
            minutes = int(duration.split("M")[0])
            duration = duration.split("M")[1]
        if "S" in duration:
            seconds = int(duration.replace("S", ""))
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return "N/A"


def format_published_date(date_str):
    if not date_str or date_str == "N/A":
        return "N/A"
    try:
        if date_str.endswith("Z"):
            published_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            published_date = datetime.fromisoformat(date_str)
        if published_date.tzinfo is None:
            published_date = published_date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - published_date
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    except:
        return date_str


def save_video_to_cache(video_info, duration=None, channel_name=None):
    try:
        video_id = video_info["id"]
        title = video_info["snippet"]["title"]
        category_id = video_info["snippet"].get("categoryId", "Unknown")
        published_at = video_info["snippet"].get("publishedAt", "")
        if CachedVideo.objects.filter(video_id=video_id).exists():
            logger.debug(f"Video {video_id} already in cache, skipping save")
            return CachedVideo.objects.get(video_id=video_id)
        cached_video = CachedVideo.objects.create(
            video_id=video_id,
            title=title,
            category=category_id,
            duration=duration or "N/A",
            channel_name=channel_name or "Unknown Channel",
            published_at=published_at,
        )
        logger.info(f"Created new cached video: {video_id}")
        return cached_video
    except Exception as e:
        logger.error(f"Error saving video to cache: {e}")
        return None


def get_cached_related_videos(category, exclude_video_id=None):
    try:
        query = CachedVideo.objects.filter(category=category)
        if exclude_video_id:
            query = query.exclude(video_id=exclude_video_id)
        cached_videos = query.order_by("?")[:15]
        related_videos = []
        for cached_video in cached_videos:
            related_videos.append(
                {
                    "id": cached_video.video_id,
                    "title": cached_video.title,
                    "description": f"Video from {cached_video.category} category",
                    "thumbnail": f"https://img.youtube.com/vi/{cached_video.video_id}/mqdefault.jpg",
                    "channel_title": cached_video.channel_name or "Unknown Channel",
                    "channel_name": cached_video.channel_name or "Unknown Channel",
                    "published_at": cached_video.published_at,
                    "published_time": format_published_date(cached_video.published_at),
                    "duration": cached_video.duration or "N/A",
                }
            )
        return related_videos
    except Exception as e:
        logger.error(f"Error getting cached related videos: {e}")
        return []


def get_video_details_and_related(video_id, api_key):
    try:
        video_url = f"https://www.googleapis.com/youtube/v3/videos"
        video_params = {
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
            "key": api_key,
        }
        video_response = requests.get(video_url, params=video_params, timeout=10)
        video_data = video_response.json()
        if "error" in video_data:
            error = video_data["error"]
            if error.get("code") == 403 and "quota" in error.get("message", "").lower():
                logger.warning("YouTube API quota exceeded, falling back to cache")
                return get_fallback_data(video_id)
        if not video_data.get("items"):
            return get_fallback_data(video_id)
        video_info = video_data["items"][0]
        category_id = video_info["snippet"].get("categoryId")
        duration = video_info.get("contentDetails", {}).get("duration", "N/A")
        channel_name = video_info["snippet"].get("channelTitle", "Unknown Channel")
        save_video_to_cache(video_info, format_duration(duration), channel_name)
        search_url = f"https://www.googleapis.com/youtube/v3/search"
        search_params = {
            "part": "snippet",
            "type": "video",
            "videoCategoryId": category_id,
            "maxResults": 20,
            "key": api_key,
            "order": "relevance",
        }
        if "tags" in video_info["snippet"]:
            tags = video_info["snippet"]["tags"][:3]
            search_params["q"] = " ".join(tags)
        search_response = requests.get(search_url, params=search_params, timeout=10)
        search_data = search_response.json()
        if "error" in search_data:
            error = search_data["error"]
            if error.get("code") == 403 and "quota" in error.get("message", "").lower():
                logger.warning(
                    "YouTube API quota exceeded during search, using cached related videos"
                )
                related_videos = get_cached_related_videos(category_id, video_id)
                return video_info, related_videos
        video_ids = []
        search_items = {}
        for item in search_data.get("items", []):
            if item["id"]["videoId"] != video_id:
                video_ids.append(item["id"]["videoId"])
                search_items[item["id"]["videoId"]] = item
        if video_ids:
            details_url = f"https://www.googleapis.com/youtube/v3/videos"
            details_params = {
                "part": "contentDetails,snippet",
                "id": ",".join(video_ids[:15]),
                "key": api_key,
            }
            details_response = requests.get(
                details_url, params=details_params, timeout=10
            )
            details_data = details_response.json()
            related_videos = []
            for detail_item in details_data.get("items", []):
                vid_id = detail_item["id"]
                search_item = search_items.get(vid_id)
                if search_item:
                    duration_raw = detail_item.get("contentDetails", {}).get(
                        "duration", "N/A"
                    )
                    duration_formatted = format_duration(duration_raw)
                    channel_title = search_item["snippet"]["channelTitle"]
                    related_video_info = {
                        "id": vid_id,
                        "snippet": {
                            "title": search_item["snippet"]["title"],
                            "categoryId": category_id,
                            "channelTitle": channel_title,
                            "publishedAt": search_item["snippet"]["publishedAt"],
                        },
                    }
                    save_video_to_cache(
                        related_video_info, duration_formatted, channel_title
                    )
                    related_videos.append(
                        {
                            "id": vid_id,
                            "title": search_item["snippet"]["title"],
                            "description": (
                                search_item["snippet"]["description"][:150] + "..."
                                if len(search_item["snippet"]["description"]) > 150
                                else search_item["snippet"]["description"]
                            ),
                            "thumbnail": search_item["snippet"]["thumbnails"]["medium"][
                                "url"
                            ],
                            "channel_title": channel_title,
                            "channel_name": channel_title,
                            "published_at": search_item["snippet"]["publishedAt"],
                            "published_time": format_published_date(
                                search_item["snippet"]["publishedAt"]
                            ),
                            "duration": duration_formatted,
                        }
                    )
            return video_info, related_videos[:15]
        else:
            related_videos = get_cached_related_videos(category_id, video_id)
            return video_info, related_videos
    except requests.RequestException as e:
        logger.error(f"Error fetching YouTube data: {e}")
        return get_fallback_data(video_id)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return get_fallback_data(video_id)


def get_fallback_data(video_id):
    try:
        cached_video = CachedVideo.objects.filter(video_id=video_id).first()
        if cached_video:
            video_info = {
                "id": cached_video.video_id,
                "snippet": {
                    "title": cached_video.title,
                    "categoryId": cached_video.category,
                    "description": f"Video from {cached_video.category} category",
                    "channelTitle": cached_video.channel_name or "Unknown Channel",
                    "publishedAt": cached_video.published_at or None,
                    "thumbnails": {
                        "medium": {
                            "url": f"https://img.youtube.com/vi/{cached_video.video_id}/mqdefault.jpg"
                        }
                    },
                },
                "statistics": {"viewCount": "N/A", "likeCount": "N/A"},
                "contentDetails": {"duration": cached_video.duration or "N/A"},
            }
            related_videos = get_cached_related_videos(cached_video.category, video_id)
            return video_info, related_videos
        else:
            category = get_youtube_category_from_video_id(video_id)
            if category:
                video_info = {
                    "id": video_id,
                    "snippet": {
                        "title": f"Video {video_id}",
                        "categoryId": category,
                        "description": "Video information unavailable",
                        "channelTitle": "Unknown Channel",
                        "publishedAt": "",
                        "thumbnails": {
                            "medium": {
                                "url": f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
                            }
                        },
                    },
                    "statistics": {"viewCount": "N/A", "likeCount": "N/A"},
                    "contentDetails": {"duration": "N/A"},
                }
                cache_video_info = {
                    "id": video_id,
                    "snippet": {
                        "title": f"Video {video_id}",
                        "categoryId": category,
                        "channelTitle": "Unknown Channel",
                        "publishedAt": "",
                    },
                }
                save_video_to_cache(cache_video_info, "N/A", "Unknown Channel")
                related_videos = get_cached_related_videos(category, video_id)
                return video_info, related_videos
    except Exception as e:
        logger.error(f"Error getting fallback data: {e}")
    return None, []


def parse_iso_date(iso_string):
    if not iso_string:
        return None
    try:
        if iso_string.endswith("Z"):
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(iso_string)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        logger.error(f"Error parsing date {iso_string}: {e}")
        return None


def shared_link(request, video_id):
    if len(video_id) != 11:
        raise Http404("Invalid video ID")
    allowed_chars = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
    )
    if not all(c in allowed_chars for c in video_id):
        raise Http404("Invalid video ID format")
    youtube_api_key = getattr(settings, "YOUTUBE_API_KEY", None)
    video_info = None
    related_videos = []
    api_used = False
    if youtube_api_key:
        video_info, related_videos = get_video_details_and_related(
            video_id, youtube_api_key
        )
        api_used = True
    else:
        video_info, related_videos = get_fallback_data(video_id)
    published_date = None
    published_time_ago = None
    if video_info and video_info.get("snippet", {}).get("publishedAt"):
        published_date = parse_iso_date(video_info["snippet"]["publishedAt"])
        published_time_ago = format_published_date(video_info["snippet"]["publishedAt"])
    context = {
        "video_id": video_id,
        "video_info": video_info,
        "related_videos": related_videos,
        "published_date": published_date,
        "published_time_ago": published_time_ago,
        "youtube_embed_url": f"https://www.youtube.com/embed/{video_id}",
        "youtube_watch_url": f"https://www.youtube.com/watch?v={video_id}",
        "has_api_key": bool(youtube_api_key),
        "api_used": api_used,
        "using_cache": not api_used or not video_info,
    }
    return render(request, "share/shared_link.html", context)


def extract_video_id(local_link):
    parsed_url = urlparse(local_link)
    path_parts = parsed_url.path.strip("/").split("/")
    if len(path_parts) == 2 and path_parts[0] == "share":
        return path_parts[1]
    return None


def get_youtube_category_from_video_id(video_id):
    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        match = re.search(r"ytInitialPlayerResponse\s*=\s*({.*?});", response.text)
        if not match:
            return None
        data = json.loads(match.group(1))
        try:
            return data["microformat"]["playerMicroformatRenderer"]["category"]
        except KeyError:
            return None
    except Exception as e:
        logger.error(f"Error scraping YouTube category: {e}")
        return None


def get_youtube_category_from_local_link(local_link):
    video_id = extract_video_id(local_link)
    if not video_id:
        return None
    return get_youtube_category_from_video_id(video_id)
