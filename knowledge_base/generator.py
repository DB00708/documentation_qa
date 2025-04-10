import os
from utils import logger
from crawler import URLExtractor
from utils.helper import clean_url
from crawler.crawler import ParallelCrawler, DocumentBuilder


class KnowledgeBaseGenerator:
    """
    Class for generating a knowledge base from documentation URLs.
    """

    def __init__(self, output_dir: str = "./docs_content", max_depth: int = 3, concurrency: int = 3):
        """
        Initialize knowledge base generator.

        Args:
            output_dir: Directory to save markdown files
            max_depth: Maximum crawl depth
            concurrency: Maximum number of concurrent crawlers
        """
        self.output_dir = output_dir
        self.max_depth = max_depth
        self.concurrency = concurrency
        self.url_extractor = URLExtractor(max_depth=max_depth, concurrency=concurrency)
        self.crawler = ParallelCrawler(max_processes=self.concurrency)
        self.document_builder = DocumentBuilder()

    async def generate(self, doc_url: str) -> str:
        """
        Generate a knowledge base from a documentation URL.

        Args:
            doc_url: Base documentation URL

        Returns:
            Path to consolidated markdown file
        """
        # Step 1: Extract doc URLs
        logger.info(f"Extracting documentation URLs from {doc_url} with depth {self.max_depth}...")
        doc_urls = await self.url_extractor.extract_doc_urls(doc_url)
        logger.info(f"Found {len(doc_urls)} documentation URLs")

        # Step 2: Crawl URLs and generate markdown
        logger.info(f"Crawling {len(doc_urls)} URLs with concurrency {self.concurrency}...")

        results = self.crawler.crawl(doc_urls)
        doc_name = clean_url(doc_url)
        
        knowledge_base_path = os.path.join(self.output_dir, f"{doc_name}_docs.txt")
        chunks_file_path = os.path.join(self.output_dir, f"{doc_name}_chunks.json")

        self.document_builder.create_combined_document(results, knowledge_base_path)
        self.document_builder.create_chunks(results, output_file=chunks_file_path)

        # Step 3: Consolidate markdown files
        successful_files = [r for r in results if r["success"]]
        logger.info(f"Successfully processed {len(successful_files)}/{len(doc_urls)} URLs")

        return knowledge_base_path
