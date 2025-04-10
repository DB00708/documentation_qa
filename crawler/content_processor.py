import os
from utils import logger
from urllib.parse import urlparse
from playwright.async_api import Page


class ContentProcessor:
    """
    Class for processing web pages and extracting content as markdown.
    """

    def __init__(self, output_dir: str = "./docs_content"):
        """
        Initialize content processor.

        Args:
            output_dir: Directory to save markdown files
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    async def process_page(self, page: Page, url: str) -> tuple[str, str]:
        """
        Process a page and extract content as markdown.

        Args:
            page: Playwright page object
            url: URL of the page

        Returns:
            Tuple of (markdown_content, file_path)
        """
        # Get page title
        title = await page.title()

        # Extract main content
        content = await self._extract_main_content(page)

        # Format as markdown
        markdown = self._format_as_markdown(title, content, url)

        # Save to file
        file_path = self._save_to_file(markdown, url)

        return markdown, file_path

    async def _extract_main_content(self, page: Page) -> str:
        """
        Extract main content from a page.

        Args:
            page: Playwright page object

        Returns:
            Extracted content as text
        """
        # Try to find the main content area using common selectors
        content = await page.evaluate("""
            () => {
                // Try to find the main content area
                const selectors = [
                    'main',
                    'article',
                    '.content',
                    '.documentation',
                    '.docs',
                    '#content',
                    '#main',
                    '.main-content',
                    '.markdown-section',
                    '.markdown-body'
                ];

                for (const selector of selectors) {
                    const element = document.querySelector(selector);
                    if (element) {
                        return element.innerText;
                    }
                }

                // Try to find heading elements and their following content
                const headings = document.querySelectorAll('h1, h2, h3');
                if (headings.length > 0) {
                    let content = '';
                    headings.forEach(heading => {
                        content += heading.innerText + '\\n\\n';
                        let sibling = heading.nextElementSibling;
                        while (sibling && !['H1', 'H2', 'H3'].includes(sibling.tagName)) {
                            content += sibling.innerText + '\\n\\n';
                            sibling = sibling.nextElementSibling;
                        }
                    });
                    if (content.length > 100) {  // Only use if we got meaningful content
                        return content;
                    }
                }

                // Fallback to body
                return document.body.innerText;
            }
        """)

        return content

    def _format_as_markdown(self, title: str, content: str, url: str) -> str:
        """
        Format extracted content as markdown.

        Args:
            title: Page title
            content: Page content
            url: Page URL

        Returns:
            Formatted markdown
        """
        # Add URL as a reference
        markdown = f"# {title}\n\n"
        markdown += f"Source: [{url}]({url})\n\n"
        markdown += content

        return markdown

    def _save_to_file(self, markdown: str, url: str) -> str:
        """
        Save markdown content to a file.

        Args:
            markdown: Markdown content
            url: URL of the page

        Returns:
            File path
        """
        # Create filename based on URL
        domain = urlparse(url).netloc
        path = urlparse(url).path.replace('/', '_')
        if not path:
            path = '_index'
        filename = f"{domain}{path}.md"
        if len(filename) > 100:
            filename = filename[:100]  # Limit filename length

        file_path = os.path.join(self.output_dir, filename)

        # Save to file
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(markdown)

        logger.info(f"Saved markdown to {file_path}")

        return file_path
