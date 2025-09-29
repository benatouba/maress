
# class AuthorBase(SQLModel):
#     full_name: str = Field(min_length=3, max_length=255)
#     initials: str = Field(min_length=2, max_length=32)
#     institutions: list[str] = Field(sa_column=Column(postgresql.ARRAY(String())))
#
#
#
#
# class AuthorCreate(SQLModel):
#     full_name: str = Field(min_length=3, max_length=255)
#     institutions: list[str] = Field(sa_column=Column(postgresql.ARRAY(String())))
#
#
# class Author(AuthorBase, table=True):
#     id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
#     items: list["Item"] = Relationship(
#         back_populates="authors",
#         link_model=ItemAuthorLink,
#     )


