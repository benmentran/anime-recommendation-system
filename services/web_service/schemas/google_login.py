from pydantic import BaseModel

class GoogleLoginData(BaseModel):
    credential: str 
    