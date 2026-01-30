"""
ChromaDB client for semantic search functionality.

This module provides persistent vector database storage and embedding functions
for semantic search over Zotero libraries.
"""

from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import sys
from typing import Any

import chromadb
from chromadb import EmbeddingFunction
from chromadb.config import Settings
import chromadb.utils.embedding_functions

logger = logging.getLogger(__name__)


@contextmanager
def suppress_stdout():
    """Context manager to suppress stdout temporarily."""
    with open(os.devnull, "w") as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


class ChromaClient:
    """ChromaDB client for Zotero semantic search."""

    def __init__(
        self,
        collection_name: str = "zotero_library",
        persist_directory: str | None = None,
        embedding_model: str = "default",
        embedding_config: dict[str, Any] | None = None,
    ):
        """
        Initialize ChromaDB client.

        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Directory to persist the database
            embedding_model: Model to use for embeddings (only 'default' supported)
            embedding_config: Configuration for the embedding model (not used for default)
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self.embedding_config = embedding_config or {}

        # Set up persistent directory
        if persist_directory is None:
            # Use user's config directory by default
            config_dir = Path.home() / ".config" / "zotero-mcp"
            config_dir.mkdir(parents=True, exist_ok=True)
            persist_directory = str(config_dir / "chroma_db")

        self.persist_directory = persist_directory

        # Initialize ChromaDB client with stdout suppression
        with suppress_stdout():
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )

            # Set up embedding function
            self.embedding_function = self._create_embedding_function()

            # Get or create collection with embedding function handling
            try:
                # Try to get existing collection first
                self.collection = self.client.get_collection(name=self.collection_name)

                # Check if embedding functions are compatible
                existing_ef = getattr(self.collection, "_embedding_function", None)
                if existing_ef is not None:
                    existing_name = getattr(existing_ef, "name", lambda: "default")()
                    new_name = getattr(
                        self.embedding_function, "name", lambda: "default"
                    )()

                    if existing_name != new_name:
                        # Log to stderr instead of letting ChromaDB print to stdout
                        sys.stderr.write(
                            f"ChromaDB: Collection exists with different embedding function: {existing_name} vs {new_name}\n"
                        )
                        # Use the existing collection's embedding function to avoid conflicts
                        self.embedding_function = existing_ef

            except Exception:
                # Collection doesn't exist, create it
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=self.embedding_function,
                )

    def _create_embedding_function(self) -> EmbeddingFunction:
        """Create the appropriate embedding function based on configuration."""
        # Use ChromaDB's default embedding function (ONNX-based, lightweight)
        # Note: This is the all-MiniLM-L6-v2 model that runs locally
        return chromadb.utils.embedding_functions.DefaultEmbeddingFunction()

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, str | int | float | None]],
        ids: list[str],
    ) -> None:
        """
        Add documents to the collection.

        Args:
            documents: List of document texts to embed
            metadatas: List of metadata dictionaries for each document
            ids: List of unique IDs for each document
        """
        try:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)  # type: ignore[arg-type]
            logger.info(f"Added {len(documents)} documents to ChromaDB collection")
        except Exception as e:
            logger.error(f"Error adding documents to ChromaDB: {e}")
            raise

    def upsert_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, str | int | float | None]],
        ids: list[str],
    ) -> None:
        """
        Upsert (update or insert) documents to the collection.

        Args:
            documents: List of document texts to embed
            metadatas: List of metadata dictionaries for each document
            ids: List of unique IDs for each document
        """
        try:
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)  # type: ignore[arg-type]
            logger.info(f"Upserted {len(documents)} documents to ChromaDB collection")
        except Exception as e:
            logger.error(f"Error upserting documents to ChromaDB: {e}")
            raise

    def search(
        self,
        query_texts: list[str],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Search for similar documents.

        Args:
            query_texts: List of query texts
            n_results: Number of results to return
            where: Metadata filter conditions
            where_document: Document content filter conditions

        Returns:
            Search results from ChromaDB
        """
        try:
            results = self.collection.query(
                query_texts=query_texts,
                n_results=n_results,
                where=where,
                where_document=where_document,  # type: ignore[arg-type]
            )
            logger.info(
                f"Semantic search returned {len(results.get('ids', [[]])[0])} results"
            )
            return dict(results)  # type: ignore[arg-type]
        except Exception as e:
            logger.error(f"Error performing semantic search: {e}")
            raise

    def delete_documents(self, ids: list[str]) -> None:
        """
        Delete documents from the collection.

        Args:
            ids: List of document IDs to delete
        """
        try:
            self.collection.delete(ids=ids)
            logger.info(f"Deleted {len(ids)} documents from ChromaDB collection")
        except Exception as e:
            logger.error(f"Error deleting documents from ChromaDB: {e}")
            raise

    def get_collection_info(self) -> dict[str, Any]:
        """Get information about the collection."""
        try:
            count = self.collection.count()
            return {
                "name": self.collection_name,
                "count": count,
                "embedding_model": self.embedding_model,
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {
                "name": self.collection_name,
                "count": 0,
                "embedding_model": self.embedding_model,
                "persist_directory": self.persist_directory,
                "error": str(e),
            }

    def reset_collection(self) -> None:
        """Reset (clear) the collection."""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self.client.create_collection(
                name=self.collection_name, embedding_function=self.embedding_function
            )
            logger.info(f"Reset ChromaDB collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            raise

    def document_exists(self, doc_id: str) -> bool:
        """Check if a document exists in the collection."""
        try:
            result = self.collection.get(ids=[doc_id])
            return len(result["ids"]) > 0
        except Exception:
            return False

    def get_document_metadata(self, doc_id: str) -> dict[str, Any] | None:
        """
        Get metadata for a document if it exists.

        Args:
            doc_id: Document ID to look up

        Returns:
            Metadata dictionary if document exists, None otherwise
        """
        try:
            result = self.collection.get(ids=[doc_id], include=["metadatas"])
            if result["ids"] and result["metadatas"]:
                return dict(result["metadatas"][0])
            return None
        except Exception:
            return None


def create_chroma_client(config_path: str | None = None) -> ChromaClient:
    """
    Create a ChromaClient instance from configuration.

    Args:
        config_path: Path to configuration file

    Returns:
        Configured ChromaClient instance
    """
    # Default configuration
    config = {
        "collection_name": "zotero_library",
        "embedding_model": "default",
        "embedding_config": {},
    }

    # Load configuration from file if it exists
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path) as f:
                file_config = json.load(f)
                config.update(file_config.get("semantic_search", {}))
        except Exception as e:
            logger.warning(f"Error loading config from {config_path}: {e}")

    # Load configuration from environment variables
    env_embedding_model = os.getenv("ZOTERO_EMBEDDING_MODEL")
    if env_embedding_model:
        config["embedding_model"] = env_embedding_model

    return ChromaClient(
        collection_name=str(config["collection_name"]),
        embedding_model=str(config["embedding_model"]),
        embedding_config=config["embedding_config"]
        if isinstance(config["embedding_config"], dict)
        else {},
    )
