"""
DocBot: A document-based chatbot with vector storage and semantic retrieval.
"""
import os
import pinecone
from rag.constants import *
from typing import Dict, List
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from langchain_pinecone import PineconeVectorStore
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder


class PreChunkedLoader:
    """Loader for pre-chunked JSON data."""

    def load_from_json(self, json_data) -> List[Document]:
        """Load pre-chunked documents from JSON data."""
        return [
            Document(
                page_content=chunk.get("content", ""),
                metadata={
                    "url": chunk.get("url", ""),
                    "chunk_length": chunk.get("chunk_length", 0)
                }
            )
            for chunk in json_data
        ]


class VectorStoreManager:
    """Manages interactions with the Pinecone vector database."""

    def __init__(self, index_name: str = None, api_key: str = None):
        self.embeddings = OpenAIEmbeddings()
        self.index_name = index_name or os.environ.get("PINECONE_INDEX", "docbot")
        self.api_key = api_key or os.environ.get("PINECONE_API_KEY")
        self.pc = pinecone.init(api_key=self.api_key)
        self.vector_store = self._initialize_vector_store()

    def _initialize_vector_store(self) -> PineconeVectorStore:
        """Initialize or connect to Pinecone vector store."""
        if self.index_name not in self.pc.list_indexes().names():
            self.pc.create_index(
                name=self.index_name,
                dimension=OPENAI_EMBEDDING_DIM,
                metric="cosine",
                spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
            )
            print(f"Created new Pinecone index: {self.index_name}")

        index = self.pc.Index(self.index_name)
        return PineconeVectorStore(index=index, embedding=self.embeddings)

    def add_documents(self, documents: List[Document], namespace: str = None) -> Dict:
        """Add documents to the vector store."""
        try:
            self.vector_store.add_documents(documents, namespace=namespace)
            return {
                "status": "success",
                "message": f"Added {len(documents)} documents to Pinecone",
                "count": len(documents)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error adding documents: {str(e)}"
            }

    def get_retriever(self, search_kwargs: Dict = None, **kwargs):
        """Get a retriever from the vector store with custom parameters."""
        default_search_kwargs = {"k": DEFAULT_RETRIEVAL_K}
        if search_kwargs:
            default_search_kwargs.update(search_kwargs)

        return self.vector_store.as_retriever(
            search_kwargs=default_search_kwargs,
            **kwargs
        )


class Reranker:
    """Cross-encoder reranker to improve retrieval quality."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(self, query: str, documents: List[Document], top_n: int = DEFAULT_TOP_K) -> List[Document]:
        """Rerank documents based on relevance to the query."""
        if not documents:
            return []

        # Prepare document pairs for scoring
        document_pairs = [(query, doc.page_content) for doc in documents]

        # Get scores and sort by relevance
        scores = self.model.predict(document_pairs)
        scored_documents = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

        # Return top_n documents
        return [doc for doc, _ in scored_documents[:top_n]]


class QueryProcessor:
    """Processes and enhances user queries for better retrieval."""

    def __init__(self, llm=None):
        self.llm = llm or ChatOpenAI(temperature=0)
        self._setup_chains()

    def _setup_chains(self):
        """Set up language chains for query processing."""
        reformulation_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_ENHANCEMENT_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{query}")
        ])

        self.query_reformulation_chain = (
                reformulation_prompt | self.llm | StrOutputParser()
        )

    def process_query(self, query: str, chat_history=None) -> str:
        """Process and enhance a user query."""
        return self.query_reformulation_chain.invoke({
            "query": query,
            "chat_history": chat_history or []
        })


class AdvancedRetriever:
    """Advanced retrieval mechanism with reranking and filtering."""

    def __init__(self, vector_store_manager: VectorStoreManager, reranker: Reranker, query_processor: QueryProcessor):
        self.vector_store_manager = vector_store_manager
        self.reranker = reranker
        self.query_processor = query_processor
        self.base_retriever = vector_store_manager.get_retriever()

    def retrieve(self, query: str, chat_history=None, filter_metadata: Dict = None, top_k: int = DEFAULT_TOP_K) -> List[
        Document]:
        """Retrieve relevant documents using enhanced query and reranking."""
        # Process the query
        enhanced_query = self.query_processor.process_query(query, chat_history)

        # Create a retriever with metadata filters if provided
        retriever = self.base_retriever
        if filter_metadata:
            retriever = self.vector_store_manager.get_retriever(
                search_kwargs={"filter": filter_metadata, "k": DEFAULT_RETRIEVAL_K}
            )

        # Retrieve and rerank documents
        raw_docs = retriever.invoke(enhanced_query)
        return self.reranker.rerank(query, raw_docs, top_n=top_k)


class ResponseGenerator:
    """Generates high-quality responses based on retrieved documents."""

    def __init__(self, llm=None):
        self.llm = llm or ChatOpenAI(model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE)
        self._setup_response_chain()

    def _setup_response_chain(self):
        """Set up the response generation chain."""
        response_prompt = ChatPromptTemplate.from_messages([
            ("system", RESPONSE_GENERATION_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{query}")
        ])
        self.response_chain = response_prompt | self.llm

    def _format_context(self, documents: List[Document]) -> str:
        """Format documents into a context string."""
        context_texts = []
        for i, doc in enumerate(documents, 1):
            source_url = doc.metadata.get("url", "Unknown source")
            content = doc.page_content.strip()
            context_texts.append(f"Document #{i} from {source_url}:\n{content}\n")

        return "\n" + "-" * 40 + "\n".join(context_texts) + "-" * 40 + "\n"

    def generate_response(self, query: str, documents: List[Document], chat_history=None) -> str:
        """Generate a response based on retrieved documents."""
        context = self._format_context(documents)
        response = self.response_chain.invoke({
            "query": query,
            "context": context,
            "chat_history": chat_history or []
        })
        return response


class DocBot:
    """Main class orchestrating the document-based chatbot."""

    def __init__(self, index_name: str = None, openai_api_key: str = None, pinecone_api_key: str = None):
        # Set environment variables from parameters if provided
        self._set_env_vars(openai_api_key, pinecone_api_key)

        # Create shared LLM instance
        self.llm = ChatOpenAI(model=DEFAULT_MODEL, temperature=DEFAULT_TEMPERATURE)

        # Initialize components
        self.vector_store_manager = VectorStoreManager(index_name=index_name, api_key=pinecone_api_key)
        self.chunk_loader = PreChunkedLoader()
        self.query_processor = QueryProcessor(self.llm)
        self.reranker = Reranker()
        self.retriever = AdvancedRetriever(
            self.vector_store_manager,
            self.reranker,
            self.query_processor
        )
        self.response_generator = ResponseGenerator(self.llm)

    def _set_env_vars(self, openai_api_key: str = None, pinecone_api_key: str = None):
        """Set environment variables if provided."""
        if openai_api_key:
            os.environ["OPENAI_API_KEY"] = openai_api_key
        if pinecone_api_key:
            os.environ["PINECONE_API_KEY"] = pinecone_api_key

    def load_json_data(self, json_data, namespace: str = None) -> Dict:
        """Load pre-chunked documentation from JSON data."""
        try:
            documents = self.chunk_loader.load_from_json(json_data)
            result = self.vector_store_manager.add_documents(documents, namespace)

            result["document_count"] = len(documents)
            return result
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error loading documentation: {str(e)}"
            }

    def query(self, query: str, chat_history=None, metadata_filter: Dict = None) -> str:
        """Process a user query and return a response."""
        try:
            # Retrieve relevant documents
            retrieved_docs = self.retriever.retrieve(
                query=query,
                chat_history=chat_history,
                filter_metadata=metadata_filter,
                top_k=DEFAULT_TOP_K
            )

            # Generate response
            response = self.response_generator.generate_response(
                query=query,
                documents=retrieved_docs,
                chat_history=chat_history
            )

            return response.content
        except Exception as e:
            return f"I encountered an error while processing your question: {str(e)}"


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    # Create and use DocBot
    docbot = DocBot()
    response = docbot.query("What is async webcrawler?")
    print(response)
