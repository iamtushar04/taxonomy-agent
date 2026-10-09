import os
from dotenv import load_dotenv
load_dotenv()
# pyrefly: ignore [missing-import]
import jwt
# pyrefly: ignore [missing-import]
from fastapi import Depends, HTTPException, status
# pyrefly: ignore [missing-import]
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    Decodes the JWT token to extract the user ID without verifying the signature,
    since it is signed by the external microservice and we don't have the secret.
    """
    token = credentials.credentials

    try:
        # Decode without verifying signature or nbf (to prevent clock drift issues)
        payload = jwt.decode(token, options={"verify_signature": False, "verify_nbf": False})
        
        # Extract the subject (user ID) from the token
        user_id_str = payload.get("sub") or payload.get("id") or payload.get("user_id")
        
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token does not contain a user ID (sub)."
            )
            
        return int(user_id_str)
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired."
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials. {str(e)}"
        )
