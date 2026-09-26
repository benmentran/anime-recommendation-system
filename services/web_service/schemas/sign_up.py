from pydantic import BaseModel, EmailStr

class SignUpSchema(BaseModel):
    email: EmailStr
    password: str
    display_name: str
