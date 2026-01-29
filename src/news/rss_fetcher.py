"""
RSS Feed Fetcher Module
Fetches news from multiple RSS feeds with rate limiting and error handling.

THREAD SAFETY: Lock-free design using atomic operations with Counter
"""

import asyncio
import aiohttp
import feedparser
import hashlib
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional
from email.utils import parsedate_to_datetime

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

from ..utils.logger_setup import setup_logger
from ..utils.timezone_utils import get_current_time, to_ist
from .models import NewsItem

logger = setup_logger("rss_fetcher")


class RSSFetcher:
    """
    Asynchronous RSS feed fetcher with parallel processing.
    
    Design:
    - Fetches all feeds in parallel using asyncio.gather()
    - Uses atomic Counter for statistics
    - No shared mutable state requiring locks
    
    Supports all 13 Business Standard RSS feeds:
    - 6 General feeds (top stories, latest, today's paper, markets, popular, editor's pick)
    - 7 Industry feeds (industry, auto, sme, banking, agriculture, news, aviation)
    """
    
    def __init__(self, 
                 feeds: Optional[Dict[str, str]] = None,
                 timeout_seconds: int = 30,
                 max_concurrent: int = 5,
                 user_agent: str = None,
                 scrape_full_articles: bool = False):
        """
        Initialize RSS fetcher.
        
        Args:
            feeds: Dictionary of feed_name -> feed_url (required)
            timeout_seconds: Request timeout per feed
            max_concurrent: Max parallel feed fetches
            user_agent: HTTP User-Agent header
            scrape_full_articles: Whether to scrape full article content
        """
        if not feeds:
            raise ValueError("RSS feeds configuration is required")
        
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.scrape_full_articles = scrape_full_articles
        
        if scrape_full_articles and not BS4_AVAILABLE:
            logger.warning("beautifulsoup4 not installed - article scraping disabled")
            self.scrape_full_articles = False
        
        # Use a realistic browser User-Agent to avoid 403 blocks
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Request headers to mimic browser
        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }
        
        # Use provided feeds from config
        self.feeds = dict(feeds)
        
        # Lock-free statistics using Counter
        self.stats = Counter({
            "feeds_fetched": 0,
            "feeds_failed": 0,
            "items_parsed": 0,
            "parse_errors": 0,
            "total_cycles": 0,
        })
        
        logger.info(f"RSSFetcher initialized with {len(self.feeds)} feeds")
    
    async def fetch_all_feeds(self) -> List[NewsItem]:
        """
        Fetch all RSS feeds in parallel.
        
        Returns:
            List of NewsItem objects from all feeds
        """
        fetch_start = get_current_time()
        self.stats["total_cycles"] += 1
        
        try:
            async with aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.headers
            ) as session:
                # Create tasks for all feeds
                tasks = [
                    self._fetch_single_feed(session, feed_name, feed_url)
                    for feed_name, feed_url in self.feeds.items()
                ]
                
                # Execute all in parallel
                results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Flatten results, handling exceptions
            all_items = []
            feeds_success = 0
            feeds_failed = 0
            
            for feed_name, result in zip(self.feeds.keys(), results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to fetch {feed_name}: {result}")
                    feeds_failed += 1
                else:
                    all_items.extend(result)
                    feeds_success += 1
            
            self.stats["feeds_fetched"] += feeds_success
            self.stats["feeds_failed"] += feeds_failed
            
            fetch_duration = (get_current_time() - fetch_start).total_seconds()
            logger.info(
                f"Fetched {len(all_items)} items from {feeds_success} feeds "
                f"in {fetch_duration:.2f}s ({feeds_failed} failed)"
            )
            
            return all_items
            
        except Exception as e:
            logger.error(f"Critical error in fetch_all_feeds: {e}", exc_info=True)
            return []
    
    async def fetch_single_feed_by_name(self, feed_name: str) -> List[NewsItem]:
        """
        Fetch a single feed by name (for testing).
        
        Args:
            feed_name: Name of the feed to fetch
            
        Returns:
            List of NewsItem objects
        """
        if feed_name not in self.feeds:
            raise ValueError(f"Unknown feed: {feed_name}")
        
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers
        ) as session:
            return await self._fetch_single_feed(
                session, feed_name, self.feeds[feed_name]
            )
    
    async def _fetch_single_feed(self, 
                                  session: aiohttp.ClientSession,
                                  feed_name: str, 
                                  feed_url: str) -> List[NewsItem]:
        """
        Fetch a single RSS feed with rate limiting.
        
        Args:
            session: aiohttp session
            feed_name: Name identifier for the feed
            feed_url: RSS feed URL
            
        Returns:
            List of NewsItem objects
        """
        async with self.semaphore:  # Rate limiting
            try:
                logger.debug(f"Fetching feed: {feed_name}")
                
                async with session.get(feed_url) as response:
                    if response.status != 200:
                        logger.warning(f"Feed {feed_name} returned status {response.status}")
                        return []
                    
                    content = await response.text()
                    items = await self._parse_feed(content, feed_name, session)
                    
                    logger.debug(f"Parsed {len(items)} items from {feed_name}")
                    return items
                    
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {feed_name}")
                raise
            except aiohttp.ClientError as e:
                logger.error(f"HTTP error fetching {feed_name}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error fetching {feed_name}: {e}")
                raise
    
    async def _scrape_article_content(self, url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Scrape full article content from URL.
        
        Args:
            url: Article URL
            session: aiohttp session
            
        Returns:
            Article text or None if scraping fails
        """
        if not BS4_AVAILABLE:
            return None
            
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove unwanted elements
                for element in soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                    element.decompose()
                
                # Try common article content containers
                article_content = None
                for selector in ['article', '.article-content', '.story-content', '.post-content', 'main']:
                    if selector.startswith('.'):
                        content = soup.find(class_=selector[1:])
                    else:
                        content = soup.find(selector)
                    if content:
                        article_content = content.get_text(separator='\n', strip=True)
                        break
                
                # Fallback to body if no article container found
                if not article_content and soup.body:
                    article_content = soup.body.get_text(separator='\n', strip=True)
                
                # Limit content size (max 5000 chars for API efficiency)
                if article_content and len(article_content) > 5000:
                    article_content = article_content[:5000] + "... (truncated)"
                
                return article_content
                
        except Exception as e:
            logger.debug(f"Failed to scrape article {url}: {e}")
            return None
    
    async def scrape_article(self, news_item: NewsItem) -> Optional[str]:
        """Scrape full article content for a NewsItem (public method)."""
        if not self.scrape_full_articles or not news_item.link:
            return None
        
        if news_item.raw_content:  # Already has content
            return news_item.raw_content
        
        logger.info(f"🔍 Scraping: {news_item.title[:50]}...")
        async with aiohttp.ClientSession(headers={'User-Agent': self.user_agent}) as session:
            content = await self._scrape_article_content(news_item.link, session)
            if content:
                logger.info(f"✅ Scraped: {len(content)} chars from {news_item.title[:40]}...")
            else:
                logger.info(f"⚠️ Scraping failed for: {news_item.title[:40]}...")
            return content
    
    async def _parse_feed(self, content: str, feed_name: str, session: aiohttp.ClientSession) -> List[NewsItem]:
        """
        Parse RSS feed content into NewsItem objects and optionally scrape full articles.
        
        Args:
            content: Raw RSS XML content
            feed_name: Source feed name
            session: aiohttp session for article scraping
            
        Returns:
            List of NewsItem objects
        """
        items = []
        
        try:
            feed = feedparser.parse(content)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"Feed {feed_name} has parsing issues: {feed.bozo_exception}")
            
            for entry in feed.entries:
                try:
                    # Generate unique ID from title + published date
                    title = entry.get('title', '').strip()
                    logger.info(f"📄 Read: [{feed_name}] {title[:60]}...")
                    published_str = entry.get('published', '')
                    
                    if not title:
                        continue  # Skip entries without title
                    
                    news_id = self._generate_news_id(title, published_str)
                    
                    # Parse published date
                    published_date = self._parse_date(published_str)
                    
                    # Get description from summary or description field
                    description = entry.get('summary', entry.get('description', '')).strip()
                    
                    # Clean HTML tags from description
                    description = self._clean_html(description)
                    
                    # Get raw content if available from RSS feed
                    raw_content = None
                    if entry.get('content'):
                        raw_content = entry['content'][0].get('value', '')
                    
                    # Note: Article scraping moved to after deduplication for efficiency
                    # Will only scrape articles that are actually new
                    
                    item = NewsItem(
                        news_id=news_id,
                        title=title,
                        description=description,
                        link=entry.get('link', ''),
                        published_date=published_date,
                        source_feed=feed_name,
                        raw_content=raw_content,
                        fetch_timestamp=get_current_time()
                    )
                    
                    items.append(item)
                    self.stats["items_parsed"] += 1
                    
                except Exception as e:
                    logger.warning(f"Error parsing entry in {feed_name}: {e}")
                    self.stats["parse_errors"] += 1
                    
        except Exception as e:
            logger.error(f"Error parsing feed {feed_name}: {e}")
            raise
            
        return items
    
    def _generate_news_id(self, title: str, published: str) -> str:
        """
        Generate unique news ID from title and date.
        
        Uses SHA256 hash truncated to 16 characters for uniqueness.
        """
        content = f"{title}_{published}"
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]
    
    def _parse_date(self, date_str: Optional[str]) -> datetime:
        """
        Parse date string to datetime, defaulting to current time.
        
        Handles RFC 2822 date format commonly used in RSS feeds.
        """
        if not date_str:
            return get_current_time()
        
        try:
            parsed = parsedate_to_datetime(date_str)
            return to_ist(parsed)
        except Exception:
            try:
                # Try ISO format as fallback
                from dateutil import parser
                parsed = parser.parse(date_str)
                return to_ist(parsed)
            except Exception:
                logger.debug(f"Could not parse date: {date_str}")
                return get_current_time()
    
    def _clean_html(self, text: str) -> str:
        """
        Remove HTML tags from text.
        
        Simple regex-based cleaning for RSS descriptions.
        """
        import re
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        import html
        clean = html.unescape(clean)
        # Normalize whitespace
        clean = ' '.join(clean.split())
        return clean.strip()
    
    def get_stats(self) -> Dict[str, int]:
        """Get fetcher statistics."""
        return dict(self.stats)
    
    def reset_stats(self):
        """Reset statistics counters."""
        self.stats = Counter({
            "feeds_fetched": 0,
            "feeds_failed": 0,
            "items_parsed": 0,
            "parse_errors": 0,
            "total_cycles": 0,
        })
    
    def get_feed_names(self) -> List[str]:
        """Get list of configured feed names."""
        return list(self.feeds.keys())
    
    def get_feed_count(self) -> int:
        """Get number of configured feeds."""
        return len(self.feeds)
