"""
Services module for Sidekick AI.

Contains external service integrations:
- Mesh AI for LLM calls
- Embeddings for semantic search
"""

from services.mesh import MeshService
from services.embeddings import EmbeddingsService

__all__ = ["MeshService", "EmbeddingsService"]
