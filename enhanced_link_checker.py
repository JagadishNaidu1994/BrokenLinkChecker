#!/usr/bin/env python3
"""
Enhanced Broken Link Checker with strict validation and folder categorization

Features:
- Multiple retry attempts with exponential backoff
- Stricter validation before marking as broken
- Folder/category extraction from source URLs
- Team-based Slack notifications
- CSV export with category column

Author: Claude Opus 4.6
"""

import os
import sys
import json
import time
import logging
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Tuple, Optional
from urllib.parse import urljoin, urlparse, unquote
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(log_file: str = "link_checker_enhanced.log") -> logging.Logger:
    """Configure structured logging."""
    formatter = logging.Formatter(
        fmt='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logger = logging.getLogger('enhanced_link_checker')
    logger.setLevel(logging.INFO)
    # Only add handler if not already configured (prevents duplicate handlers on re-import)
    if not logger.handlers:
        logger.addHandler(console_handler)

    return logger


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Load configuration from environment variables."""

    def __init__(self):
        env_file = Path(__file__).parent / '.env'
        if env_file.exists():
            self._load_env_file(env_file)

        self.docs_urls = [url.strip() for url in os.getenv('DOCS_URLS', '').split(',') if url.strip()]
        self.max_depth = int(os.getenv('MAX_CRAWL_DEPTH', '3'))  # NOTE: Not enforced for internal domain links
        self.max_pages = int(os.getenv('MAX_PAGES_PER_SITE', '100'))
        self.max_links = int(os.getenv('MAX_LINKS_TO_CHECK', '0'))
        self.follow_external = os.getenv('FOLLOW_EXTERNAL_LINKS', 'false').lower() == 'true'
        self.check_external = os.getenv('CHECK_EXTERNAL_LINKS', 'true').lower() == 'true'
        self.timeout = int(os.getenv('REQUEST_TIMEOUT_SECONDS', '10'))
        self.parallel_workers = int(os.getenv('PARALLEL_WORKERS', '20'))

        # Enhanced retry settings
        self.max_retries = int(os.getenv('MAX_RETRIES', '5'))  # More retries for verification
        self.retry_backoff = float(os.getenv('RETRY_BACKOFF', '2.0'))  # Exponential backoff
        self.verify_ssl_strict = os.getenv('VERIFY_SSL_STRICT', 'false').lower() == 'true'

        exclude_str = os.getenv('EXCLUDE_PATTERNS', '')
        self.exclude_patterns = [p.strip() for p in exclude_str.split(',') if p.strip()]

        self.enable_desktop = os.getenv('ENABLE_DESKTOP_NOTIFICATIONS', 'true').lower() == 'true'
        self.enable_slack = os.getenv('ENABLE_SLACK_NOTIFICATIONS', 'false').lower() == 'true'
        self.slack_webhook = os.getenv('SLACK_WEBHOOK_URL', '')
        self.slack_channel = os.getenv('SLACK_CHANNEL', '')
        self.notification_sound = os.getenv('NOTIFICATION_SOUND', 'Glass')

        self.min_broken_links_alert = int(os.getenv('MIN_BROKEN_LINKS_FOR_ALERT', '1'))
        self.notify_on_completion = os.getenv('NOTIFY_ON_COMPLETION', 'true').lower() == 'true'

        # GitHub Pages settings
        self.github_repo_name = os.getenv('GITHUB_REPO_NAME', 'broken-links-reports')
        self.github_username = os.getenv('GITHUB_USERNAME', '')
        self.enable_github_upload = os.getenv('ENABLE_GITHUB_UPLOAD', 'true').lower() == 'true'

        self.report_dir = Path(__file__).parent / 'reports'
        self.report_dir.mkdir(exist_ok=True)

        self.check_interval = int(os.getenv('CHECK_INTERVAL_HOURS', '24'))

    def _load_env_file(self, env_file: Path):
        """Load environment variables from .env file."""
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    value = value.split('#')[0].strip()
                    os.environ[key.strip()] = value

    def validate(self) -> bool:
        """Validate required configuration."""
        if not self.docs_urls:
            print("❌ No documentation URLs configured")
            return False
        return True


# ============================================================================
# HOMEPAGE FOLDER CATEGORIZATION
# ============================================================================

class CategoryExtractor:
    """Extract homepage folder category from URLs."""

    # Homepage folder mapping based on keywords in page names
    HOMEPAGE_FOLDERS = {
        'Sonatype Nexus Repository': [
            'nexus-repository',
            'nxrm',
            'repository-manager',
            'apt-repositories',
            'bower-repositories',
            'npm-',
            'maven-',
            'docker-',
            'pypi-',
            'nuget-',
            'helm-',
            'yum-',
            'go-',
            'conda-repositories',
            'conan-repositories',
            'cocoapods-repositories',
            'composer-repositories',
            'git-lfs-repositories',
            'p2-repositories',
            'r-repositories',
            'raw-repositories',
            'rubygems-repositories',
            'upgrading-nexus-repository',
            'deploy-nexus-repository',
            'resilient-nexus-repository',
            'configuration',
            'config',
            'logging',
            'authentication',
            'saml',
            'ldap',
            'ssl',
            'atlassian-crowd',
            'system-requirements',
            'database',
            'high-availability',
            'backup',
            'restore',
            'migration',
        ],

        'Sonatype IQ Server': [
            'iq-server',
            'iq-20',  # IQ release notes like iq-2023, iq-2024
            'iq-for-idea',
            'iq-for-eclipse',
            'iq-for-visual-studio',
            'download-and-compatibility',
            'java-compatibility-matrix',
            'cloud-deployments',
            'container-deployments',
        ],

        'Sonatype Lifecycle': [
            'lifecycle',
            'policy-management',
            'automated-pull-requests',
            'pull-request-commenting',
            'hugging-face-model-analysis',
            'ai-component-analysis',
            'security',
            'log4j',
            'vulnerability',
            'cve',
            'find-and-fix',
        ],

        'Sonatype Repository Firewall': [
            'firewall',
            'repository-firewall',
            'quarantine',
        ],

        'Sonatype Integrations': [
            'integration',
            'jenkins',
            'jira',
            'bamboo',
            'crowd',
            'gitlab',
            'github',
            'azure-devops',
            'teamcity',
            'fortify',
            'sonarqube',
            'notable-integrations-changes',
        ],

        'Sonatype SBOM Manager': [
            'sbom',
            'software-bill-of-materials',
            'sbom-manager',
        ],

        'Sonatype Developer': [
            'developer',
            'bundle-development',
            'plugin',
            'api',
            'sdk',
        ],

        'Sonatype Guide': [
            'guide',
            'getting-started',
            'overview',
        ],

        'Sonatype Platform Overview': [
            'platform-overview',
            'announcements',
            'sunsetting',
        ],
    }

    @staticmethod
    def extract_category(url: str, base_url: str = "") -> str:
        """Extract homepage folder category from URL.

        Returns one of the 9 official Sonatype categories.
        If no match found, defaults to 'Sonatype Nexus Repository' as it's the most common.
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            filename = Path(path).stem

            # Check homepage folders
            for folder, keywords in CategoryExtractor.HOMEPAGE_FOLDERS.items():
                for keyword in keywords:
                    if keyword in filename:
                        return folder

            # Default to Nexus Repository for unmatched pages
            # (most documentation is Nexus-related)
            return "Sonatype Nexus Repository"

        except Exception:
            return "Sonatype Nexus Repository"

    @staticmethod
    def get_display_category(category: str) -> str:
        """Convert category to display-friendly name with emoji.

        Only supports the 9 official Sonatype categories.
        """
        emoji_map = {
            'Sonatype Platform Overview': '🏠',
            'Sonatype Guide': '📖',
            'Sonatype Nexus Repository': '📦',
            'Sonatype IQ Server': '🔍',
            'Sonatype Lifecycle': '🔄',
            'Sonatype Repository Firewall': '🛡️',
            'Sonatype SBOM Manager': '📋',
            'Sonatype Developer': '💻',
            'Sonatype Integrations': '🔗',
        }
        emoji = emoji_map.get(category, '📦')
        return f"{emoji} {category}"


# ============================================================================
# ENHANCED LINK CHECKER
# ============================================================================

class EnhancedLinkChecker:
    """Check links with strict validation and retry logic."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.session = self._create_session()
        self.checked_urls: Dict[str, Tuple[int, str]] = {}
        self.verification_cache: Dict[str, bool] = {}  # url -> is_truly_broken

    def _create_session(self) -> requests.Session:
        """Create a requests session with enhanced retry logic."""
        session = requests.Session()

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=self.config.retry_backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=20, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0'
        })

        return session

    def check_link_with_retry(self, url: str, attempt: int = 1) -> Tuple[int, str]:
        """
        Check link with exponential backoff retry.

        Returns:
            Tuple of (status_code, error_message)
        """
        if url in self.checked_urls:
            return self.checked_urls[url]

        # URN links are invalid in HTML - return as broken immediately
        if url.startswith('urn:'):
            result = (0, 'Invalid URN link in HTML (not a valid web URL)')
            self.checked_urls[url] = result
            return result

        # 404-page.html links are suspicious broken references
        if '404-page.html' in url:
            result = (404, 'Link to 404 error page (likely broken reference)')
            self.checked_urls[url] = result
            return result

        try:
            # Try HEAD first
            response = self.session.head(
                url,
                timeout=self.config.timeout,
                allow_redirects=True,
                verify=True  # Verify SSL certificates
            )

            # If HEAD fails with client error, try GET
            if response.status_code >= 400:
                time.sleep(0.5)  # Small delay
                response = self.session.get(
                    url,
                    timeout=self.config.timeout,
                    allow_redirects=True,
                    stream=True,
                    verify=True
                )
                response.close()

            status = response.status_code
            error = "" if status < 400 else f"HTTP {status}"

            self.checked_urls[url] = (status, error)
            return (status, error)

        except requests.exceptions.Timeout:
            # Retry on timeout with exponential backoff
            if attempt < self.config.max_retries:
                wait_time = self.config.retry_backoff ** attempt
                self.logger.debug(f"Timeout on {url}, retrying in {wait_time}s (attempt {attempt}/{self.config.max_retries})")
                time.sleep(wait_time)
                return self.check_link_with_retry(url, attempt + 1)

            self.checked_urls[url] = (0, "Timeout (after retries)")
            return (0, "Timeout (after retries)")

        except requests.exceptions.SSLError as e:
            # SSL errors might be temporary, retry
            if attempt < self.config.max_retries:
                wait_time = self.config.retry_backoff ** attempt
                self.logger.debug(f"SSL Error on {url}, retrying in {wait_time}s (attempt {attempt}/{self.config.max_retries})")
                time.sleep(wait_time)
                return self.check_link_with_retry(url, attempt + 1)

            self.checked_urls[url] = (0, f"SSL Error (persistent)")
            return (0, f"SSL Error (persistent)")

        except requests.exceptions.ConnectionError as e:
            # Connection errors might be temporary, retry
            if attempt < self.config.max_retries:
                wait_time = self.config.retry_backoff ** attempt
                self.logger.debug(f"Connection error on {url}, retrying in {wait_time}s (attempt {attempt}/{self.config.max_retries})")
                time.sleep(wait_time)
                return self.check_link_with_retry(url, attempt + 1)

            error_str = str(e)
            # Check if it's a local URL (localhost, 127.0.0.1)
            if 'localhost' in url.lower() or '127.0.0.1' in url or '0.0.0.0' in url:
                self.checked_urls[url] = (0, "Local URL (expected)")
                return (0, "Local URL (expected)")

            self.checked_urls[url] = (0, "Connection Failed (persistent)")
            return (0, "Connection Failed (persistent)")

        except requests.exceptions.RequestException as e:
            error_msg = str(e)[:100]
            self.checked_urls[url] = (0, error_msg)
            return (0, error_msg)

    def is_truly_broken(self, url: str, status: int, error: str) -> bool:
        """
        Determine if a link is truly broken or a false positive.

        Returns True only for genuinely broken links.
        """
        # URN schemes are invalid in HTML - report as broken
        if url.startswith('urn:'):
            return True

        # Links to 404-page.html are suspicious - likely broken references
        if '404-page.html' in url:
            return True

        # Skip ideas.sonatype.com connection pool errors
        if 'ideas.sonatype.com' in url and 'HTTPSConnectionPool' in error:
            return False

        # 403 Forbidden - usually bot blocking, not truly broken
        if status == 403:
            return False

        # Local URLs are not broken, just not accessible
        if 'localhost' in url.lower() or '127.0.0.1' in url or 'Local URL' in error:
            return False

        # GPG/PGP key files from repo.sonatype.com - working as intended (trigger downloads)
        # These return 404 on HEAD but actually work (download on GET)
        # Pattern: repo.sonatype.com/*/pki/*/GPG-KEY-*.asc
        if 'repo.sonatype.com' in url and 'GPG-KEY' in url and url.endswith('.asc'):
            return False

        # 404, 500+ are truly broken
        if status == 404 or status >= 500:
            return True

        # Connection failures after retries are truly broken
        if 'Connection Failed (persistent)' in error:
            return True

        # Skip SSL errors - often false positives (certificate issues, not broken links)
        if 'SSL Error (persistent)' in error:
            return False

        # Persistent timeouts after retries
        if 'Timeout (after retries)' in error:
            return True

        return False


# ============================================================================
# WEB CRAWLER (reuse from original)
# ============================================================================

class WebCrawler:
    """Crawl documentation sites and extract links."""

    def __init__(self, config: Config, logger: logging.Logger, link_checker: EnhancedLinkChecker):
        self.config = config
        self.logger = logger
        self.link_checker = link_checker
        self.visited_pages: Set[str] = set()
        self.normalized_urls: Set[str] = set()  # Track normalized URLs to detect duplicates
        self.pages_to_crawl: List[Tuple[str, int]] = []
        self.all_links: Dict[str, Set[str]] = defaultdict(set)

    def normalize_url(self, url: str) -> str:
        """
        Normalize URL to detect duplicates.

        Converts various URL patterns to canonical form:
        - /en/en/page.html -> /en/page.html
        - /document/preview/page.html -> /en/page.html
        - Removes query strings and fragments
        """
        # Remove query strings and fragments for normalization
        base_url = url.split('?')[0].split('#')[0]

        # Normalize duplicate /en/en/ pattern
        base_url = base_url.replace('/en/en/', '/en/')

        # Normalize /document/preview/ to /en/
        base_url = base_url.replace('/document/preview/', '/en/')
        base_url = base_url.replace('/document/index.html', '/en/index.html')

        return base_url

    def should_crawl(self, url: str, base_domain: str) -> bool:
        """Check if URL should be crawled."""
        parsed = urlparse(url)

        if parsed.scheme not in ['http', 'https']:
            return False

        for pattern in self.config.exclude_patterns:
            if re.search(pattern, url):
                return False

        if not self.config.follow_external:
            if parsed.netloc != base_domain:
                return False

        # Check if normalized URL already visited (duplicate detection)
        normalized = self.normalize_url(url)
        if normalized in self.normalized_urls:
            self.logger.debug(f"Skipping duplicate: {url} (normalized: {normalized})")
            return False

        return True

    def extract_links(self, html: str, base_url: str) -> Dict[str, str]:
        """Extract all links from HTML with their surrounding text context.

        Returns:
            Dict mapping URL to context text (sentence/paragraph containing the link)
        """
        links_with_context = {}

        try:
            soup = BeautifulSoup(html, 'html.parser')

            for tag in soup.find_all('a', href=True):
                href = tag['href']
                absolute_url = urljoin(base_url, href)

                # Check if this is a 404-page.html link BEFORE stripping anchor
                is_404_page = '404-page.html' in absolute_url

                # Strip anchors for all URLs by default
                absolute_url_no_anchor = absolute_url.split('#')[0]

                # For 404-page.html, keep the full URL with anchor
                # For everything else, use URL without anchor
                if is_404_page:
                    final_url = absolute_url  # Keep anchor
                else:
                    final_url = absolute_url_no_anchor  # Strip anchor

                if final_url:
                    # Skip excluded patterns
                    excluded = False
                    for pattern in self.config.exclude_patterns:
                        if re.search(pattern, final_url):
                            excluded = True
                            break

                    if excluded:
                        continue

                    # Get the link text
                    link_text = tag.get_text(strip=True)

                    # Try to get surrounding context
                    context = self._extract_context(tag, link_text)

                    links_with_context[final_url] = context

        except Exception as e:
            self.logger.warning(f"Failed to parse HTML from {base_url}: {e}")

        return links_with_context

    def _extract_context(self, tag, link_text: str, max_length: int = 150) -> str:
        """Extract surrounding context text for a link.

        Args:
            tag: The anchor tag
            link_text: Text of the link itself
            max_length: Maximum context length

        Returns:
            Context string with the link highlighted
        """
        # Try to get parent paragraph or list item
        parent = tag.find_parent(['p', 'li', 'td', 'div'])

        if parent:
            # Get all text from parent
            text = parent.get_text(separator=' ', strip=True)

            # Truncate if too long
            if len(text) > max_length:
                # Try to find the link text position
                if link_text in text:
                    link_pos = text.find(link_text)
                    start = max(0, link_pos - 60)
                    end = min(len(text), link_pos + len(link_text) + 60)
                    text = '...' + text[start:end] + '...'
                else:
                    text = text[:max_length] + '...'

            return text
        else:
            # Fallback: just return link text
            return link_text if link_text else "(no context)"

    def crawl_site(self, start_url: str) -> Dict[str, Dict[str, str]]:
        """Crawl a documentation site starting from start_url.

        Returns:
            Dict mapping source_url to dict of {link_url: context_text}
        """
        self.logger.info(f"Starting crawl from: {start_url}")

        base_domain = urlparse(start_url).netloc
        self.pages_to_crawl = [(start_url, 0)]
        pages_crawled = 0

        # Crawl all internal pages (no limit), but don't follow external links
        while self.pages_to_crawl and (self.config.max_pages == 0 or pages_crawled < self.config.max_pages):
            current_url, depth = self.pages_to_crawl.pop(0)

            if current_url in self.visited_pages:
                continue

            # No depth limitation - crawl as deep as needed

            # Track normalized URL to prevent duplicates
            normalized = self.normalize_url(current_url)
            self.normalized_urls.add(normalized)

            self.visited_pages.add(current_url)
            pages_crawled += 1

            page_info = f"[{pages_crawled}]" if self.config.max_pages == 0 else f"[{pages_crawled}/{self.config.max_pages}]"
            self.logger.info(f"Crawling {page_info} depth={depth}: {current_url}")

            try:
                response = self.link_checker.session.get(
                    current_url,
                    timeout=self.config.timeout
                )

                if response.status_code != 200:
                    self.logger.warning(f"Failed to fetch {current_url}: HTTP {response.status_code}")
                    continue

                links_with_context = self.extract_links(response.text, current_url)
                self.all_links[current_url] = links_with_context

                for link in links_with_context.keys():
                    if link not in self.visited_pages and self.should_crawl(link, base_domain):
                        self.pages_to_crawl.append((link, depth + 1))

            except Exception as e:
                self.logger.error(f"Error crawling {current_url}: {e}")

        self.logger.info(f"✓ Crawl complete: {pages_crawled} pages visited")

        return self.all_links


# ============================================================================
# ENHANCED REPORT GENERATOR WITH CATEGORIES
# ============================================================================

class EnhancedReportGenerator:
    """Generate reports with category/folder information."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def generate_csv_with_categories(self, broken_links: List[Dict], base_url: str) -> Path:
        """Generate CSV with category column."""
        import csv

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_file = self.config.report_dir / f"broken_links_categorized_{timestamp}.csv"

        # Group by category
        by_category = defaultdict(list)
        for link in broken_links:
            category = CategoryExtractor.extract_category(link['source'], base_url)
            link['category'] = category
            by_category[category].append(link)

        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Homepage Folder', 'Source Page', 'Broken Link', 'Error', 'Status Code', 'Context'])

            # Write links grouped by category
            for category in sorted(by_category.keys()):
                for link in by_category[category]:
                    writer.writerow([
                        category,
                        link['source'],
                        link['url'],
                        link['error'],
                        link['status'],
                        link.get('context', '(no context)')
                    ])

        self.logger.info(f"✓ CSV with categories saved: {csv_file}")
        return csv_file

    def generate_category_summary(self, broken_links: List[Dict], base_url: str) -> Dict[str, List[Dict]]:
        """Generate summary grouped by category."""
        by_category = defaultdict(list)

        for link in broken_links:
            category = CategoryExtractor.extract_category(link['source'], base_url)
            by_category[category].append(link)

        return dict(by_category)

    def generate_html_report(self, broken_links: List[Dict], base_url: str) -> Path:
        """Generate HTML report with categories and context."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file = self.config.report_dir / f"broken_links_report_{timestamp}.html"

        # Group by category
        by_category = defaultdict(list)
        for link in broken_links:
            category = CategoryExtractor.extract_category(link['source'], base_url)
            link['category'] = category
            by_category[category].append(link)

        # Build rows JSON for JS filtering
        import json as _json
        all_rows = []
        for category in sorted(by_category.keys()):
            display_cat = CategoryExtractor.get_display_category(category)
            for link in by_category[category]:
                error_type = link['error']
                if 'HTTP 404' in error_type or '404' in error_type:
                    error_label = '404'
                    error_class = 'e404'
                elif 'Connection Failed' in error_type or 'connection' in error_type.lower():
                    error_label = 'Connection'
                    error_class = 'econn'
                elif 'SSL' in error_type:
                    error_label = 'SSL'
                    error_class = 'essl'
                elif 'Timeout' in error_type:
                    error_label = 'Timeout'
                    error_class = 'etimeout'
                elif 'Invalid' in error_type or 'not a valid' in error_type.lower():
                    error_label = 'Invalid URL'
                    error_class = 'einvalid'
                else:
                    error_label = error_type[:18]
                    error_class = 'eother'
                source = link['source']
                url = link['url']
                context = (link.get('context') or '').strip()
                if len(context) > 120:
                    context = context[:117] + '...'
                all_rows.append({
                    'cat': display_cat,
                    'src': source,
                    'url': url,
                    'ctx': context,
                    'err': error_label,
                    'ecls': error_class,
                })

        rows_json = _json.dumps(all_rows)
        cats_json = _json.dumps(sorted([CategoryExtractor.get_display_category(c) for c in by_category.keys()]))
        scan_ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_broken = len(broken_links)
        total_cats = len(by_category)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Broken Links Report — {scan_ts}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:13px;background:#f4f5f7;color:#172b4d;min-height:100vh}}
a{{color:#0052cc;text-decoration:none}}a:hover{{text-decoration:underline}}

/* ── top bar ── */
.topbar{{background:#fff;border-bottom:1px solid #dfe1e6;padding:0 24px;display:flex;align-items:center;height:48px;gap:16px;position:sticky;top:0;z-index:100}}
.topbar-logo{{font-weight:700;font-size:14px;color:#172b4d;display:flex;align-items:center;gap:6px}}
.topbar-logo span{{color:#e34234}}
.topbar-meta{{color:#6b778c;font-size:12px;margin-left:auto}}

/* ── layout ── */
.page{{max-width:1320px;margin:0 auto;padding:20px 24px}}

/* ── stat cards ── */
.stats{{display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap}}
.stat-card{{background:#fff;border:1px solid #dfe1e6;border-radius:4px;padding:12px 20px;min-width:120px;flex:1}}
.stat-card .val{{font-size:28px;font-weight:700;line-height:1}}
.stat-card .lbl{{font-size:11px;color:#6b778c;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
.stat-card.red .val{{color:#de350b}}
.stat-card.green .val{{color:#00875a}}
.stat-card.blue .val{{color:#0052cc}}
.stat-card.grey .val{{font-size:13px;font-weight:600;color:#172b4d;padding-top:4px}}

/* ── page heading ── */
.page-heading{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px}}
.page-heading h1{{font-size:20px;font-weight:700;color:#172b4d}}
.page-sub{{font-size:12px;color:#6b778c;margin-top:3px}}

/* ── toolbar ── */
.toolbar{{background:#fff;border:1px solid #dfe1e6;border-radius:4px;padding:10px 14px;display:flex;gap:10px;align-items:center;margin-bottom:16px;flex-wrap:wrap}}
.toolbar input{{border:1px solid #dfe1e6;border-radius:3px;padding:5px 10px;font-size:12px;width:260px;outline:none;color:#172b4d}}
.toolbar input:focus{{border-color:#4c9aff;box-shadow:0 0 0 2px rgba(76,154,255,.2)}}
.toolbar select{{border:1px solid #dfe1e6;border-radius:3px;padding:5px 10px;font-size:12px;color:#172b4d;background:#fff;outline:none;cursor:pointer}}
.toolbar select:focus{{border-color:#4c9aff}}
.toolbar .sep{{width:1px;height:24px;background:#dfe1e6}}
.toolbar .count{{margin-left:auto;font-size:12px;color:#6b778c}}
.btn-clear{{border:1px solid #dfe1e6;border-radius:3px;padding:5px 10px;font-size:12px;background:#fff;cursor:pointer;color:#6b778c}}
.btn-clear:hover{{background:#f4f5f7}}

/* ── table ── */
.tbl-wrap{{background:#fff;border:1px solid #dfe1e6;border-radius:4px;overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
thead tr{{background:#f4f5f7;border-bottom:2px solid #dfe1e6}}
th{{padding:8px 12px;text-align:left;font-size:11px;font-weight:700;color:#6b778c;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap}}
td{{padding:8px 12px;border-bottom:1px solid #f4f5f7;vertical-align:top;font-size:12px}}
tbody tr:last-child td{{border-bottom:none}}
tbody tr:hover td{{background:#f8f9ff}}
.col-cat{{width:14%}}
.col-src{{width:22%}}
.col-url{{width:30%}}
.col-ctx{{width:24%}}
.col-err{{width:10%}}

.cat-pill{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:11px;font-weight:600;background:#ebecf0;color:#172b4d}}
.src-link{{color:#0052cc;font-size:11px;word-break:break-all}}
.broken-url{{font-family:'SFMono-Regular',Consolas,monospace;font-size:11px;color:#de350b;word-break:break-all}}
.ctx-text{{color:#6b778c;font-size:11px;line-height:1.4}}

.badge{{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:700;white-space:nowrap}}
.e404{{background:#ffebe6;color:#de350b}}
.econn{{background:#fff0b3;color:#974f0c}}
.essl{{background:#e3fcef;color:#006644}}
.etimeout{{background:#e6f0ff;color:#0052cc}}
.einvalid{{background:#f4f5f7;color:#6b778c}}
.eother{{background:#f4f5f7;color:#6b778c}}

/* ── empty state ── */
.empty{{text-align:center;padding:60px 20px;color:#6b778c}}
.empty .ico{{font-size:40px;margin-bottom:12px}}
.empty p{{font-size:14px}}

/* ── footer ── */
.footer{{text-align:center;color:#6b778c;font-size:11px;margin-top:24px;padding-bottom:24px}}
</style>
</head>
<body>

<div class="topbar">
  <div class="topbar-logo">Sonatype <span>&bull;</span> Documentation Health</div>
  <div class="topbar-meta">Generated {scan_ts}</div>
</div>

<div class="page">

  <div class="page-heading">
    <div>
      <h1>Broken Link Checker Report</h1>
      <div class="page-sub">Scanned: <a href="{base_url}" target="_blank">{base_url}</a></div>
    </div>
  </div>

  <div class="stats">
    <div class="stat-card red">
      <div class="val" id="visibleCount">{total_broken}</div>
      <div class="lbl">Showing</div>
    </div>
    <div class="stat-card green">
      <div class="val">{total_broken}</div>
      <div class="lbl">Total Broken</div>
    </div>
    <div class="stat-card blue">
      <div class="val">{total_cats}</div>
      <div class="lbl">Categories</div>
    </div>
    <div class="stat-card grey">
      <div class="val">{scan_ts}</div>
      <div class="lbl">Scan Date</div>
    </div>
  </div>

  <div class="toolbar">
    <input type="text" id="searchBox" placeholder="Search URL, source or context…" oninput="applyFilters()">
    <div class="sep"></div>
    <select id="catFilter" onchange="applyFilters()">
      <option value="">All Categories</option>
    </select>
    <select id="errFilter" onchange="applyFilters()">
      <option value="">All Errors</option>
      <option value="404">404</option>
      <option value="Connection">Connection</option>
      <option value="Timeout">Timeout</option>
      <option value="SSL">SSL</option>
      <option value="Invalid URL">Invalid URL</option>
    </select>
    <button class="btn-clear" onclick="clearFilters()">Clear</button>
    <div class="count" id="countLabel">{total_broken} results</div>
  </div>

  <div class="tbl-wrap">
    <table>
      <thead>
        <tr>
          <th class="col-cat">Category</th>
          <th class="col-src">Source Page</th>
          <th class="col-url">Broken URL</th>
          <th class="col-ctx">Context</th>
          <th class="col-err">Error</th>
        </tr>
      </thead>
      <tbody id="tableBody"></tbody>
    </table>
    <div class="empty" id="emptyState" style="display:none">
      <div class="ico">🔍</div>
      <p>No results match your filters.</p>
    </div>
  </div>

  <div class="footer">Sonatype Documentation Health Check &mdash; {scan_ts}</div>
</div>

<script>
const ROWS = {rows_json};
const CATS = {cats_json};

// Populate category filter
const catSel = document.getElementById('catFilter');
CATS.forEach(c => {{
  const o = document.createElement('option');
  o.value = c; o.textContent = c;
  catSel.appendChild(o);
}});

function renderRow(r) {{
  const srcShort = r.src.replace(/https?:\\/\\/[^/]+/, '').replace(/\\.html$/, '') || r.src;
  return `<tr data-cat="${{r.cat}}" data-err="${{r.err}}">
    <td><span class="cat-pill">${{r.cat}}</span></td>
    <td><a class="src-link" href="${{r.src}}" target="_blank" title="${{r.src}}">${{srcShort}}</a></td>
    <td><span class="broken-url" title="${{r.url}}">${{r.url}}</span></td>
    <td><span class="ctx-text">${{r.ctx || '<em style=\\"color:#c1c7d0\\">—</em>'}}</span></td>
    <td><span class="badge ${{r.ecls}}">${{r.err}}</span></td>
  </tr>`;
}}

function applyFilters() {{
  const q = document.getElementById('searchBox').value.toLowerCase();
  const cat = document.getElementById('catFilter').value;
  const err = document.getElementById('errFilter').value;

  let visible = 0;
  const body = document.getElementById('tableBody');
  body.innerHTML = '';
  const frag = document.createDocumentFragment();

  ROWS.forEach(r => {{
    if (cat && r.cat !== cat) return;
    if (err && r.err !== err) return;
    if (q && !r.url.toLowerCase().includes(q) && !r.src.toLowerCase().includes(q) && !r.ctx.toLowerCase().includes(q)) return;
    const tr = document.createElement('tbody');
    tr.innerHTML = renderRow(r);
    frag.appendChild(tr.firstChild);
    visible++;
  }});

  body.appendChild(frag);
  document.getElementById('visibleCount').textContent = visible;
  document.getElementById('countLabel').textContent = visible + ' result' + (visible !== 1 ? 's' : '');
  document.getElementById('emptyState').style.display = visible === 0 ? 'block' : 'none';
}}

function clearFilters() {{
  document.getElementById('searchBox').value = '';
  document.getElementById('catFilter').value = '';
  document.getElementById('errFilter').value = '';
  applyFilters();
}}

applyFilters();
</script>
</body>
</html>
"""

        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)

        self.logger.info(f"✓ HTML report saved: {html_file}")
        return html_file


# ============================================================================
# GITHUB PAGES UPLOADER
# ============================================================================

class GitHubPagesUploader:
    """Upload reports to GitHub Pages and get public URL."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.repo_name = config.github_repo_name
        self.username = config.github_username or self._get_github_username()

    def _get_github_username(self) -> str:
        """Get GitHub username from gh CLI."""
        try:
            result = subprocess.run(
                ['gh', 'api', 'user', '--jq', '.login'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except Exception as e:
            self.logger.error(f"Failed to get GitHub username: {e}")
            return ""

    def upload_report(self, html_file: Path, csv_file: Path) -> Optional[str]:
        """
        Upload report to GitHub Pages and return public URL.

        Returns:
            Public URL of the uploaded report, or None if upload failed
        """
        if not self.config.enable_github_upload:
            self.logger.info("GitHub upload disabled in config")
            return None

        if not self.username:
            self.logger.error("GitHub username not configured")
            return None

        try:
            self.logger.info(f"📤 Uploading report to GitHub Pages...")

            # Clone or update repo
            repo_dir = Path(__file__).parent / '.github_pages_repo'

            # Use GH_PAT token if available (for GitHub Actions)
            github_token = os.getenv('GITHUB_TOKEN')
            if github_token:
                repo_url = f"https://x-access-token:{github_token}@github.com/{self.username}/{self.repo_name}.git"
            else:
                repo_url = f"https://github.com/{self.username}/{self.repo_name}.git"

            if repo_dir.exists():
                self.logger.info("Updating existing repository...")
                subprocess.run(['git', '-C', str(repo_dir), 'pull'], check=True, capture_output=True)
            else:
                self.logger.info("Cloning repository...")
                subprocess.run(['git', 'clone', repo_url, str(repo_dir)], check=True, capture_output=True)

            # Copy files to repo
            import shutil
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Copy HTML report as latest.html
            shutil.copy(html_file, repo_dir / 'latest.html')

            # Also save timestamped version
            archive_dir = repo_dir / 'archive'
            archive_dir.mkdir(exist_ok=True)
            shutil.copy(html_file, archive_dir / f'report_{timestamp}.html')
            shutil.copy(csv_file, archive_dir / f'report_{timestamp}.csv')

            # Update index.html with last updated time
            index_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url=./latest.html">
    <title>Broken Links Reports</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: linear-gradient(to bottom, #ffffff, #f5f3ff);
        }}
        .container {{
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #6B46C1; }}
        p {{ color: #666; font-size: 1.1em; margin: 10px 0; }}
        a {{ color: #6B46C1; text-decoration: none; font-weight: 600; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 Broken Links Reports</h1>
        <p>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Redirecting to <a href="./latest.html">latest report</a>...</p>
        <p><a href="./archive/">View archive</a></p>
    </div>
</body>
</html>"""

            with open(repo_dir / 'index.html', 'w') as f:
                f.write(index_content)

            # Create archive index
            archive_files = sorted([f for f in archive_dir.glob('*.html')], reverse=True)
            archive_index = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Report Archive</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 20px;
            background: linear-gradient(to bottom, #ffffff, #f5f3ff);
        }
        h1 { color: #6B46C1; }
        ul { list-style: none; padding: 0; }
        li {
            background: white;
            margin: 10px 0;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        a { color: #6B46C1; text-decoration: none; font-weight: 600; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>📚 Report Archive</h1>
    <p><a href="../">← Back to latest</a></p>
    <ul>
"""
            for html_report in archive_files:
                report_name = html_report.stem
                archive_index += f'        <li><a href="./{html_report.name}">📄 {report_name}</a></li>\n'

            archive_index += """    </ul>
</body>
</html>"""

            with open(archive_dir / 'index.html', 'w') as f:
                f.write(archive_index)

            # Commit and push
            subprocess.run(['git', '-C', str(repo_dir), 'add', '.'], check=True, capture_output=True)
            subprocess.run(
                ['git', '-C', str(repo_dir), 'commit', '-m', f'Update report: {timestamp}'],
                capture_output=True
            )
            subprocess.run(['git', '-C', str(repo_dir), 'push'], check=True, capture_output=True)

            # Construct public URL
            public_url = f"https://{self.username}.github.io/{self.repo_name}/"

            self.logger.info(f"✅ Report uploaded successfully!")
            self.logger.info(f"🌐 Public URL: {public_url}")

            return public_url

        except subprocess.CalledProcessError as e:
            self.logger.error(f"Git command failed: {e}")
            self.logger.error(f"Output: {e.stderr if hasattr(e, 'stderr') else 'N/A'}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to upload to GitHub Pages: {e}")
            return None


# ============================================================================
# SLACK NOTIFIER
# ============================================================================

class SlackNotifier:
    """Send Slack notifications with report summary and link."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def send_report_notification(self, broken_links: List[Dict], public_url: str, by_category: Dict[str, List[Dict]], total_checked: int = 0):
        """Send Slack notification with report summary and public URL."""
        if not self.config.enable_slack or not self.config.slack_webhook:
            self.logger.info("Slack notifications disabled or webhook not configured")
            return

        try:
            total_broken = len(broken_links)
            scan_date = datetime.now().strftime('%Y-%m-%d')

            # Category bullet list with emojis
            cat_lines = ""
            for category in sorted(by_category.keys()):
                count = len(by_category[category])
                cat_lines += f"• {category}: *{count}*\n"

            # Key issues — top error types
            from collections import Counter
            error_counts = Counter()
            for lnk in broken_links:
                err = lnk.get('error', '')
                if '404' in err:
                    error_counts['404 Not Found'] += 1
                elif 'Connection' in err:
                    error_counts['Connection Failed'] += 1
                elif 'SSL' in err:
                    error_counts['SSL Error'] += 1
                elif 'Timeout' in err:
                    error_counts['Timeout'] += 1
                else:
                    error_counts[err[:30]] += 1
            top_issues = ', '.join(f"{k} ({v})" for k, v in error_counts.most_common(3))

            checked_str = f"{total_checked:,}" if total_checked else "—"

            message = {
                "channel": self.config.slack_channel if self.config.slack_channel else None,
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🔗 Broken Links Scan Results",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                "Hi Team! :wave:\n\n"
                                "Just sharing this week's broken links scan results. "
                                "Whenever you get a chance, could you take a quick look at the links in your respective areas? "
                                "No rush — just something to keep on the radar as we continue to keep our docs in great shape."
                            )
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f":bar_chart: *Links Checked*\n{checked_str}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f":x: *Broken Found*\n{total_broken}"
                            }
                        ]
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*By Category:*\n{cat_lines.strip()}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":warning: *Key Issues:* {top_issues}"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":page_facing_up: *Full Report:* <{public_url}|View detailed report>"
                        }
                    },
                    {"type": "divider"},
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "Thanks so much for all you do! Feel free to reach out if you have any questions or need help investigating anything. :heart:"
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f":calendar: Scan date: {scan_date}"
                            }
                        ]
                    }
                ]
            }

            # Send to Slack
            response = requests.post(
                self.config.slack_webhook,
                json=message,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info("✅ Slack notification sent successfully!")
            else:
                self.logger.error(f"Failed to send Slack notification: {response.status_code} {response.text}")

        except Exception as e:
            self.logger.error(f"Error sending Slack notification: {e}")

    def _get_category_emoji(self, category: str) -> str:
        """Get emoji for category (9 official categories only)."""
        emoji_map = {
            'Sonatype Platform Overview': '🏠',
            'Sonatype Guide': '📖',
            'Sonatype Nexus Repository': '📦',
            'Sonatype IQ Server': '🔍',
            'Sonatype Lifecycle': '🔄',
            'Sonatype Repository Firewall': '🛡️',
            'Sonatype SBOM Manager': '📋',
            'Sonatype Developer': '💻',
            'Sonatype Integrations': '🔗',
        }
        return emoji_map.get(category, '📦')


# ============================================================================
# ENHANCED MONITOR
# ============================================================================

class EnhancedBrokenLinkMonitor:
    """Enhanced broken link monitoring with categories."""

    def __init__(self, config: Config, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.link_checker = EnhancedLinkChecker(config, logger)
        self.report_gen = EnhancedReportGenerator(config, logger)
        self.github_uploader = GitHubPagesUploader(config, logger)
        self.slack_notifier = SlackNotifier(config, logger)

    def check_all_sites(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Check all sites and return broken links.

        Returns:
            Tuple of (truly_broken_links, false_positives)
        """
        all_broken = []
        all_false_positives = []

        for doc_url in self.config.docs_urls:
            self.logger.info("="*70)
            self.logger.info(f"Checking: {doc_url}")
            self.logger.info("="*70)

            crawler = WebCrawler(self.config, self.logger, self.link_checker)
            all_links = crawler.crawl_site(doc_url)

            self.logger.info(f"\n🔍 Checking links with strict validation ({self.config.parallel_workers} workers)...")

            links_to_check = []
            seen_links = set()  # dedupe across all source pages
            for source_url, links_dict in all_links.items():
                for link, context in links_dict.items():
                    # Skip excluded patterns
                    excluded = False
                    for pattern in self.config.exclude_patterns:
                        if re.search(pattern, link):
                            excluded = True
                            break

                    if excluded:
                        if link not in seen_links:
                            self.logger.info(f"EXCLUDED: {link}")
                            seen_links.add(link)
                    elif link not in seen_links and link not in self.link_checker.checked_urls:
                        seen_links.add(link)
                        links_to_check.append((link, source_url, context))

                    if self.config.max_links > 0 and len(links_to_check) >= self.config.max_links:
                        break
                if self.config.max_links > 0 and len(links_to_check) >= self.config.max_links:
                    break

            total_to_check = len(links_to_check)
            checked_count = 0

            with ThreadPoolExecutor(max_workers=self.config.parallel_workers) as executor:
                future_to_link = {
                    executor.submit(self.link_checker.check_link_with_retry, link): (link, source_url, context)
                    for link, source_url, context in links_to_check
                }

                for future in as_completed(future_to_link):
                    link, source_url, context = future_to_link[future]
                    checked_count += 1

                    if checked_count % 20 == 0 or checked_count == total_to_check:
                        self.logger.info(f"✓ Checked {checked_count}/{total_to_check} links...")

                    try:
                        status, error = future.result()

                        if status == 0 or status >= 400:
                            link_data = {
                                'url': link,
                                'source': source_url,
                                'status': status,
                                'error': error,
                                'site': doc_url,
                                'context': context
                            }

                            # Classify as truly broken or false positive
                            if self.link_checker.is_truly_broken(link, status, error):
                                all_broken.append(link_data)
                                self.logger.warning(f"❌ BROKEN: {link} ({error})")
                            else:
                                all_false_positives.append(link_data)
                                self.logger.info(f"⚠️  FALSE POSITIVE: {link} ({error})")

                    except Exception as e:
                        self.logger.error(f"Error checking {link}: {e}")

        # Clean up session connections to free file descriptors
        self.link_checker.session.close()
        self.logger.info("✓ Closed HTTP session to free resources")

        return all_broken, all_false_positives

    def run_check(self):
        """Run enhanced check with categorization."""
        # Increase system limits for file descriptors to handle many connections
        try:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
            new_limit = min(hard, 65536)  # Increase to max allowed
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_limit, hard))
            self.logger.info(f"Increased file descriptor limit from {soft} to {new_limit}")
        except Exception as e:
            self.logger.warning(f"Could not increase file descriptor limit: {e}")

        self.logger.info("="*70)
        self.logger.info("🚀 Enhanced Broken Link Checker with Categories")
        self.logger.info("="*70)
        self.logger.info(f"Max retries per link: {self.config.max_retries}")
        self.logger.info(f"Retry backoff factor: {self.config.retry_backoff}")
        self.logger.info("="*70)

        start_time = time.time()

        truly_broken, false_positives = self.check_all_sites()

        elapsed = time.time() - start_time
        total_checked = len(self.link_checker.checked_urls)

        self.logger.info("="*70)
        self.logger.info("✅ Check Complete")
        self.logger.info("="*70)
        self.logger.info(f"Total links checked: {total_checked}")
        self.logger.info(f"Truly broken links: {len(truly_broken)}")
        self.logger.info(f"False positives (403, local URLs, etc.): {len(false_positives)}")
        self.logger.info(f"Time elapsed: {elapsed:.1f} seconds")
        self.logger.info("="*70)

        # Strip any excluded-pattern URLs from broken list before reporting
        if self.config.exclude_patterns:
            import re as _re
            truly_broken = [
                lnk for lnk in truly_broken
                if not any(_re.search(pat, lnk['url']) for pat in self.config.exclude_patterns)
            ]

        # Generate categorized CSV and HTML reports
        if truly_broken:
            base_url = self.config.docs_urls[0] if self.config.docs_urls else ""
            csv_file = self.report_gen.generate_csv_with_categories(truly_broken, base_url)
            html_file = self.report_gen.generate_html_report(truly_broken, base_url)

            # Generate category summary
            by_category = self.report_gen.generate_category_summary(truly_broken, base_url)

            self.logger.info("\n📊 Broken Links by Category:")
            for category in sorted(by_category.keys()):
                count = len(by_category[category])
                display_cat = CategoryExtractor.get_display_category(category)
                self.logger.info(f"  {display_cat}: {count} broken links")

            # Upload to GitHub Pages
            public_url = self.github_uploader.upload_report(html_file, csv_file)

            # Send Slack notification with public URL
            if public_url:
                self.slack_notifier.send_report_notification(truly_broken, public_url, by_category, total_checked)

            return csv_file, html_file, by_category, public_url

        return None, None, {}, None


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    logger = setup_logging()
    config = Config()

    if not config.validate():
        sys.exit(1)

    monitor = EnhancedBrokenLinkMonitor(config, logger)
    csv_file, html_file, by_category, public_url = monitor.run_check()

    if csv_file:
        print(f"\n✅ CSV report: {csv_file}")
        print(f"✅ HTML report: {html_file}")
        if public_url:
            print(f"🌐 Public URL: {public_url}")
        print(f"\n📁 Categories found: {len(by_category)}")


if __name__ == '__main__':
    main()
