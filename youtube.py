"""
YouTube API service for fetching playlist data
Handles playlist parsing, video processing, and error handling
"""

import re
import asyncio
import logging
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse, parse_qs

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils import async_ttl_cache, RateLimiter
from config import CACHE_DURATION_SECONDS

logger = logging.getLogger(__name__)


class YouTubeService:
    """
    YouTube API service with caching, rate limiting, and robust error handling
    
    Features:
    - Automatic playlist ID extraction from various URL formats
    - Cached API responses to reduce quota usage
    - Rate limiting to prevent API abuse
    - Comprehensive error handling and logging
    - Video description parsing for combo notation and notes
    """
    
    def __init__(self, api_key: str):
        """
        Initialize YouTube service
        
        Args:
            api_key: YouTube Data API v3 key
        """
        self.api_key = api_key
        self._service = None
        
        # Rate limiter: 100 requests per 100 seconds (YouTube default quota)
        self.rate_limiter = RateLimiter(max_calls=90, time_window=100.0)
        
        logger.info("YouTube service initialized")
    
    @property
    def service(self):
        """Lazy load YouTube service to avoid unnecessary initialization"""
        if not self._service:
            try:
                self._service = build("youtube", "v3", developerKey=self.api_key)
                logger.info("YouTube API service connected")
            except Exception as e:
                logger.error(f"Failed to initialize YouTube service: {e}")
                raise
        return self._service
    
    @staticmethod
    def extract_playlist_id(url_or_id: str) -> Optional[str]:
        """
        Extract playlist ID from URL or validate existing ID
        
        Supports various YouTube URL formats:
        - https://www.youtube.com/playlist?list=PLxxxxxxx
        - https://youtube.com/playlist?list=PLxxxxxxx
        - https://m.youtube.com/playlist?list=PLxxxxxxx
        - PLxxxxxxx (direct ID)
        
        Args:
            url_or_id: YouTube playlist URL or ID
            
        Returns:
            Playlist ID if valid, None otherwise
        """
        if not url_or_id or not isinstance(url_or_id, str):
            return None
        
        url_or_id = url_or_id.strip()
        
        try:
            parsed = urlparse(url_or_id)
            
            # Check if it's a YouTube URL
            if parsed.hostname in ('www.youtube.com', 'youtube.com', 'm.youtube.com'):
                if parsed.path == '/playlist':
                    query_params = parse_qs(parsed.query)
                    playlist_ids = query_params.get('list', [])
                    if playlist_ids:
                        return playlist_ids[0]
                elif parsed.path.startswith('/watch') and 'list' in parsed.query:
                    # Handle watch URLs with playlist parameter
                    query_params = parse_qs(parsed.query)
                    playlist_ids = query_params.get('list', [])
                    if playlist_ids:
                        return playlist_ids[0]
            
            # Check if it's already a playlist ID
            # YouTube playlist IDs typically start with PL, UU, FL, OL, or RD
            # and are followed by 10+ characters
            if re.match(r"^(PL|UU|FL|OL|RD)?[a-zA-Z0-9_-]{10,}$", url_or_id):
                return url_or_id
            
        except Exception as e:
            logger.warning(f"Error parsing playlist URL/ID '{url_or_id}': {e}")
        
        return None
    
    @async_ttl_cache(CACHE_DURATION_SECONDS)
    async def fetch_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """
        Fetch playlist data with caching and error handling
        
        Args:
            playlist_id: YouTube playlist ID
            
        Returns:
            Dictionary containing playlist note and processed videos
            
        Raises:
            ValueError: For various error conditions with descriptive messages
        """
        if not playlist_id:
            raise ValueError("Playlist ID cannot be empty")
        
        # Check rate limiting
        if not self.rate_limiter.can_proceed():
            wait_time = self.rate_limiter.time_until_next_call()
            logger.warning(f"Rate limited, waiting {wait_time:.1f} seconds")
            await asyncio.sleep(wait_time)
        
        try:
            logger.info(f"Fetching playlist: {playlist_id}")
            
            # Get playlist metadata
            playlist_response = await asyncio.to_thread(
                self.service.playlists().list(
                    part="snippet,status",
                    id=playlist_id
                ).execute
            )
            
            if not playlist_response.get("items"):
                raise ValueError(f"Playlist '{playlist_id}' not found or is private")
            
            playlist_item = playlist_response["items"][0]
            
            # Check if playlist is accessible
            status = playlist_item.get("status", {})
            if status.get("privacyStatus") == "private":
                raise ValueError(f"Playlist '{playlist_id}' is private")
            
            # Extract playlist information
            snippet = playlist_item["snippet"]
            playlist_title = snippet.get("title", "Unknown Playlist")
            playlist_description = snippet.get("description", "")
            
            # Parse note from description
            note = self._extract_playlist_note(playlist_description)
            
            logger.info(f"Found playlist: '{playlist_title}' with {snippet.get('itemCount', 0)} items")
            
            # Fetch playlist videos
            videos = await self._fetch_playlist_videos(playlist_id)
            
            logger.info(f"Successfully fetched {len(videos)} videos from playlist")
            
            return {
                "title": playlist_title,
                "note": note,
                "videos": videos
            }
            
        except HttpError as e:
            error_msg = self._handle_http_error(e, playlist_id)
            logger.error(f"YouTube API error: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Unexpected error fetching playlist {playlist_id}: {e}")
            raise ValueError(f"Failed to fetch playlist: {str(e)}")
    
    async def _fetch_playlist_videos(self, playlist_id: str, max_videos: int = 200) -> List[Dict[str, str]]:
        """
        Fetch all videos from a playlist with pagination
        
        Args:
            playlist_id: YouTube playlist ID
            max_videos: Maximum number of videos to fetch
            
        Returns:
            List of processed video dictionaries
        """
        videos = []
        page_token = None
        
        while len(videos) < max_videos:
            try:
                # Rate limiting check
                if not self.rate_limiter.can_proceed():
                    wait_time = self.rate_limiter.time_until_next_call()
                    await asyncio.sleep(wait_time)
                
                # Fetch playlist items
                items_response = await asyncio.to_thread(
                    self.service.playlistItems().list(
                        part="snippet,contentDetails",
                        playlistId=playlist_id,
                        maxResults=min(50, max_videos - len(videos)),
                        pageToken=page_token
                    ).execute
                )
                
                items = items_response.get("items", [])
                if not items:
                    break
                
                # Process videos
                for item in items:
                    try:
                        video_data = self._process_video_item(item)
                        if video_data:
                            videos.append(video_data)
                    except Exception as e:
                        logger.warning(f"Error processing video item: {e}")
                        continue
                
                # Check for next page
                page_token = items_response.get("nextPageToken")
                if not page_token:
                    break
                    
            except HttpError as e:
                logger.error(f"Error fetching playlist items: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error fetching playlist items: {e}")
                break
        
        return videos
    
    def _process_video_item(self, item: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Process a single video item from playlist
        
        Args:
            item: YouTube API playlist item
            
        Returns:
            Processed video data or None if invalid
        """
        try:
            snippet = item.get("snippet", {})
            content_details = item.get("contentDetails", {})
            
            # Get video ID
            video_id = snippet.get("resourceId", {}).get("videoId")
            if not video_id:
                return None
            
            # Skip deleted/private videos
            if snippet.get("title") == "Deleted video" or snippet.get("title") == "Private video":
                logger.debug(f"Skipping deleted/private video: {video_id}")
                return None
            
            # Extract video information
            title = snippet.get("title", "Untitled Video")
            description = snippet.get("description", "")
            
            # Parse description for combo data
            parsed_data = self._parse_video_description(description)
            
            return {
                "title": title,
                "notation": parsed_data["notation"],
                "notes": parsed_data["notes"],
                "link": f"https://youtu.be/{video_id}"
            }
            
        except Exception as e:
            logger.warning(f"Error processing video item: {e}")
            return None
    
    @staticmethod
    def _extract_playlist_note(description: str) -> str:
        """
        Extract note from playlist description
        
        Args:
            description: Playlist description
            
        Returns:
            Extracted note or default message
        """
        if not description:
            return "No overall notes provided."
        
        # Look for "Note:" pattern in description
        note_match = re.search(r"(?i)Note:\s*(.+)", description, re.MULTILINE)
        if note_match:
            note = note_match.group(1).strip()
            # Take only the first line of the note
            note = note.split('\n')[0].strip()
            if note:
                return note
        
        # Fallback: use first line of description if it's short enough
        first_line = description.split('\n')[0].strip()
        if first_line and len(first_line) <= 200:
            return first_line
        
        return "No overall notes provided."
    
    @staticmethod
    def _parse_video_description(description: str) -> Dict[str, str]:
        """
        Parse video description for combo notation and notes
        
        Args:
            description: Video description text
            
        Returns:
            Dictionary with 'notation' and 'notes' keys
        """
        notation = "Unknown Notation"
        notes = "No Notes Provided"
        
        if not description:
            return {"notation": notation, "notes": notes}
        
        # Look for notation pattern
        notation_patterns = [
            r"(?i)notation:\s*(.+)",
            r"(?i)combo:\s*(.+)",
            r"(?i)inputs?:\s*(.+)"
        ]
        
        for pattern in notation_patterns:
            match = re.search(pattern, description, re.MULTILINE)
            if match:
                found_notation = match.group(1).strip()
                # Take only the first line and clean it up
                found_notation = found_notation.split('\n')[0].strip()
                if found_notation:
                    # Replace common separators for better readability
                    notation = found_notation.replace(",", " >").replace("->", " >")
                    break
        
        # Look for notes pattern
        notes_patterns = [
            r"(?i)notes?:\s*(.+)",
            r"(?i)tips?:\s*(.+)",
            r"(?i)comments?:\s*(.+)"
        ]
        
        for pattern in notes_patterns:
            match = re.search(pattern, description, re.MULTILINE)
            if match:
                found_notes = match.group(1).strip()
                # Take only the first line
                found_notes = found_notes.split('\n')[0].strip()
                if found_notes:
                    notes = found_notes
                    break
        
        return {
            "notation": notation[:500],  # Limit length
            "notes": notes[:300]  # Limit length
        }
    
    @staticmethod
    def _handle_http_error(error: HttpError, playlist_id: str) -> str:
        """
        Handle YouTube API HTTP errors with user-friendly messages
        
        Args:
            error: HttpError from YouTube API
            playlist_id: Playlist ID that caused the error
            
        Returns:
            User-friendly error message
        """
        status_code = error.resp.status
        
        if status_code == 400:
            return f"Invalid playlist ID: '{playlist_id}'"
        elif status_code == 403:
            # Check if it's quota exceeded or access forbidden
            error_content = str(error.content)
            if "quotaExceeded" in error_content or "dailyLimitExceeded" in error_content:
                return "YouTube API quota exceeded. Please try again later or contact the bot administrator."
            else:
                return f"Access forbidden to playlist '{playlist_id}'. It may be private or restricted."
        elif status_code == 404:
            return f"Playlist '{playlist_id}' not found. Please check the playlist ID or URL."
        elif status_code == 500:
            return "YouTube API is temporarily unavailable. Please try again later."
        elif status_code == 503:
            return "YouTube API is temporarily overloaded. Please try again in a few minutes."
        else:
            return f"YouTube API error (status {status_code}). Please try again or contact support."
    
    def clear_cache(self) -> None:
        """Clear all cached playlist data"""
        if hasattr(self.fetch_playlist, 'clear_cache'):
            self.fetch_playlist.clear_cache()
            logger.info("YouTube service cache cleared")
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if hasattr(self.fetch_playlist, 'cache_info'):
            return self.fetch_playlist.cache_info()
        return {"error": "Cache info not available"}
