from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import google.auth.transport.requests
import google.oauth2.id_token
from schemas.google_login import GoogleLoginData

router = APIRouter()

@router.post("api/google-login")
async def google_login(data: GoogleLoginData):
    try:
        request_adapter = google.auth.transport.requests.Request()
        id_info = google.oauth2.id_token.verify_oauth2_token(
            data.credential,
            request_adapter,
            audience="YOUR_GOOGLE_CLIENT_ID"
        )
        
        return {"success": True, "email": id_info.get("email")}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": str(e)})