class ResponseCode:
    # 1000–1999 系統層級／通用回應
    # 2000–2999 成功／一般操作
    # 3000–3999 驗證 & 授權（Authentication）
    # 3000：未授權；3001：Token 過期
    # 4000–4999 用戶請求錯誤（Client Error）
    # 5000–5999 伺服器錯誤（Server Error）
    # 6000–6999 外部服務錯誤／第三方 API

    SUCCESS = 2000

    UNAUTHORIZED = 3000
    TOKEN_EXPIRED = 3001
    PERMISSION_DENIED = 3002

    INVALID_REQUEST = 4000
    METHOD_NOT_ALLOWED = 4001
    GENERAL_NOT_FOUND = 4002
    USER_NOT_FOUND = 4003

    INTERNAL_ERROR = 5000

    EXTERNAL_API_ERROR = 6000
    EXTERNAL_API_AUTHORIZATION_ERROR = 6001
    EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND = 6002


class ResponseMessage:
    SUCCESS = 'success'

    UNAUTHORIZED = 'unauthorized'
    TOKEN_EXPIRED = 'token expired'
    PERMISSION_DENIED = 'permission denied'

    INVALID_REQUEST = 'invalid request'
    USER_NOT_FOUND = 'user not found'

    INTERNAL_ERROR = 'internal error'

    EXTERNAL_API_ERROR = 'external api error'
    EXTERNAL_API_AUTHORIZATION_ERROR = 'external api authorization error'
    EXTERNAL_API_ACCESS_TOKEN_NOT_FOUND = 'external api access_token not found'
