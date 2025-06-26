from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
import subprocess
import re
import json
from urllib.parse import urlparse
import logging

# Set up logging
logger = logging.getLogger(__name__)

def media_grabber(request):
    """
    Render the index page for the media grabber.
    """
    return render(request, "media_grabber/index.html")

@csrf_exempt
@require_http_methods(["POST"])
def extract_video(request):
    """
    Extract video information and get direct download URL from external platform using yt-dlp
    """
    print("=" * 50)
    print("EXTRACT_VIDEO FUNCTION CALLED")
    print("=" * 50)
    
    try:
        # Parse JSON request body
        try:
            data = json.loads(request.body)
            video_url = data.get('url', '').strip()
            print(f"📥 Received JSON data: {data}")
            print(f"🔗 Video URL from JSON: {video_url}")
        except json.JSONDecodeError:
            # Fallback to form data if JSON parsing fails
            video_url = request.POST.get('url', '').strip()
            print(f"📥 Received form data: {request.POST}")
            print(f"🔗 Video URL from form: {video_url}")
        
        if not video_url:
            print("❌ No video URL provided")
            return JsonResponse({
                "success": False, 
                "message": "Please provide a video URL"
            })

        print(f"🎯 Processing URL: {video_url}")

        # Basic URL validation
        try:
            parsed_url = urlparse(video_url)
            print(f"🔍 Parsed URL - Scheme: {parsed_url.scheme}, Netloc: {parsed_url.netloc}")
            if not parsed_url.scheme or not parsed_url.netloc:
                print("❌ Invalid URL format - missing scheme or netloc")
                return JsonResponse({
                    "success": False, 
                    "message": "Invalid URL format"
                })
        except Exception as e:
            print(f"❌ URL parsing error: {e}")
            return JsonResponse({
                "success": False, 
                "message": "Invalid URL format"
            })

        # Build yt-dlp command to get video info and direct download URL
        yt_dlp_command = [
            'yt-dlp',
            video_url,
            '--get-url',           # Get direct URL without downloading
            '--get-title',         # Get video title
            '--get-duration',      # Get video duration
            '--get-thumbnail',     # Get thumbnail URL
            '--format', 'best[ext=mp4]/best',  # Prefer mp4 format
            '--no-playlist',       # Don't download playlists
            '--no-warnings',       # Reduce noise in output
            '--print-json',        # Print JSON with all info
        ]

        # Add platform-specific options
        if 'tiktok.com' in video_url.lower():
            yt_dlp_command.extend(['--extractor-args', 'tiktok:watermark=none'])
            print("🎵 TikTok URL detected - added watermark removal")

        print(f"🚀 Running command: {' '.join(yt_dlp_command)}")

        # Execute yt-dlp to get video information
        try:
            result = subprocess.run(
                yt_dlp_command, 
                capture_output=True, 
                text=True, 
                check=True, 
                timeout=45  # 45 second timeout
            )
            
            print(f"✅ yt-dlp completed successfully")
            print(f"📤 yt-dlp stdout: {result.stdout}")
            print(f"📤 yt-dlp stderr: {result.stderr}")
            
            output_lines = result.stdout.strip().split('\n')
            print(f"📋 Output lines ({len(output_lines)}): {output_lines}")
            
            if len(output_lines) < 1:
                print("❌ No output from yt-dlp")
                return JsonResponse({
                    "success": False,
                    "message": "Could not extract video information"
                })

            # Try to parse JSON output first (if --print-json worked)
            video_info = None
            try:
                # Look for JSON line in output
                for line in output_lines:
                    if line.strip().startswith('{'):
                        video_info = json.loads(line)
                        print(f"📊 Parsed JSON info: {video_info}")
                        break
            except:
                print("⚠️ Could not parse JSON output, using line-by-line parsing")

            if video_info:
                # Extract from JSON
                direct_url = video_info.get('url', '')
                video_title = video_info.get('title', 'Unknown Video')
                duration = str(video_info.get('duration', ''))
                thumbnail = video_info.get('thumbnail', '')
            else:
                # Parse output lines manually
                direct_url = output_lines[0] if len(output_lines) > 0 else ""
                video_title = output_lines[1] if len(output_lines) > 1 else "Unknown Video"
                duration = output_lines[2] if len(output_lines) > 2 else ""
                thumbnail = output_lines[3] if len(output_lines) > 3 else ""
            
            print(f"🎬 Extracted data:")
            print(f"  📹 Direct URL: {direct_url}")
            print(f"  📝 Title: {video_title}")
            print(f"  ⏱️ Duration: {duration}")
            print(f"  🖼️ Thumbnail: {thumbnail}")
            
            if not direct_url:
                print("❌ No direct URL extracted")
                return JsonResponse({
                    "success": False,
                    "message": "Could not extract download URL from this video"
                })

            # Validate that the direct URL is accessible
            print(f"🔍 Direct download URL: {direct_url}")

        except subprocess.TimeoutExpired:
            print("⏰ yt-dlp timed out")
            return JsonResponse({
                "success": False,
                "message": "Request timed out. The video might be too long or the platform is slow to respond."
            })
        except subprocess.CalledProcessError as e:
            error_output = e.stderr if e.stderr else str(e)
            print(f"❌ yt-dlp error: {error_output}")
            print(f"❌ yt-dlp stdout: {e.stdout if hasattr(e, 'stdout') else 'No stdout'}")
            
            # Handle common errors
            if "Unsupported URL" in error_output or "No video formats found" in error_output:
                return JsonResponse({
                    "success": False,
                    "message": "This video URL is not supported or the video is private/deleted"
                })
            elif "Sign in to confirm your age" in error_output:
                return JsonResponse({
                    "success": False,
                    "message": "This video requires age verification and cannot be downloaded"
                })
            elif "Private video" in error_output:
                return JsonResponse({
                    "success": False,
                    "message": "This video is private and cannot be downloaded"
                })
            else:
                return JsonResponse({
                    "success": False,
                    "message": f"Failed to process video: {error_output}"
                })

        # Clean video title for safe filename
        clean_title = re.sub(r'[<>:"/\\|?*]', '', video_title)
        clean_title = clean_title[:50] if clean_title else "video"

        # Detect platform
        platform = "Unknown"
        if 'tiktok.com' in video_url.lower():
            platform = "TikTok"
        elif 'instagram.com' in video_url.lower():
            platform = "Instagram"
        elif 'twitter.com' in video_url.lower() or 'x.com' in video_url.lower():
            platform = "Twitter/X"
        elif 'facebook.com' in video_url.lower():
            platform = "Facebook"
        elif 'youtube.com' in video_url.lower() or 'youtu.be' in video_url.lower():
            platform = "YouTube"

        print(f"🏷️ Detected platform: {platform}")

        # Return success response with video information
        response_data = {
            "success": True,
            "download_url": direct_url,  # Direct URL from platform
            "title": video_title,
            "platform": platform,
            "duration": duration,
            "thumbnail": thumbnail,
            "filename": f"{clean_title}.mp4"
        }
        
        print(f"📤 Sending response: {json.dumps(response_data, indent=2)}")
        print("=" * 50)
        return JsonResponse(response_data)

    except Exception as e:
        print(f"💥 Unexpected error in extract_video: {str(e)}")
        import traceback
        print(f"📍 Traceback: {traceback.format_exc()}")
        return JsonResponse({
            "success": False,
            "message": f"An unexpected server error occurred: {str(e)}"
        })