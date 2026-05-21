from pydantic import BaseModel


class UserRegister(BaseModel):
    username: str
    password: str

    model_config = {
        "json_schema_extra": {
            "example": {"username": "john_doe", "password": "secret123"}
        }
    }


class UserLogin(BaseModel):
    username: str
    password: str

    model_config = {
        "json_schema_extra": {
            "example": {"username": "john_doe", "password": "secret123"}
        }
    }


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str

    model_config = {
        "json_schema_extra": {
            "example": {"refresh_token": "<your_refresh_token>"}
        }
    }


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
