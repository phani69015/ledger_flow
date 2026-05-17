from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    """Schema for user registration."""
    email: str = Field(..., description="User email address")
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=6, description="Password (min 6 chars)")


class UserLogin(BaseModel):
    """Schema for user login."""
    email: str = Field(..., description="Email address or username")
    password: str = Field(..., description="User password")


class UserResponse(BaseModel):
    """Schema for user response (public info only)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    is_active: bool
    created_at: Optional[datetime] = None


class Token(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Decoded token data."""
    user_id: Optional[int] = None
    email: Optional[str] = None
