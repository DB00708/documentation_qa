import asyncio
from typing import List
from utils import logger
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright


class URLExtractor:
    """
    Class for extracting documentation URLs from websites.
    """

    def __init__(self, max_depth: int = 3, concurrency: int = 3):
        """
        Initialize URL extractor.

        Args:
            max_depth: Maximum crawl depth
            concurrency: Maximum number of concurrent crawlers
        """
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.doc_urls = set()  # URLs containing 'doc' or 'docs'
        self.visited_urls = set()  # URLs that have been visited
        self.queued_urls = set()  # URLs that have been added to the queue
        self.queue = asyncio.Queue()

    async def extract_doc_urls(self, base_url: str) -> List[str]:
        """
        Extract all URLs with 'doc' or 'docs' in them up to the specified depth using concurrent crawling.

        Args:
            base_url: The base URL to start crawling from

        Returns:
            List of URLs containing 'doc' or 'docs'
        """
        # Reset state for a new extraction
        self.doc_urls = set()
        self.visited_urls = set()
        self.queued_urls = set()
        self.queue = asyncio.Queue()

        # Start with the base URL at depth 1
        await self.queue.put((base_url, 1))
        self.queued_urls.add(base_url)

        # Start concurrent workers
        workers = []
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker())
            workers.append(task)

        # Wait for all URLs to be processed
        await self.queue.join()

        # Cancel worker tasks
        for task in workers:
            task.cancel()

        # Wait for all worker tasks to be cancelled
        await asyncio.gather(*workers, return_exceptions=True)

        return list(self.doc_urls)

    async def _worker(self) -> None:
        """
        Worker task for processing URLs from the queue.
        """
        while True:
            try:
                # Get a URL and its depth from the queue
                url, depth = await self.queue.get()

                if url in self.visited_urls:
                    self.queue.task_done()
                    continue

                logger.info(f"Crawling URL (depth {depth}/{self.max_depth}): {url}")
                self.visited_urls.add(url)

                try:
                    # Process the page and extract links
                    links = await self._fetch_links(url)

                    # Process each link
                    for link in links:
                        # Skip if the link is None or empty
                        if not link:
                            continue

                        # Normalize link
                        parsed = urlparse(link)
                        if not parsed.netloc:
                            link = urljoin(url, link)

                        # Add to doc_urls if it contains 'doc' or 'docs'
                        if 'doc' in link.lower():
                            self.doc_urls.add(link)

                        # Add links to the queue for the next depth
                        if depth < self.max_depth and link not in self.visited_urls and link not in self.queued_urls:
                            await self.queue.put((link, depth + 1))
                            self.queued_urls.add(link)  # Mark as queued to avoid duplicates

                except Exception as e:
                    logger.error(f"Error processing {url}: {e}")

                finally:
                    # Mark the task as done
                    self.queue.task_done()

            except Exception as e:
                logger.error(f"Worker error: {e}")
                self.queue.task_done()

    async def _fetch_links(self, url: str) -> List[str]:
        """
        Fetch all links from a URL.

        Args:
            url: URL to fetch links from

        Returns:
            List of links
        """
        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # Set timeout and user agent
                page.set_default_timeout(30000)
                await context.set_extra_http_headers({"User-Agent": "DocBot/1.0 Documentation Crawler"})

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # Extract all links on the page
                links = await page.evaluate("""
                    () => {
                        return Array.from(document.querySelectorAll('a'))
                            .map(a => a.href)
                            .filter(href => href && !href.startsWith('javascript:'));
                    }
                """)

                await browser.close()

                return links
        except Exception as e:
            logger.error(f"Error fetching links from {url}: {e}")
            return []
