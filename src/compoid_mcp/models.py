"""Pydantic models for Compoid API responses.

Note: These models are defined for type safety and documentation purposes.
The current implementation uses dictionaries for flexibility, but these models
can be used for validation and IDE support.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Contributor(BaseModel):
    """Contributor information for a record."""
    name: Optional[str] = None
    affiliation: Optional[List[Dict[str, Any]]] = None
    role: Optional[Dict[str, Any]] = None


class Subject(BaseModel):
    """Subject/topic information."""
    subject: Optional[str] = None
    scheme: Optional[str] = None


class Description(BaseModel):
    """Description field."""
    type: Optional[str] = None
    description: Optional[str] = None
    lang: Optional[str] = None


class RelatedIdentifier(BaseModel):
    """Related identifier/reference."""
    identifier: Optional[str] = None
    scheme: Optional[str] = None


class FileMetadata(BaseModel):
    """File metadata."""
    id: Optional[str] = None
    key: Optional[str] = None
    size: Optional[int] = None
    type: Optional[str] = None
    filename: Optional[str] = None


class FilesInfo(BaseModel):
    """Files information for a record."""
    count: Optional[int] = None
    default_preview: Optional[str] = None
    entries: List[FileMetadata] = Field(default_factory=list)


class RecordMetadata(BaseModel):
    """Metadata for a Compoid record."""
    title: Optional[str] = None
    description: Optional[str] = None
    creators: List[Contributor] = Field(default_factory=list)
    contributors: List[Contributor] = Field(default_factory=list)
    subjects: List[Subject] = Field(default_factory=list)
    related_identifiers: List[RelatedIdentifier] = Field(default_factory=list)
    additional_descriptions: List[Description] = Field(default_factory=list)
    additional_titles: List[Description] = Field(default_factory=list)
    publication_date: Optional[str] = None
    resource_type: Optional[Dict[str, Any]] = None
    language: Optional[str] = None
    language_name: Optional[str] = None
    website: Optional[str] = None
    references: Optional[List[Dict[str, Any]]] = None


class RecordLinks(BaseModel):
    """Links for a record."""
    self: Optional[str] = None
    self_html: Optional[str] = None
    self_csv: Optional[str] = None
    self_doi: Optional[str] = None
    preview: Optional[str] = None
    files: Optional[str] = None
    versions: Optional[str] = None
    publish: Optional[str] = None


class Record(BaseModel):
    """Compoid record model (InvenioRDM structure)."""
    id: str
    metadata: Optional[RecordMetadata] = None
    files: Optional[FilesInfo] = None
    links: Optional[RecordLinks] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    published: Optional[str] = None
    version: Optional[str] = None
    pids: Optional[Dict[str, Any]] = None
    access: Optional[Dict[str, Any]] = None
    custom_fields: Optional[Dict[str, Any]] = None


class CommunityMetadata(BaseModel):
    """Metadata for a Compoid community."""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[Dict[str, Any]] = None
    website: Optional[str] = None
    curation_policy: Optional[str] = None


class CommunityLinks(BaseModel):
    """Links for a community."""
    self: Optional[str] = None
    self_html: Optional[str] = None
    records: Optional[str] = None
    avatar: Optional[str] = None
    logo: Optional[str] = None


class Community(BaseModel):
    """Compoid community model."""
    id: str
    slug: Optional[str] = None
    metadata: Optional[CommunityMetadata] = None
    links: Optional[CommunityLinks] = None
    access: Optional[Dict[str, Any]] = None
    created: Optional[str] = None
    updated: Optional[str] = None
    is_published: Optional[bool] = None


class SearchHit(BaseModel):
    """Single search result hit."""
    id: str
    metadata: Optional[Dict[str, Any]] = None
    links: Optional[Dict[str, Any]] = None
    created: Optional[str] = None
    updated: Optional[str] = None


class SearchMeta(BaseModel):
    """Search metadata."""
    total: int
    count: int
    start: int
    page: int
    pages: int


class SearchResponse(BaseModel):
    """Search response model."""
    hits: Dict[str, Any]
    took: Optional[float] = None
