import json
import time
import asyncio
import multiprocessing
from utils.logger import logger
from crawl4ai import AsyncWebCrawler
from typing import List, Dict, Any, Optional


class SingleCrawler:
    """Class for crawling a single URL in its own process"""

    @staticmethod
    def crawl_process(url: str) -> Dict[str, Any]:
        """
        Function that runs in its own process to crawl a single URL

        Args:
            url: URL to crawl

        Returns:
            Dictionary with crawl results
        """
        process_name = multiprocessing.current_process().name
        logger.info(f"Process {process_name} starting crawl for {url}")
        start = time.time()

        # Run async code in this process
        result = asyncio.run(SingleCrawler.crawl_async(url))

        duration = time.time() - start
        logger.info(f"Process {process_name} finished crawling {url} in {duration:.2f} seconds")
        return result

    @staticmethod
    async def crawl_async(url: str) -> Dict[str, Any]:
        """
        Async function to crawl a URL using AsyncWebCrawler

        Args:
            url: URL to crawl

        Returns:
            Dictionary with the crawl results including content
        """
        try:
            async with AsyncWebCrawler(verbose=True) as crawler:
                result = await crawler.arun(url=url)

                # Extract only the text content we need to avoid serialization issues
                markdown = str(result.markdown) if hasattr(result, "markdown") else ""
                extracted_content = str(result.extracted_content) if hasattr(result, "extracted_content") else ""
                cleaned_html = str(result.cleaned_html) if hasattr(result, "cleaned_html") else ""

                # Return a simple dictionary that can be easily pickled
                return {
                    "url": url,
                    "success": True,
                    "markdown": markdown,
                    "cleaned_html": cleaned_html,
                    "extracted_content": extracted_content
                }
        except Exception as e:
            logger.error(f"Error crawling {url}: {e}")
            return {"url": url, "success": False, "error": str(e)}


class ParallelCrawler:
    """Class for crawling multiple URLs in parallel"""

    def __init__(self, max_processes: Optional[int] = None):
        """
        Initialize the parallel crawler

        Args:
            max_processes: Maximum number of parallel processes (defaults to CPU count)
        """
        self.max_processes = max_processes

    def crawl(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Crawl multiple URLs in parallel and return the results

        Args:
            urls: List of URLs to crawl

        Returns:
            List of results with content from each URL
        """
        if not urls:
            logger.warning("No URLs provided for crawling")
            return []

        # Determine max processes (default to CPU count if not specified)
        max_processes = self.max_processes
        if max_processes is None:
            max_processes = multiprocessing.cpu_count()

        # Cap max_processes to number of URLs
        max_processes = min(max_processes, len(urls))

        logger.info(f"Starting parallel crawl with {max_processes} processes for {len(urls)} URLs")
        start_time = time.time()

        # Use multiprocessing pool to crawl URLs in parallel
        with multiprocessing.Pool(processes=max_processes) as pool:
            results = pool.map(SingleCrawler.crawl_process, urls)

        end_time = time.time()
        logger.info(f"Parallel crawling completed in {end_time - start_time:.2f} seconds")

        # Log success/failure statistics
        success_count = sum(1 for r in results if r.get("success", False))
        logger.info(f"Successfully crawled {success_count}/{len(urls)} URLs")

        return results


class DocumentBuilder:
    """Class for building documents from crawled content"""

    @staticmethod
    def create_combined_document(results: List[Dict[str, Any]],
                                 output_file: str = "crawled_content.txt") -> str:
        """
        Combine multiple crawl results into a single text document

        Args:
            results: List of crawl results
            output_file: Path to save the combined content

        Returns:
            The combined content as a string
        """
        content_sections = []
        total_content_length = 0

        for result in results:
            if result.get("success") and result.get("markdown"):
                markdown = result.get("markdown", "")
                content_sections.append(f"# Content from {result['url']}\n\n{markdown}")
                total_content_length += len(markdown)

        combined_content = "\n\n---\n\n".join(content_sections)

        try:
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(combined_content)
            logger.info(f"Combined content ({total_content_length} characters) saved to '{output_file}'")
        except Exception as e:
            logger.error(f"Failed to write output file '{output_file}': {e}")

        return combined_content

    @staticmethod
    def create_chunks(results: List[Dict[str, Any]],
                      chunk_size: int = 1000,
                      chunk_overlap: int = 200,
                      output_file: str = "content_chunks.json") -> List[Dict[str, Any]]:
        """
        Create chunks from crawled content and save to a JSON file.

        Args:
            results: List of crawl results
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks
            output_file: Path to save the JSON file containing chunks

        Returns:
            List of chunks, where each chunk is a dictionary with 'content' and 'url' keys
        """
        chunks = []

        for result in results:
            if not result.get("success") or not result.get("markdown"):
                continue

            url = result.get("url", "")
            content = result.get("markdown", "")

            # Skip empty content
            if not content.strip():
                continue

            # Create chunks from the content
            content_chunks = DocumentBuilder._split_text(content, chunk_size, chunk_overlap)

            # Add URL to each chunk
            for chunk_content in content_chunks:
                chunk = {
                    "content": chunk_content,
                    "url": url,
                    "chunk_length": len(chunk_content)
                }
                chunks.append(chunk)

        # Save chunks to JSON file
        try:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(chunks, f, ensure_ascii=False, indent=2)
            logger.info(f"Created {len(chunks)} chunks and saved to '{output_file}'")
        except Exception as e:
            logger.error(f"Failed to write chunks to '{output_file}': {e}")

        return chunks

    @staticmethod
    def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """
        Split text into chunks of approximately chunk_size characters with overlap.

        Args:
            text: Text to split
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of characters to overlap between chunks

        Returns:
            List of text chunks
        """
        # Handle edge cases
        if not text:
            return []

        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            # Find the end position for this chunk
            end = start + chunk_size

            # Adjust end to not cut in the middle of a paragraph if possible
            if end < len(text):
                # Try to find paragraph break
                paragraph_break = text.find("\n\n", end - chunk_size // 2, end + chunk_size // 2)
                if paragraph_break != -1:
                    end = paragraph_break + 2  # Include the newline characters
                else:
                    # Try to find sentence break (period followed by space)
                    sentence_break = text.find(". ", end - chunk_size // 4, end + chunk_size // 4)
                    if sentence_break != -1:
                        end = sentence_break + 2  # Include the period and space
                    else:
                        # If no natural break found, try to break at a space
                        if end < len(text):
                            space = text.rfind(" ", end - chunk_size // 8, end)
                            if space != -1:
                                end = space + 1  # Include the space

            # Ensure we don't go past the end of the text
            end = min(end, len(text))

            # Add this chunk
            chunks.append(text[start:end])

            # Move to next chunk, accounting for overlap
            next_start = end - chunk_overlap

            # Ensure we're making progress to avoid infinite loop
            if next_start <= start:
                next_start = start + 1  # Force at least one character of progress

            # Update the start position for next iteration
            start = next_start

            # Break if we've reached the end of the text
            if start >= len(text):
                break

        return chunks
