from pydantic import BaseModel, EmailStr

class Profile(BaseModel):
    email: EmailStr
    display_name: str
    avatar_url: str | None = None
    