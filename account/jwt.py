from datetime import timedelta

from django.contrib.auth.models import User
from rest_framework import authentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from account.caches import TokenBlacklistCache
from account.models import Member

# JWT expires in seconds (1 day)
JWT_EXPIRES_IN = 60 * 60 * 24


class JWTService:
    """JWT 服務，統一管理 token 生成、驗證、刷新"""

    @staticmethod
    def create_tokens(member):
        """
        為 member 創建 JWT tokens

        Args:
            member: Member instance

        Returns:
            dict: {
                'access_token': str,
                'refresh_token': str,
                'token_type': 'Bearer',
                'expires_in': int
            }
        """
        user = member.user
        refresh = RefreshToken.for_user(user)

        # 只添加必要的 member 資訊到 token payload
        refresh['member_id'] = member.id
        refresh['role'] = member.role

        return {
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'token_type': 'Bearer',
            'expires_in': JWT_EXPIRES_IN,
        }

    @staticmethod
    def validate_token(token):
        """
        驗證 access token

        Args:
            token: JWT access token string

        Returns:
            tuple: (is_valid: bool, result: Member instance or error message)
        """
        try:
            access_token = AccessToken(token)

            # 檢查 token 是否在黑名單中
            token_jti = access_token.get('jti')
            if token_jti and TokenBlacklistCache.is_token_blacklisted(token_jti):
                return False, 'Token 已被撤銷'

            # 獲取 member 資訊
            member_id = access_token.get('member_id')
            if not member_id:
                return False, 'Token 中缺少 member 資訊'

            try:
                member = Member.objects.select_related('user').get(id=member_id)
            except Member.DoesNotExist:
                return False, 'Member 不存在'

            # 檢查 member 和 user 是否啟用
            if not member.user.is_active:
                return False, '用戶已被停用'

            return True, member

        except (TokenError, InvalidToken) as e:
            return False, f"無效的 token: {str(e)}"
        except Exception as e:
            return False, f"Token 驗證失敗: {str(e)}"

    @staticmethod
    def refresh_access_token(refresh_token):
        """
        使用 refresh token 獲取新的 access token

        Args:
            refresh_token: JWT refresh token string

        Returns:
            dict or None: 新的 token 資訊或 None（如果失敗）
        """
        try:
            refresh = RefreshToken(refresh_token)

            # 檢查 refresh token 是否在黑名單中
            refresh_jti = refresh.get('jti')
            if refresh_jti and TokenBlacklistCache.is_token_blacklisted(refresh_jti):
                return None

            # 檢查 member 是否仍然存在且啟用
            member_id = refresh.get('member_id')
            if member_id:
                try:
                    member = Member.objects.select_related('user').get(id=member_id)
                    if not member.user.is_active:
                        return None
                except Member.DoesNotExist:
                    return None

            # 生成新的 access token
            access_token = refresh.access_token

            return {
                'access_token': str(access_token),
                'token_type': 'Bearer',
                'expires_in': JWT_EXPIRES_IN,
            }

        except (TokenError, InvalidToken):
            return None
        except Exception:
            return None

    @staticmethod
    def blacklist_token(token):
        """
        將 token 加入黑名單

        Args:
            token: JWT token string (access or refresh)

        Returns:
            bool: 是否成功加入黑名單
        """
        try:
            # 可能是 access token 或 refresh token
            try:
                access_token = AccessToken(token)
                token_jti = access_token.get('jti')
            except:
                refresh_token = RefreshToken(token)
                token_jti = refresh_token.get('jti')

            if token_jti:
                TokenBlacklistCache.add_token_to_blacklist(token_jti)
                return True

        except Exception:
            pass

        return False


class JWTAuthentication(authentication.BaseAuthentication):
    """
    自定義 JWT 認證類別，替代 rest_framework_simplejwt 的標準實作
    """

    def authenticate(self, request):
        """
        認證請求中的 JWT token

        Returns:
            tuple: (member.user, token) or None
        """
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')

        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header.split(' ')[1]

        try:
            is_valid, result = JWTService.validate_token(token)

            if not is_valid:
                raise AuthenticationFailed(result)

            member = result
            return (member.user, token)

        except Exception as e:
            raise AuthenticationFailed(f'Authentication failed: {str(e)}')

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response.
        """
        return 'Bearer'
