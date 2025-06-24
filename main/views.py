import requests
from django.shortcuts import render
from django.http import JsonResponse
from django.conf import settings
from django.core.cache import cache
from share.models import CachedVideo
import logging
import random
from datetime import datetime, timedelta
import re
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


def homepage(request):
    categories = [
        {"id": "music", "title": "Music"},
        {"id": "gaming", "title": "Gaming"},
        {"id": "entertainment", "title": "Entertainment"},
        {"id": "news", "title": "News"},
        {"id": "education", "title": "Education"},
        {"id": "science", "title": "Science & Tech"},
        {"id": "sports", "title": "Sports"},
        {"id": "comedy", "title": "Comedy"},
        {"id": "film", "title": "Film & Animation"},
    ]
    return render(request, "main/homepage.html", {"categories": categories})


def format_time_ago(published_at):
    """Convert published_at to human readable format like '1 day ago'"""
    if not published_at or published_at == "Unknown":
        return "Unknown"

    try:
        if isinstance(published_at, datetime):
            pub_date = published_at
        else:
            if "T" in str(published_at):
                pub_date = datetime.fromisoformat(
                    str(published_at).replace("Z", "+00:00")
                )
            else:
                pub_date = datetime.strptime(
                    str(published_at)[:19], "%Y-%m-%d %H:%M:%S"
                )

        now = datetime.now()
        if pub_date.tzinfo is not None:
            from django.utils import timezone

            now = timezone.now()

        diff = now - pub_date

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
    except Exception as e:
        logger.warning(f"Error formatting time: {e}")
        return "Unknown"


def parse_duration(duration):
    """Convert YouTube API duration format (PT4M13S) to readable format (4:13)"""
    if not duration:
        return "0:00"
    
    try:
        # Remove PT prefix
        duration = duration[2:]
        
        # Extract hours, minutes, seconds
        hours = 0
        minutes = 0
        seconds = 0
        
        if 'H' in duration:
            hours = int(duration.split('H')[0])
            duration = duration.split('H')[1]
        
        if 'M' in duration:
            minutes = int(duration.split('M')[0])
            duration = duration.split('M')[1]
        
        if 'S' in duration:
            seconds = int(duration.split('S')[0])
        
        # Format as H:MM:SS or M:SS
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return "0:00"


def get_youtube_service():
    """Get YouTube API service using available API keys"""
    api_keys = [
        getattr(settings, 'YOUTUBE_API_KEY_1', None),
        getattr(settings, 'YOUTUBE_API_KEY_2', None),
    ]
    
    for api_key in api_keys:
        if api_key:
            try:
                youtube = build('youtube', 'v3', developerKey=api_key)
                # Test the API key with a simple request
                youtube.videos().list(part='id', id='dQw4w9WgXcQ').execute()
                return youtube
            except HttpError as e:
                if e.resp.status == 403:  # Quota exceeded
                    logger.warning(f"API key quota exceeded, trying next key")
                    continue
                else:
                    logger.error(f"YouTube API error: {e}")
                    continue
            except Exception as e:
                logger.error(f"Error with YouTube API key: {e}")
                continue
    
    logger.error("All YouTube API keys failed or unavailable")
    return None


def fetch_videos_from_youtube_api(category_id, max_results=50):
    """Fetch videos from YouTube API for a specific category"""
    youtube = get_youtube_service()
    if not youtube:
        return []

    try:
        # First, try to get most popular videos by category
        try:
            videos_response = youtube.videos().list(
                part='snippet,contentDetails,statistics',
                chart='mostPopular',
                videoCategoryId=category_id,
                regionCode='US',
                maxResults=min(max_results, 50)
            ).execute()
            
            processed_videos = []
            for item in videos_response['items']:
                try:
                    video_data = {
                        'video_id': item['id'],
                        'title': item['snippet']['title'],
                        'category': category_id,
                        'duration': parse_duration(item['contentDetails']['duration']),
                        'channel_name': item['snippet']['channelTitle'],
                        'published_at': item['snippet']['publishedAt'],
                    }
                    processed_videos.append(video_data)
                except Exception as e:
                    logger.warning(f"Error processing video {item.get('id', 'unknown')}: {e}")
                    continue
            
            if processed_videos:
                return processed_videos
                
        except Exception as e:
            logger.warning(f"Chart method failed, trying search: {e}")

        # Fallback: Search for videos with category-specific keywords
        search_queries = get_category_search_terms(category_id)
        all_videos = []
        
        for query in search_queries:
            try:
                search_response = youtube.search().list(
                    part='id,snippet',
                    type='video',
                    q=query,
                    regionCode='US',
                    maxResults=min(20, max_results // len(search_queries) + 5),
                    order='relevance',
                    publishedAfter=(datetime.now() - timedelta(days=90)).isoformat() + 'Z'
                ).execute()

                video_ids = [item['id']['videoId'] for item in search_response['items']]
                
                if video_ids:
                    videos_response = youtube.videos().list(
                        part='snippet,contentDetails,statistics',
                        id=','.join(video_ids)
                    ).execute()

                    for item in videos_response['items']:
                        try:
                            video_data = {
                                'video_id': item['id'],
                                'title': item['snippet']['title'],
                                'category': category_id,
                                'duration': parse_duration(item['contentDetails']['duration']),
                                'channel_name': item['snippet']['channelTitle'],
                                'published_at': item['snippet']['publishedAt'],
                            }
                            all_videos.append(video_data)
                        except Exception as e:
                            logger.warning(f"Error processing video {item.get('id', 'unknown')}: {e}")
                            continue
                            
                if len(all_videos) >= max_results:
                    break
                    
            except Exception as e:
                logger.warning(f"Search query '{query}' failed: {e}")
                continue

        return all_videos[:max_results]

    except HttpError as e:
        logger.error(f"YouTube API HTTP error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching videos from YouTube API: {e}")
        return []


def get_category_search_terms(category_id):
    """Get search terms for different categories"""
    category_searches = {
        "10": ["music", "song", "artist", "album", "concert"],  # Music
        "20": ["gaming", "gameplay", "game review", "esports", "gaming news"],  # Gaming
        "24": ["entertainment", "celebrity", "talk show", "comedy show"],  # Entertainment
        "25": ["news", "breaking news", "current events", "politics"],  # News
        "27": ["education", "tutorial", "learning", "how to", "educational"],  # Education
        "28": ["science", "technology", "tech review", "innovation", "research"],  # Science & Tech
        "17": ["sports", "football", "basketball", "soccer", "athletics"],  # Sports
        "23": ["comedy", "funny", "humor", "stand up", "comedy sketch"],  # Comedy
        "1": ["film", "movie", "cinema", "trailer", "animation"],  # Film & Animation
    }
    
    return category_searches.get(category_id, ["popular", "trending", "viral"])


def save_videos_to_cache(videos_data):
    """Save fetched videos to database cache"""
    saved_count = 0
    
    for video_data in videos_data:
        try:
            cached_video, created = CachedVideo.objects.get_or_create(
                video_id=video_data['video_id'],
                defaults={
                    'title': video_data['title'],
                    'category': video_data['category'],
                    'duration': video_data['duration'],
                    'channel_name': video_data['channel_name'],
                    'published_at': video_data['published_at'],
                }
            )
            
            if created:
                saved_count += 1
                logger.info(f"Cached new video: {video_data['title']}")
            else:
                # Update existing video data
                cached_video.title = video_data['title']
                cached_video.category = video_data['category']
                cached_video.duration = video_data['duration']
                cached_video.channel_name = video_data['channel_name']
                cached_video.published_at = video_data['published_at']
                cached_video.save()
                
        except Exception as e:
            logger.error(f"Error saving video {video_data['video_id']}: {e}")
            continue
    
    logger.info(f"Saved {saved_count} new videos to cache")
    return saved_count


def ensure_category_has_videos(category_id, min_videos=20):
    """Ensure a category has minimum number of videos, fetch if needed"""
    if not category_id:
        return
    
    # Check current count
    current_count = CachedVideo.objects.filter(category=category_id).count()
    
    if current_count < min_videos:
        logger.info(f"Category {category_id} has only {current_count} videos, fetching more...")
        
        # Fetch videos from YouTube API
        new_videos = fetch_videos_from_youtube_api(category_id, max_results=50)
        
        if new_videos:
            saved_count = save_videos_to_cache(new_videos)
            logger.info(f"Fetched and saved {saved_count} new videos for category {category_id}")
        else:
            logger.warning(f"No new videos fetched for category {category_id}")


def load_videos(request):
    category = request.GET.get("category", "all")
    max_results = int(request.GET.get("max_results", 24))
    page = int(request.GET.get("page", 1))

    if page > 5:
        return JsonResponse({"success": True, "videos": [], "has_more": False})

    cache_key = f"shown_videos_{category}"
    shown_video_ids = (
        cache.get(cache_key, set()) if page == 1 else cache.get(cache_key, set())
    )

    CATEGORY_MAP = {
        "music": "10",
        "gaming": "20",
        "entertainment": "24",
        "news": "25",
        "education": "27",
        "science": "28",
        "sports": "17",
        "comedy": "23",
        "film": "1",
        "all": None,
    }

    try:
        category_id = CATEGORY_MAP.get(category)
        
        # Ensure category has enough videos before fetching
        if category_id:
            ensure_category_has_videos(category_id, min_videos=20)
        
        if category == "all":
            videos = fetch_all_videos_from_db(max_results, shown_video_ids, page)
        else:
            videos = fetch_category_videos_from_db(
                category_id, max_results, shown_video_ids, page
            )

        # If still not enough videos after fetching, try to get more
        if len(videos) < max_results // 2 and category_id:
            logger.info(f"Still insufficient videos for {category}, fetching more...")
            new_videos = fetch_videos_from_youtube_api(category_id, max_results=50)
            if new_videos:
                save_videos_to_cache(new_videos)
                # Re-fetch from database
                videos = fetch_category_videos_from_db(
                    category_id, max_results, shown_video_ids, page
                )

        new_video_ids = {video["id"] for video in videos}
        shown_video_ids.update(new_video_ids)
        cache.set(cache_key, shown_video_ids, 3600)

        has_more = len(videos) == max_results and page < 4

        return JsonResponse(
            {"success": True, "videos": videos, "has_more": has_more, "page": page}
        )

    except Exception as e:
        logger.error(f"Error loading videos: {e}")
        return get_fallback_response()


def fetch_all_videos_from_db(max_results, shown_videos, page):
    """Fetch videos from all categories mixed together"""
    try:
        offset = (page - 1) * max_results

        cached_videos = CachedVideo.objects.exclude(video_id__in=shown_videos).order_by(
            "?"
        )[offset : offset + max_results * 2]

        processed_videos = []
        for video in cached_videos:
            processed_video = process_cached_video(video)
            if processed_video and is_video_valid(processed_video):
                processed_videos.append(processed_video)
                if len(processed_videos) >= max_results:
                    break

        if len(processed_videos) < max_results // 2:
            additional_videos = CachedVideo.objects.order_by("?")[
                offset : offset + max_results * 2
            ]
            for video in additional_videos:
                if len(processed_videos) >= max_results:
                    break
                processed_video = process_cached_video(video)
                if (
                    processed_video
                    and is_video_valid(processed_video)
                    and processed_video["id"] not in [v["id"] for v in processed_videos]
                ):
                    processed_videos.append(processed_video)

        return processed_videos

    except Exception as e:
        logger.error(f"Error fetching all videos from DB: {e}")
        return []


def fetch_category_videos_from_db(category_id, max_results, shown_videos, page):
    try:
        offset = (page - 1) * max_results

        if category_id:
            cached_videos = (
                CachedVideo.objects.filter(category=category_id)
                .exclude(video_id__in=shown_videos)
                .order_by("?")[offset : offset + max_results * 2]
            )

            if cached_videos.count() < max_results // 2:
                cached_videos = CachedVideo.objects.filter(
                    category=category_id
                ).order_by("?")[offset : offset + max_results * 2]
        else:
            cached_videos = CachedVideo.objects.exclude(
                video_id__in=shown_videos
            ).order_by("?")[offset : offset + max_results * 2]

        processed_videos = []
        for video in cached_videos:
            processed_video = process_cached_video(video)
            if processed_video and is_video_valid(processed_video):
                processed_videos.append(processed_video)
                if len(processed_videos) >= max_results:
                    break

        return processed_videos

    except Exception as e:
        logger.error(f"Error fetching category videos from DB: {e}")
        return []


def process_cached_video(video):
    try:
        thumbnail_url = f"https://img.youtube.com/vi/{video.video_id}/maxresdefault.jpg"

        return {
            "id": video.video_id,
            "title": video.title,
            "thumbnail": thumbnail_url,
            "channel_title": video.channel_name or "Unknown Channel",
            "duration": video.duration or "0:00",
            "published_at": format_time_ago(video.published_at),
        }
    except Exception as e:
        logger.error(f"Error processing cached video {video.video_id}: {e}")
        return None


def is_video_valid(video_data):
    if not video_data or not video_data.get("id"):
        return False

    title = video_data.get("title", "").lower()
    skip_indicators = [
        "private video",
        "deleted video",
        "unavailable",
        "[deleted]",
        "[private]",
    ]

    for indicator in skip_indicators:
        if indicator in title:
            return False

    return True


def get_fallback_response():
    fallback_videos = [
        {
            "id": "9bZkp7q19f0",
            "title": "Gangnam Style - PSY",
            "thumbnail": "https://img.youtube.com/vi/9bZkp7q19f0/maxresdefault.jpg",
            "channel_title": "officialpsy",
            "duration": "4:12",
            "published_at": "12 years ago",
        },
        {
            "id": "kJQP7kiw5Fk",
            "title": "Despacito - Luis Fonsi ft. Daddy Yankee",
            "thumbnail": "https://img.youtube.com/vi/kJQP7kiw5Fk/maxresdefault.jpg",
            "channel_title": "LuisFonsiVEVO",
            "duration": "4:41",
            "published_at": "7 years ago",
        },
    ]

    return JsonResponse(
        {
            "success": True,
            "videos": fallback_videos[:12],
            "fallback": True,
            "has_more": False,
        }
    )


# Management command or utility function to populate all categories
def populate_all_categories():
    """Utility function to populate all categories with videos"""
    CATEGORY_MAP = {
        "music": "10",
        "gaming": "20",
        "entertainment": "24",
        "news": "25",
        "education": "27",
        "science": "28",
        "sports": "17",
        "comedy": "23",
        "film": "1",
    }
    
    for category_name, category_id in CATEGORY_MAP.items():
        logger.info(f"Populating category: {category_name}")
        ensure_category_has_videos(category_id, min_videos=50)
        
    logger.info("Finished populating all categories")