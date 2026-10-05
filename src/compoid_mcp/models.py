"""Pydantic models for Compoid API responses."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AuthorInfo(BaseModel):
    """Author information."""
    id: Optional[str] = None
    display_name: Optional[str] = None
    orcid: Optional[str] = None


class Institution(BaseModel):
    """Institution information."""
    id: Optional[str] = None
    display_name: Optional[str] = None
    ror: Optional[str] = None
    country_code: Optional[str] = None
    type: Optional[str] = None


class Authorship(BaseModel):
    """Authorship information for a work."""
    author_position: Optional[str] = None
    author: Optional[AuthorInfo] = None
    institutions: List[Institution] = Field(default_factory=list)
    countries: List[str] = Field(default_factory=list)
    is_corresponding: Optional[bool] = None


class Source(BaseModel):
    """Source/venue information."""
    id: Optional[str] = None
    display_name: Optional[str] = None
    issn_l: Optional[str] = None
    issn: Optional[List[str]] = None
    is_oa: Optional[bool] = None
    is_in_doaj: Optional[bool] = None
    type: Optional[str] = None
    host_organization: Optional[str] = None


class Location(BaseModel):
    """Location information for a work."""
    source: Optional[Source] = None
    landing_page_url: Optional[str] = None
    pdf_url: Optional[str] = None
    is_oa: Optional[bool] = None
    version: Optional[str] = None
    license: Optional[str] = None


class Topic(BaseModel):
    """Topic information."""
    id: Optional[str] = None
    display_name: Optional[str] = None
    score: Optional[float] = None
    subfield: Optional[Dict[str, Any]] = None
    field: Optional[Dict[str, Any]] = None
    domain: Optional[Dict[str, Any]] = None


class Work(BaseModel):
    """Compoid work (publication) model."""
    id: str
    doi: Optional[str] = None
    title: Optional[str] = None
    display_name: Optional[str] = None
    publication_year: Optional[int] = None
    publication_date: Optional[str] = None
    type: Optional[str] = None
    type_crossref: Optional[str] = None

    # Authors and affiliations
    authorships: List[Authorship] = Field(default_factory=list)

    # Publication venue
    primary_location: Optional[Location] = None
    best_oa_location: Optional[Location] = None
    locations: List[Location] = Field(default_factory=list)

    # Topics and concepts
    topics: List[Topic] = Field(default_factory=list)
    keywords: List[Dict[str, Any]] = Field(default_factory=list)

    # Citation metrics
    cited_by_count: Optional[int] = None
    citation_normalized_percentile: Optional[float] = None
    counts_by_year: List[Dict[str, Any]] = Field(default_factory=list)

    # References
    referenced_works: List[str] = Field(default_factory=list)
    cited_by_api_url: Optional[str] = None

    # Metadata
    is_retracted: Optional[bool] = None
    is_paratext: Optional[bool] = None
    abstract_inverted_index: Optional[Dict[str, List[int]]] = None
    language: Optional[str] = None

    # Timestamps
    created_date: Optional[str] = None
    updated_date: Optional[str] = None


class Author(BaseModel):
    """Compoid author model."""
    id: str
    orcid: Optional[str] = None
    display_name: Optional[str] = None
    display_name_alternatives: List[str] = Field(default_factory=list)

    # Metrics
    works_count: Optional[int] = None
    cited_by_count: Optional[int] = None
    i10_index: Optional[int] = None
    h_index: Optional[int] = None

    # Affiliations
    last_known_institution: Optional[Institution] = None
    affiliations: List[Dict[str, Any]] = Field(default_factory=list)

    # Research areas
    topics: List[Topic] = Field(default_factory=list)

    # Summary stats
    summary_stats: Optional[Dict[str, Any]] = None
    counts_by_year: List[Dict[str, Any]] = Field(default_factory=list)

    # URLs
    works_api_url: Optional[str] = None

    # Timestamps
    created_date: Optional[str] = None
    updated_date: Optional[str] = None


class InstitutionModel(BaseModel):
    """Compoid institution model."""
    id: str
    ror: Optional[str] = None
    display_name: Optional[str] = None
    display_name_alternatives: List[str] = Field(default_factory=list)
    display_name_acronyms: List[str] = Field(default_factory=list)

    # Location
    country_code: Optional[str] = None
    geo: Optional[Dict[str, Any]] = None

    # Classification
    type: Optional[str] = None
    homepage_url: Optional[str] = None
    image_url: Optional[str] = None
    image_thumbnail_url: Optional[str] = None

    # Metrics
    works_count: Optional[int] = None
    cited_by_count: Optional[int] = None

    # Associated entities
    associated_institutions: List[Dict[str, Any]] = Field(default_factory=list)

    # Summary stats
    summary_stats: Optional[Dict[str, Any]] = None
    counts_by_year: List[Dict[str, Any]] = Field(default_factory=list)

    # URLs
    works_api_url: Optional[str] = None

    # Timestamps
    created_date: Optional[str] = None
    updated_date: Optional[str] = None


class SourceModel(BaseModel):
    """Compoid source model."""
    id: str
    issn_l: Optional[str] = None
    issn: Optional[List[str]] = None
    display_name: Optional[str] = None

    # Publisher
    host_organization: Optional[str] = None
    host_organization_name: Optional[str] = None
    host_organization_lineage: List[str] = Field(default_factory=list)

    # Classification
    type: Optional[str] = None
    is_oa: Optional[bool] = None
    is_in_doaj: Optional[bool] = None

    # Metrics
    works_count: Optional[int] = None
    cited_by_count: Optional[int] = None
    h_index: Optional[int] = None
    i10_index: Optional[int] = None

    # Summary stats
    summary_stats: Optional[Dict[str, Any]] = None
    counts_by_year: List[Dict[str, Any]] = Field(default_factory=list)

    # URLs
    homepage_url: Optional[str] = None
    works_api_url: Optional[str] = None

    # Timestamps
    created_date: Optional[str] = None
    updated_date: Optional[str] = None


class TopicModel(BaseModel):
    """Compoid topic model."""
    id: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)

    # Hierarchy
    subfield: Optional[Dict[str, Any]] = None
    field: Optional[Dict[str, Any]] = None
    domain: Optional[Dict[str, Any]] = None

    # Metrics
    works_count: Optional[int] = None
    cited_by_count: Optional[int] = None

    # Summary stats
    summary_stats: Optional[Dict[str, Any]] = None
    counts_by_year: List[Dict[str, Any]] = Field(default_factory=list)

    # URLs
    works_api_url: Optional[str] = None

    # Timestamps
    created_date: Optional[str] = None
    updated_date: Optional[str] = None


class SearchResponse(BaseModel):
    """Generic search response model."""
    meta: Dict[str, Any]
    results: List[Dict[str, Any]]
    group_by: Optional[List[Dict[str, Any]]] = None
