import uuid
from datetime import datetime
from typing import Any, Literal, Optional, Self

from geoalchemy2 import Geometry, WKBElement  # noqa: TC002
from pydantic import (  # noqa: TC002
    ConfigDict,
    EmailStr,
    computed_field,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_extra_types.coordinate import Latitude, Longitude  # noqa: TC002
from sqlalchemy import Index, event
from sqlmodel import Column, Enum, Field, Relationship, SQLModel

from app.core.security import cipher_suite
from app.model_factories.factories import timestamp_field
from maress_types import (
    CeleryState,
    CoordinateExtractionMethod,
    CoordinateSourceType,
    InitialTaskState,
    PaperSections,
)


class ItemTagLink(SQLModel, table=True):
    item_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="item.id",
        primary_key=True,
    )
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


class CollectionBase(SQLModel):
    name: str = Field(max_length=64)


class Collection(CollectionBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="collections")
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: Optional["User"] = Relationship(back_populates="collections")


class CollectionCreate(CollectionBase):
    pass


# Properties to return via API, id is always required
class CollectionPublic(CollectionBase):
    id: uuid.UUID
    owner_id: uuid.UUID


class CollectionsPublic(SQLModel):
    data: list[CollectionPublic]
    count: int


class CreatorBase(SQLModel):
    creatorType: str 
    firstName: str | None = None
    lastName: str


class Creator(CreatorBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="creators")


class CreatorCreate(CreatorBase):
    pass


class CreatorPublic(CreatorBase):
    id: int
    item_id: uuid.UUID


class CreatorsPublic(SQLModel):
    data: list[CreatorPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    version: int | None = Field(default=None, ge=1)
    itemType: str = Field(min_length=1, max_length=64)
    abstractNote: str = Field(default="", min_length=0, max_length=8192)
    publicationTitle: str = Field(default="", min_length=0, max_length=255)
    volume: str | None = Field(default=None, max_length=32)
    issue: str | None = Field(default=None, max_length=32)
    pages: str | None = Field(default=None, max_length=32)
    date: str | None = Field(default=None, max_length=20)
    series: str = Field(default="", max_length=128)
    seriesTitle: str = Field(default="", max_length=128)
    seriesText: str = Field(default="", max_length=255)
    journalAbbreviation: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=8)
    doi: str | None = Field(default=None, max_length=128, alias="DOI")
    issn: str | None = Field(default=None, max_length=32, alias="ISSN")
    shortTitle: str = Field(default="", max_length=255)
    url: str = Field(default="", max_length=512)
    archive: str = Field(default="", max_length=128)
    archiveLocation: str = Field(default="", max_length=255)
    libraryCatalog: str | None = Field(default=None, max_length=255)
    callNumber: str = Field(default="", max_length=64)
    rights: str | None = Field(default=None, max_length=255)
    extra: str = Field(default="", max_length=255)
    dateAdded: datetime = timestamp_field()
    dateModified: datetime = timestamp_field(onupdate_now=True)
    attachment: str | None = Field(default=None, max_length=512)

    # get datetime of string if type of dateAdded or dateModified is str
    @classmethod
    def model_validate(cls, obj, **kwargs) -> SQLModel:  # noqa: ANN001, ANN003  # pyright: ignore[reportUnknownParameterType, reportMissingParameterType, reportImplicitOverride]
        """Convert dateAdded and dateModified from string to datetime."""
        if isinstance(obj, dict):
            if "dateAdded" in obj and isinstance(obj["dateAdded"], str):
                obj["dateAdded"] = datetime.fromisoformat(obj["dateAdded"])
            if "dateModified" in obj and isinstance(obj["dateModified"], str):
                obj["dateModified"] = datetime.fromisoformat(obj["dateModified"])
        return super().model_validate(obj, **kwargs)  # pyright: ignore[reportUnknownArgumentType]


# Properties to receive on item creation
class ItemCreate(ItemBase):
    key: str = Field(min_length=8, max_length=8, regex="^[A-Z0-9]{8}$", index=True)


class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)
    abstractNote: str | None = Field(default=None, min_length=0, max_length=8192)
    publicationTitle: str | None = Field(default=None, min_length=0, max_length=255)
    volume: str | None = Field(default=None, max_length=32)
    issue: str | None = Field(default=None, max_length=32)
    pages: str | None = Field(default=None, max_length=32)
    date: str | None = Field(default=None, max_length=20)
    series: str | None = Field(default=None, max_length=128)
    seriesTitle: str | None = Field(default=None, max_length=128)
    seriesText: str | None = Field(default=None, max_length=255)
    journalAbbreviation: str | None = Field(default=None, max_length=64)
    language: str | None = Field(default=None, max_length=8)
    doi: str | None = Field(default=None, max_length=128, alias="DOI")
    issn: str | None = Field(default=None, max_length=32, alias="ISSN")
    shortTitle: str | None = Field(default=None, max_length=255)
    url: str | None = Field(default=None, max_length=512)
    archive: str | None = Field(default=None, max_length=128)
    archiveLocation: str | None = Field(default=None, max_length=255)
    libraryCatalog: str | None = Field(default=None, max_length=255)
    callNumber: str | None = Field(default=None, max_length=64)
    rights: str | None = Field(default=None, max_length=255)
    extra: str | None = Field(default=None, max_length=255)
    attachment: str | None = Field(default=None, max_length=512)
    model_config = {  # pyright: ignore[reportUnannotatedClassAttribute, reportAssignmentType]
        "extra": "forbid",  # reject unapproved keys
        "populate_by_name": True,  # accept either alias or field name (e.g., DOI or doi)
    }


class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(
        foreign_key="user.id",
        nullable=False,
        ondelete="CASCADE",
    )
    owner: "User" = Relationship(back_populates="items")
    tags: list["Tag"] = Relationship(
        back_populates="items", link_model=ItemTagLink, sa_relationship_kwargs={"lazy": "selectin"}
    )
    # authors: list["Author"] = Relationship(
    #     back_populates="items",
    #     link_model=ItemAuthorLink,
    # )
    collections: list["Collection"] = Relationship(back_populates="item")
    accessDate: str | None = Field(default=None, max_length=32)  # ISO-format
    creators: list["Creator"] = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    relations: list["Relation"] = Relationship(back_populates="item")
    study_sites: list["StudySite"] | None = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    extraction_results: list["ExtractionResult"] | None = Relationship(
        back_populates="item",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    key: str = Field(min_length=8, max_length=8, regex="^[A-Z0-9]{8}$", index=True)


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    creators: list["CreatorPublic"] | None = None
    study_sites: list["StudySitePublic"] | None = None
    tags: list["Tag"] | None = None  # List of tag IDs

    @field_serializer("study_sites")
    def serialize_study_sites(self, study_sites: list["StudySite"] | None, _info):
        """Serialize study sites with location data."""
        if not study_sites:
            return None
        # Pydantic computed fields automatically handle lat/lon from location
        return [StudySitePublic.model_validate(site) for site in study_sites]

    @field_serializer("creators")
    def serialize_creators(self, creators: list["Creator"] | None, _info):
        """Serialize creators."""
        if not creators:
            return None
        return [CreatorPublic.model_validate(creator) for creator in creators]

    @field_serializer("tags")
    def serialize_tags(self, tags: list["Tag"] | None, _info):
        """Serialize tags as list of IDs."""
        if not tags:
            return None
        return [tag.id for tag in tags]


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


class ItemSummary(SQLModel):
    id: uuid.UUID
    title: str | None = None


class MapItemSummary(SQLModel):
    id: uuid.UUID
    title: str | None = None
    publicationTitle: str | None = None
    date: str | None = None
    study_site_count: int = 0


class MapItemsPublic(SQLModel):
    data: list[MapItemSummary]
    count: int


class GISSelection(SQLModel):
    """Feature selection descriptor used by GIS operations."""

    type: Literal["all", "ids", "bbox"] = "all"
    ids: list[uuid.UUID] | None = None
    bbox: list[float] | None = None

    @model_validator(mode="after")
    def validate_shape(self) -> Self:
        if self.type == "ids":
            if not self.ids:
                raise ValueError("selection.ids is required when selection.type='ids'")
        elif self.type == "bbox":
            if not self.bbox or len(self.bbox) != 4:
                raise ValueError(
                    "selection.bbox must contain [minLon, minLat, maxLon, maxLat] when selection.type='bbox'",
                )
            min_lon, min_lat, max_lon, max_lat = self.bbox
            if min_lon >= max_lon or min_lat >= max_lat:
                raise ValueError("selection.bbox extents are invalid")
        return self


class GISFeatureSetRef(SQLModel):
    """Reference to a GIS layer and an optional selection."""

    layer_id: Literal["study-sites", "regions"]
    selection: GISSelection = Field(default_factory=GISSelection)


class GISOperationCapability(SQLModel):
    id: str
    label: str
    description: str
    permission: str
    execution: Literal["sync", "async"] = "sync"
    requires_authentication: bool = True
    enabled: bool = False
    geometry_inputs: list[str] = Field(default_factory=list)
    parameter_schema: dict[str, Any] = Field(default_factory=dict)


class GISCapabilitiesPublic(SQLModel):
    version: str
    operations: list[GISOperationCapability]
    limits: dict[str, Any] = Field(default_factory=dict)


class GISWithinDistanceParameters(SQLModel):
    distance: float = Field(gt=0)
    unit: Literal["meter", "kilometer"] = "meter"
    return_target: Literal["source", "against"] = Field(default="source", alias="return")

    model_config = ConfigDict(populate_by_name=True)


class GISWithinDistanceRequest(SQLModel):
    source: GISFeatureSetRef
    against: GISFeatureSetRef
    parameters: GISWithinDistanceParameters


class GISRegionFeature(SQLModel):
    id: uuid.UUID
    name: str


class GISWithinDistanceResult(SQLModel):
    source_layer_id: str
    against_layer_id: str
    return_layer_id: str
    distance_meters: float
    count: int
    study_sites: list["StudySiteMapPoint"] | None = None
    regions: list[GISRegionFeature] | None = None


class GISBufferParameters(SQLModel):
    distance: float = Field(gt=0)
    unit: Literal["meter", "kilometer"] = "meter"
    dissolve: bool = False


class GISBufferRequest(SQLModel):
    target: GISFeatureSetRef
    parameters: GISBufferParameters


class GISBufferedFeature(SQLModel):
    source_id: uuid.UUID | None = None
    geometry: dict[str, Any]


class GISBufferResult(SQLModel):
    target_layer_id: str
    distance_meters: float
    dissolved: bool
    count: int
    features: list[GISBufferedFeature]


class GISClipRequest(SQLModel):
    target: GISFeatureSetRef
    clip_with: GISFeatureSetRef


class GISClipResult(SQLModel):
    target_layer_id: str
    clip_layer_id: str
    count: int
    study_sites: list["StudySiteMapPoint"] | None = None


class GISMetric(SQLModel):
    type: Literal["count", "avg"]
    field: str
    alias: str | None = None


class GISSpatialFilter(SQLModel):
    layer_id: Literal["regions"]
    selection: GISSelection = Field(default_factory=GISSelection)
    predicate: Literal["within"] = "within"


class GISSummaryStatsRequest(SQLModel):
    target: GISFeatureSetRef
    group_by: list[str] = Field(default_factory=list)
    metrics: list[GISMetric] = Field(min_length=1)
    spatial_filter: GISSpatialFilter | None = None


class GISSummaryStatsPublic(SQLModel):
    rows: list[dict[str, Any]]
    count: int


class LocationBase(SQLModel):
    """Database model (base) for geographic locations."""

    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180
    cluster_label: int | None = None


class Location(LocationBase, table=True):
    __table_args__ = (Index("ix_location_lon_lat", "longitude", "latitude"),)

    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    geom: Any = Field(
        default=None,
        sa_column=Column(Geometry("POINT", srid=4326), nullable=False),
    )
    study_sites: list["StudySite"] = Relationship(back_populates="location")


def _sync_location_geom(mapper: Any, connection: Any, target: Location) -> None:  # noqa: ANN401, ARG001
    """Keep geom column in sync with latitude/longitude."""
    from geoalchemy2.shape import from_shape
    from shapely.geometry import Point as ShapelyPoint

    target.geom = from_shape(ShapelyPoint(float(target.longitude), float(target.latitude)), srid=4326)


event.listen(Location, "before_insert", _sync_location_geom)
event.listen(Location, "before_update", _sync_location_geom)


class LocationPublicSimple(LocationBase):
    """Location without nested study sites (to avoid circular references)."""

    id: uuid.UUID


class LocationPublic(LocationBase):
    id: uuid.UUID
    study_sites: list["StudySitePublic"]


class LocationsPublic(SQLModel):
    data: list[LocationPublic]
    count: int


class LocationUpdate(LocationBase):
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180


class LocationCreate(LocationBase):
    pass


# Generic message
class Message(SQLModel):
    message: str


class RelationBase(SQLModel):
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    key: str = Field(max_length=255)
    value: str = Field(max_length=255)


class Relation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id")
    item: Optional["Item"] = Relationship(back_populates="relations")


class RelationCreate(RelationBase):
    pass


class RelationPublic(RelationBase):
    id: int
    item_id: uuid.UUID


class RelationsPublic(SQLModel):
    data: list[RelationPublic]
    count: int


class StudySiteBase(SQLModel):
    """Database model for study site extraction results."""

    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    confidence_score: float
    context: str
    extraction_method: CoordinateExtractionMethod
    item_id: uuid.UUID = Field(foreign_key="item.id", index=True)
    validation_score: float = 0.0
    source_type: CoordinateSourceType = Field(
        description="Type of source from which the study site was extracted",
    )
    section: PaperSections = Field(
        default=PaperSections.OTHER,
        description="Section of the paper where the study site was mentioned",
        sa_column=Column(Enum(PaperSections)),
    )
    name: str | None = Field(
        default=None,
        description="Name of the study site, if available",
        max_length=255,
    )
    is_manual: bool = Field(
        default=False,
        description="True if created or modified by a human, False if automatic extraction",
        index=True,
    )
    location_id: uuid.UUID = Field(foreign_key="location.id", index=True)


class StudySite(StudySiteBase, table=True):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    item: "Item" = Relationship(back_populates="study_sites")
    location: "Location" = Relationship(back_populates="study_sites")


class StudySiteUpdate(StudySiteBase):
    validation_score: float = 0.0
    latitude: Latitude
    longitude: Longitude  # validates -180 <= value <= 180
    confidence_score: float
    source_type: CoordinateSourceType = Field(
        description="Type of source from which the study site was extracted",
    )
    context: str
    section: PaperSections = Field(
        default=PaperSections.OTHER,
        description="Section of the paper where the study site was mentioned",
        sa_column=Column(Enum(PaperSections)),
    )

    extraction_method: CoordinateExtractionMethod


class StudySitePublic(StudySiteBase):
    id: uuid.UUID
    item_id: uuid.UUID
    location: "LocationPublicSimple"

    model_config = ConfigDict(from_attributes=True)  # pyright: ignore[reportAssignmentType]

    # Computed fields for backward compatibility with frontend
    # These are automatically included in JSON serialization
    @computed_field  # type: ignore[misc]
    @property
    def latitude(self) -> float | None:
        """Get latitude from location relationship."""
        return self.location.latitude if self.location else None

    @computed_field  # type: ignore[misc]
    @property
    def longitude(self) -> float | None:
        """Get longitude from location relationship."""
        return self.location.longitude if self.location else None


class StudySiteCreate(StudySiteBase):
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
    )
    item_id: uuid.UUID
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    location_id: uuid.UUID | None = None

    def validate_location_or_coordinates(self) -> Self:
        """Ensure either location_id or coordinates are provided."""
        if self.location_id is None and (self.latitude is None or self.longitude is None):
            msg = "Either location_id or both latitude and longitude must be provided."
            raise ValueError(msg)
        return self


class StudySiteManualCreate(SQLModel):
    """Model for manually creating a study site via API."""

    name: str = Field(description="Name of the study site", max_length=255)
    latitude: Latitude = Field(description="Latitude coordinate")
    longitude: Longitude = Field(description="Longitude coordinate")
    context: str = Field(
        default="Manually added by user",
        description="Description or context about the study site",
    )
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    validation_score: float = Field(default=1.0, ge=0.0, le=1.0)


class StudySiteManualUpdate(SQLModel):
    """Model for manually updating a study site via API."""

    name: str | None = Field(default=None, description="Name of the study site", max_length=255)
    latitude: Latitude | None = Field(default=None, description="Latitude coordinate")
    longitude: Longitude | None = Field(default=None, description="Longitude coordinate")
    context: str | None = Field(default=None, description="Description or context")
    confidence_score: float | None = Field(default=None, ge=0.0, le=1.0)
    validation_score: float | None = Field(default=None, ge=0.0, le=1.0)


class StudySitesPublic(SQLModel):
    """Collection of study sites."""

    data: list[StudySitePublic]
    count: int


class StudySiteMapPoint(SQLModel):
    """Lightweight model for map display — only coordinates and minimal metadata."""

    id: uuid.UUID
    name: str | None = None
    item_id: uuid.UUID
    item_title: str | None = None
    latitude: float
    longitude: float
    is_manual: bool
    confidence_score: float


class StudySiteMapPointsPublic(SQLModel):
    """Collection of lightweight map points."""

    data: list[StudySiteMapPoint]
    count: int


# ---------- Regions (uploaded shapefiles) ----------


class RegionBase(SQLModel):
    """Base model for geographic regions from uploaded shapefiles."""

    name: str = Field(max_length=255)
    description: str = Field(default="", max_length=2048)
    source_filename: str | None = Field(default=None, max_length=255)
    properties_json: str | None = Field(default=None, description="Original shapefile attributes as JSON")


class Region(RegionBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE")
    owner: "User" = Relationship(back_populates="regions")
    geom: Any = Field(
        sa_column=Column(Geometry("MULTIPOLYGON", srid=4326), nullable=False),
    )
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)


class RegionPublic(RegionBase):
    """Region with GeoJSON geometry for API responses."""

    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    geojson: dict[str, Any] | None = None  # populated at the route level via ST_AsGeoJSON

    model_config = ConfigDict(from_attributes=True)


class RegionsPublic(SQLModel):
    data: list[RegionPublic]
    count: int


class RegionStats(SQLModel):
    """Spatial statistics for a region."""

    region_id: uuid.UUID
    region_name: str
    study_site_count: int = 0
    paper_count: int = 0
    manual_count: int = 0
    automatic_count: int = 0
    extraction_methods: dict[str, int] = Field(default_factory=dict)
    papers: list["ItemSummary"] = Field(default_factory=list)


# Extraction Results - store all candidates found during extraction
class ExtractionResultBase(SQLModel):
    """Base model for extraction results (all candidates found)."""

    name: str | None = Field(default=None, max_length=512)
    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    context: str | None = Field(default=None, max_length=2048)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: CoordinateExtractionMethod = Field(
        sa_column=Column(Enum(CoordinateExtractionMethod)),
    )
    source_type: CoordinateSourceType = Field(
        sa_column=Column(Enum(CoordinateSourceType)),
    )
    section: PaperSections = Field(sa_column=Column(Enum(PaperSections)))
    rank: int = Field(default=0)  # Ranking position (1 = highest)
    is_saved: bool = Field(default=False)  # Whether it was saved as a StudySite


class ExtractionResult(ExtractionResultBase, table=True):
    """Extraction result - stores all candidates found during extraction.

    This model stores ALL entities found during extraction (not just top 10),
    allowing users to see what was detected and review lower-ranked results.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    item_id: uuid.UUID = Field(foreign_key="item.id", index=True)
    item: "Item" = Relationship(back_populates="extraction_results")
    created_at: datetime = timestamp_field()


class ExtractionResultPublic(ExtractionResultBase):
    """Public extraction result with computed fields."""

    id: uuid.UUID
    item_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExtractionResultsPublic(SQLModel):
    """Collection of extraction results."""

    data: list[ExtractionResultPublic]
    count: int
    top_10_count: int  # How many of the top 10 were saved


class TagBase(SQLModel):
    name: str = Field(max_length=64)


class Tag(TagBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=64)
    items: list["Item"] = Relationship(
        back_populates="tags", link_model=ItemTagLink, sa_relationship_kwargs={"lazy": "selectin"}
    )
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: "User" = Relationship(back_populates="tags")
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)


class TagCreate(TagBase):
    item_ids: list[uuid.UUID] = Field(default_factory=list)


class TagPublic(TagBase):
    id: int
    owner_id: uuid.UUID
    items: list["ItemSummary"] | None = None

    @field_serializer("items")
    def serialize_items(self, items: list["Item"] | None, _info):
        """Serialize Item objects to ItemSummary."""
        if not items:
            return None
        return [ItemSummary(id=item.id, title=item.title) for item in items]


class TagsPublic(SQLModel):
    data: list["TagPublic"]
    count: int


class TaskRef(SQLModel):
    """Model representing a reference to an asynchronous task.

    The task can be discovered and handled by celery workers.
    """

    # Target domain entity the task operates on
    item_id: uuid.UUID = Field(description="Target Item ID")
    # Celery AsyncResult.id
    task_id: str = Field(description="Celery task identifier")
    # Initial server-side assessment at enqueue time
    status: InitialTaskState = Field(
        default="queued",
        description="Initial enqueue assessment for 202 responses",
    )
    # Optional per-task note (e.g., reason when skipped)
    message: str | None = Field(default=None, description="Optional reason")


class ExtractStudySitesRequest(SQLModel):
    """Request body for study site extraction endpoint."""

    item_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Optional list of specific item IDs to process. If None, processes all items.",
    )
    force: bool = Field(
        default=False,
        description="Force re-extraction even if study sites already exist",
    )


class EnrichItemsRequest(SQLModel):
    """Request body for CrossRef enrichment endpoint."""

    item_ids: list[uuid.UUID] | None = Field(
        default=None,
        description="Optional list of specific item IDs to enrich. If None, enriches all items missing title, abstract, or DOI.",
    )


class TasksAccepted(SQLModel):
    """Model representing a batch of accepted tasks."""

    data: list[TaskRef]
    count: int


class TaskStatus(SQLModel):
    """Model representing the status of an asynchronous task."""

    task_id: str = Field(description="Celery task identifier")
    task_status: CeleryState = Field(description="Celery task state")
    task_result: ItemPublic | None = Field(
        default=None,
        description="Result payload if available; omitted/None in most states",
    )


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


class SignupResponse(SQLModel):
    user: "UserPublic"
    message: str
    email_sent: bool


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class UserBase(SQLModel):
    created_at: datetime = timestamp_field()
    updated_at: datetime = timestamp_field(onupdate_now=True)
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)
    zotero_id: str | None = Field(default=None, max_length=32)
    enc_zotero_api_key: str | None = Field(
        default=None,
        alias="zotero_api_key",
        description="Your Zotero API key. It will be encrypted for security",
    )

    @field_validator("enc_zotero_api_key", mode="before")
    @classmethod
    def encrypt_api_key(cls, v: str | None) -> str | None:
        """Encrypt API key before storing."""
        if v is None or v == "":
            return None
        if v.startswith("gAAAAAB"):  # Already encrypted
            return v
        return cipher_suite.encrypt(v.encode()).decode()

    @field_serializer("enc_zotero_api_key", when_used="json")
    def serialize_api_key(self, value: str | None) -> str | None:
        """Return masked value in JSON responses."""
        return "****" if value else None

    def get_zotero_api_key(self) -> str | None:
        """Decrypt and return the actual API key."""
        if not self.enc_zotero_api_key:
            return None
        try:
            return cipher_suite.decrypt(self.enc_zotero_api_key.encode()).decode()
        except Exception:
            # Key may be stored unencrypted (legacy data)
            return self.enc_zotero_api_key


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=40)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(UserBase):
    email: EmailStr | None = Field(default=None, max_length=255)  # pyright: ignore[reportIncompatibleVariableOverride]
    password: str | None = Field(default=None, min_length=8, max_length=40)
    full_name: str | None = Field(default=None, max_length=255)
    zotero_id: str | None = Field(default=None, max_length=32)
    enc_zotero_api_key: str | None = Field(
        default=None,
        alias="zotero_api_key",
        description="Your Zotero API key. It will be encrypted for security",
    )


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)
    zotero_id: str | None = Field(default=None, max_length=32)
    enc_zotero_api_key: str | None = Field(
        default=None,
        alias="zotero_api_key",
    )


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=40)
    new_password: str = Field(min_length=8, max_length=40)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    items: list["Item"] = Relationship(back_populates="owner", cascade_delete=True)
    tags: list["Tag"] = Relationship(back_populates="owner", cascade_delete=True)
    collections: list["Collection"] = Relationship(
        back_populates="owner",
        cascade_delete=True,
    )
    regions: list["Region"] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
