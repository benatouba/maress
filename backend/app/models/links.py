from sqlmodel import SQLModel, Field
import uuid

class ItemTagLink(SQLModel, table=True):
    item_id: uuid.UUID | None = Field(
        default=None,
        foreign_key="item.id",
        primary_key=True,
    )
    tag_id: int | None = Field(default=None, foreign_key="tag.id", primary_key=True)


# class ItemAuthorLink(SQLModel, table=True):
#     item_id: uuid.UUID | None = Field(
#         default=None,
#         foreign_key="item.id",
#         primary_key=True,
#     )
#     author_id: uuid.UUID | None = Field(
#         default=None,
#         foreign_key="author.id",
#         primary_key=True,
#     )
