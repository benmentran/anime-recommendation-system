from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import JWTError
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("SECRET_KEY") 
ALGORITHM = "HS256"
EXPIRY = 60 * 24

def hash_pw(password): 
    return pwd_context.hash(password)

def verify_pw(plain, hashed): 
    return pwd_context.verify(plain, hashed)

def create_token(email, display_name: str):
    payload = {
        "sub": email,
        "display_name": display_name,
        "exp": datetime.utcnow() + timedelta(minutes=EXPIRY)
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError as e:
        console.log(f"Expired Signature Error: {e}")
        return None
    except jwt.InvalidTokenError:
        console.log(f"Invalid Token Error: {e}")
        return None
    except JWTError as e:
        console.log(f"Failed to decode token: {token}", e)
        return None
    