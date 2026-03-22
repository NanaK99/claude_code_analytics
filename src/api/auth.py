import os
from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str = Security(_api_key_header)) -> None:
    expected = os.getenv("API_KEY")
    if not expected or key != expected:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
