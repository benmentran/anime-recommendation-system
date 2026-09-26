from fastapi import APIRouter, HTTPException, Header, status
from schemas.sign_in import SignInSchema
from schemas.sign_up import SignUpSchema
from schemas.profile import Profile
from app.security import hash_pw, verify_pw, create_token, decode_token
from app.db import db, UserQuery

router = APIRouter(prefix="/auth")

@router.post("/signup")
def signup(data: SignUpSchema):
    if db.get(UserQuery.email == data.email):
        raise HTTPException(status_code=400, detail="Email already exists")

    db.insert({
        "email": data.email,
        "hashed_password": hash_pw(data.password),
        "display_name": data.display_name,
        "avatar_url": None,
        "devices": [],
        "roles": ["user"]
    })

    return {"success": True}

@router.post("/signin")
def signin(data: SignInSchema):
    user = db.get(UserQuery.email == data.email)
    if not user or not verify_pw(data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    access_token = create_token(user['email'], user['display_name'])
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=Profile)
def me(authorization: str = Header(...)):
    token = token_from_header(authorization)
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    email = payload.get("sub")
    user = db.get(UserQuery.email == email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return {
        "email": user["email"],
        "display_name": user["display_name"],
        "avatar_url": user["avatar_url"]
    }

def token_from_header(header: str):
    if not header or not header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing token")
    
    return header.split(" ")[1]
