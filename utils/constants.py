class ResponseCode:
    # 1000–1999 系統層級／通用回應
    # 2000–2999 成功／一般操作
    # 3000–3999 驗證 & 授權（Authentication）
    # 4000–4999 用戶請求錯誤（Client Error）
    # 5000–5999 伺服器錯誤（Server Error）
    # 6000–6999 外部服務錯誤／第三方 API

    SUCCESS = 2000  # Operation completed successfully

    UNAUTHORIZED = 3000  # Authentication failed or credentials invalid
    TOKEN_EXPIRED = 3001  # JWT token has expired
    PERMISSION_DENIED = 3002  # User lacks required permissions

    VALIDATION_ERROR = 4000  # Request data validation failed
    METHOD_NOT_ALLOWED = 4001  # HTTP method not supported
    NOT_FOUND = 4002  # Requested resource not found
    USER_NOT_FOUND = 4003  # Specific user not found
    USER_INACTIVE = 4004  # User account is inactive
    INVALID_TOKEN = 4005  # Invalid JWT token
    RESOURCE_NOT_FOUND = 4006  # Resource not found
    RESOURCE_NOT_AVAILABLE = 4007  # Resource not available
    RESOURCE_BUSY = 4008  # Resource is busy
    CONFLICT = 4009  # Data conflict or duplicate entry
    FORBIDDEN = 4030  # Access forbidden
    UNKNOWN_ERROR = 4999  # Unhandled client error

    INTERNAL_ERROR = 5000  # Server internal error

    EXTERNAL_API_ERROR = 6000  # Third-party API error
    EXTERNAL_API_AUTHORIZATION_ERROR = 6001  # Third-party API auth error
    EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND = 6002  # Third-party API token missing


class ResponseMessage:
    SUCCESS = 'success'  # General success message

    UNAUTHORIZED = 'unauthorized'  # Authentication failed
    TOKEN_EXPIRED = 'token expired'  # JWT token expired
    PERMISSION_DENIED = 'permission denied'  # Insufficient permissions
    INVALID_TOKEN = 'invalid token'

    VALIDATION_ERROR = 'validation error'  # Input validation failed
    METHOD_NOT_ALLOWED = 'method not allowed'  # HTTP method not supported
    NOT_FOUND = 'resource not found'  # Resource does not exist
    USER_NOT_FOUND = 'user not found'  # User does not exist
    RESOURCE_NOT_FOUND = 'resource not found'  # Resource not found
    RESOURCE_NOT_AVAILABLE = 'resource not available'  # Resource not available
    RESOURCE_BUSY = 'resource busy'  # Resource is busy
    CONFLICT = 'data conflict'  # Data conflict or duplicate
    FORBIDDEN = 'forbidden'  # Access forbidden
    UNKNOWN_ERROR = 'request failed'  # Unhandled error

    INTERNAL_ERROR = 'internal error'  # Server internal error

    EXTERNAL_API_ERROR = 'external api error'  # Third-party API error
    EXTERNAL_API_AUTHORIZATION_ERROR = (
        'external api authorization error'  # Third-party API auth error
    )
    EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND = (
        'external api access_token not found'  # Third-party API token missing
    )
