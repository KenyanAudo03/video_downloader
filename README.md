# Universal Video Downloader - Django Setup Guide

This is a complete Django-based video downloader that supports YouTube, Instagram, TikTok, Twitter, Facebook, and Vimeo with user session tracking and download history.

## Features

- ✅ **Multi-platform support**: YouTube, Instagram, TikTok, Twitter, Facebook, Vimeo
- ✅ **User session tracking**: Tracks downloads per user session
- ✅ **Download history**: Users can re-download previous videos
- ✅ **Multiple quality options**: Best, 1080p, 720p, 480p, Audio-only
- ✅ **Real-time status updates**: Shows processing status
- ✅ **Responsive design**: Works on desktop and mobile
- ✅ **No brand logos**: Clean, unbranded interface

## Prerequisites

- Python 3.8 or higher
- Redis server (for background tasks)
- FFmpeg (for audio conversion)

## Installation Steps

### 1. Clone/Create Project Structure

```bash
mkdir video_downloader
cd video_downloader

# Create the following structure:
video_downloader/
├── manage.py
├── requirements.txt
├── video_downloader/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── downloader/
    ├── __init__.py
    ├── models.py
    ├── views.py
    ├── urls.py
    └── templates/
        └── downloader/
            └── index.html
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

**requirements.txt content:**
```
Django==4.2.7
yt-dlp==2023.10.13
requests==2.31.0
celery==5.3.4
redis==5.0.1
pillow==10.1.0
```

### 3. Install System Dependencies

**On Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server ffmpeg
sudo systemctl start redis
sudo systemctl enable redis
```

**On macOS:**
```bash
brew install redis ffmpeg
brew services start redis
```

**On Windows:**
- Download and install Redis from: https://redis.io/download
- Download FFmpeg from: https://ffmpeg.org/download.html
- Add FFmpeg to your PATH

### 4. Django Setup

Copy all the Django code from the artifacts into your project files, then run:

```bash
# Create and run migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser

# Collect static files (for production)
python manage.py collectstatic --noinput
```

### 5. Create Required Directories

```bash
mkdir -p media/downloads
chmod 755 media/downloads
```

### 6. Start the Application

**Development Mode:**
```bash
python manage.py runserver 0.0.0.0:8000
```

**Production Mode (with Gunicorn):**
```bash
pip install gunicorn
gunicorn video_downloader.wsgi:application --bind 0.0.0.0:8000
```

### 7. Access the Application

Open your browser and navigate to:
- Local: `http://localhost:8000`
- Network: `http://your-server-ip:8000`

## Configuration

### Environment Variables (Recommended for Production)

Create a `.env` file:
```bash
SECRET_KEY=your-super-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,your-server-ip
REDIS_URL=redis://localhost:6379/0
```

Update `settings.py` to use environment variables:
```python
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY', 'your-default-key')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost').split(',')

# Add this for environment-based settings
```

### Database Configuration (PostgreSQL for Production)

For production, consider using PostgreSQL:

```bash
pip install psycopg2-binary
```

Update `settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'video_downloader',
        'USER': 'your_db_user',
        'PASSWORD': 'your_db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## Usage

### How to Use the Application

1. **Select Platform**: Choose from YouTube, Instagram, TikTok, etc.
2. **Enter URL**: Paste the video URL in the input field
3. **Choose Quality**: Select desired video quality or audio-only
4. **Download**: Click "Get Video Info" to process the video
5. **Download File**: Once processed, click "Download Now"

### API Endpoints

The application provides these API endpoints:

- `POST /api/get-video-info/` - Get video information
- `GET /api/check-status/<download_id>/` - Check download status
- `POST /api/download/<download_id>/` - Start video download
- `GET /api/history/` - Get user's download history
- `GET /download/<download_id>/` - Serve download file

## Troubleshooting

### Common Issues

**1. "yt-dlp not found" error:**
```bash
pip install --upgrade yt-dlp
```

**2. FFmpeg not found:**
```bash
# Check if FFmpeg is installed and in PATH
ffmpeg -version
```

**3. Redis connection error:**
```bash
# Check if Redis is running
redis-cli ping
# Should return "PONG"
```

**4. Permission denied for downloads:**
```bash
chmod -R 755 media/downloads
```

**5. Video extraction fails:**
- Some platforms frequently update their protection mechanisms
- Update yt-dlp regularly: `pip install --upgrade yt-dlp`
- Check if the URL is valid and accessible

### Performance Optimization

**1. Enable Caching:**
```python
# Add to settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
```

**2. Use Celery for Background Tasks:**
```bash
pip install celery
celery -A video_downloader worker --loglevel=info
```

**3. Add Rate Limiting:**
```python
# Install django-ratelimit
pip install django-ratelimit

# Add to views.py
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='10/m', method='POST')
def get_video_info(request):
    # Your existing code
```

## Security Considerations

### Important Security Notes

1. **CSRF Protection**: Already implemented
2. **Input Validation**: URLs are validated
3. **File Permissions**: Set proper permissions on download directory
4. **Rate Limiting**: Implement rate limiting to prevent abuse
5. **Content Filtering**: Consider implementing content filtering

### Production Deployment

For production deployment:

1. **Use HTTPS**: Always use SSL certificates
2. **Environment Variables**: Store secrets in environment variables
3. **Database**: Use PostgreSQL instead of SQLite
4. **Static Files**: Use a CDN for static files
5. **Monitoring**: Implement logging and monitoring
6. **Backups**: Regular database backups

### Legal Compliance

⚠️ **Important Legal Notes:**

- Always respect platform Terms of Service
- Consider copyright implications
- Some platforms explicitly prohibit downloading
- Use responsibly and ensure compliance with local laws
- Consider implementing user agreements

### Example Deployment Script

```bash
#!/bin/bash
# deploy.sh

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3-pip nginx redis-server ffmpeg -y

# Clone your project
git clone your-repo-url
cd video_downloader

# Install Python dependencies
pip3 install -r requirements.txt

# Setup Django
python3 manage.py migrate
python3 manage.py collectstatic --noinput

# Setup systemd service
sudo cp deploy/video_downloader.service /etc/systemd/system/
sudo systemctl enable video_downloader
sudo systemctl start video_downloader

# Setup Nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/video_downloader
sudo ln -s /etc/nginx/sites-available/video_downloader /etc/nginx/sites-enabled/
sudo systemctl restart nginx

echo "Deployment complete! Visit http://your-server-ip"
```

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Ensure all dependencies are installed correctly
3. Check Django and yt-dlp documentation
4. Consider platform-specific limitations

## License

This project is for educational purposes. Ensure you comply with all relevant terms of service and copyright laws.