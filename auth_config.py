from datetime import timedelta

# Secret keys – change these in production!
SECRET_KEY = "super-secret-jwt-key-change-in-production"
REFRESH_SECRET_KEY = "super-secret-refresh-key-change-in-production"

ALGORITHM = "HS256"

ACCESS_TOKEN_EXPIRE_MINUTES = 15       # short-lived
REFRESH_TOKEN_EXPIRE_DAYS = 7          # long-lived
