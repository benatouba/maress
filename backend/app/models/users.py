import uuid

from pydantic import EmailStr, field_serializer, field_validator  # noqa: TC002
from sqlmodel import Field, Relationship, SQLModel

from app.core.security import cipher_suite
from app.models.collections import Collection


# Shared properties
class UserBase(SQLModel):
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
        if v.startswith("gAAAAAB"):  # Not already encrypted
            return cipher_suite.encrypt(v.encode()).decode()
        return v

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
            return None


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
    enc_zotero_api_key: str | None = Field(default=None)


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


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)
