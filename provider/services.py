from dataclasses import dataclass
from typing import Any, Dict, Optional

from django.core.cache import cache
from django.db import transaction
from django.db.models import Count

from provider.caches import MemberProviderProxyAccountCache
from provider.handlers.spotify import SpotifyAPIProviderHandler
from provider.models import Provider, ProviderProxyAccount
from utils.constants import ResponseCode


@dataclass
class ServiceResult:
    success: bool
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    message: Optional[str] = None


class SpotifyProxyAccountService:
    """Spotify Proxy Account 業務邏輯服務"""

    PLATFORM = Provider.PlatformOptions.SPOTIFY

    @staticmethod
    def acquire_proxy_account(member) -> ServiceResult:
        platform = SpotifyProxyAccountService.PLATFORM

        # 1. 檢查快取（信任快取，如果有就直接返回）
        cached_data = MemberProviderProxyAccountCache.get_cache(platform, member.id)
        if cached_data:
            proxy_account = (
                ProviderProxyAccount.objects.filter(
                    code=cached_data['proxy_account_code']
                )
                .select_related('provider')
                .first()
            )

            if proxy_account:
                return ServiceResult(
                    success=True,
                    data=SpotifyProxyAccountService._get_proxy_account_data_with_token(
                        proxy_account
                    ),
                )

        # 2. 快取未命中，獲取分散式鎖
        if not MemberProviderProxyAccountCache.acquire_lock(platform, member.id):
            return ServiceResult(
                success=False,
                error_code=ResponseCode.RESOURCE_BUSY,
                message='處理中，請稍後再試',
            )

        try:
            with transaction.atomic():
                # 3. Double-check：查詢資料庫（防止在等待鎖期間已被分配）
                existing_proxy = (
                    ProviderProxyAccount.objects.select_for_update()
                    .filter(current_member=member, provider__platform=platform)
                    .select_related('provider')
                    .first()
                )

                if existing_proxy:
                    # 寫回快取
                    MemberProviderProxyAccountCache.set_cache(
                        platform,
                        member.id,
                        existing_proxy.code,
                        existing_proxy.provider.code,
                    )
                    return ServiceResult(
                        success=True,
                        data=SpotifyProxyAccountService._get_proxy_account_data_with_token(
                            existing_proxy
                        ),
                    )

                # 4. 分配新的 proxy account
                proxy_account = SpotifyProxyAccountService._allocate_proxy_account()

                if not proxy_account:
                    return ServiceResult(
                        success=False,
                        error_code=ResponseCode.RESOURCE_NOT_AVAILABLE,
                        message='目前沒有可用的 proxy account，請稍後再試',
                    )

                proxy_account.current_member = member
                proxy_account.save()

                # 5. 寫入快取
                MemberProviderProxyAccountCache.set_cache(
                    platform, member.id, proxy_account.code, proxy_account.provider.code
                )

            # 6. 分配新 proxy account 時 force refresh token
            return ServiceResult(
                success=True,
                data=SpotifyProxyAccountService._get_proxy_account_data_with_token(
                    proxy_account, force_refresh_from_provider=True
                ),
            )

        except Exception as e:
            return ServiceResult(
                success=False,
                error_code=ResponseCode.INTERNAL_ERROR,
                message=f"分配 proxy account 時發生錯誤: {str(e)}",
            )
        finally:
            # 6. 釋放鎖
            MemberProviderProxyAccountCache.release_lock(platform, member.id)

    @staticmethod
    def release_proxy_account(member) -> ServiceResult:
        """釋放用戶的 proxy account"""
        platform = SpotifyProxyAccountService.PLATFORM

        # 1. 獲取分散式鎖
        if not MemberProviderProxyAccountCache.acquire_lock(platform, member.id):
            return ServiceResult(
                success=False,
                error_code=ResponseCode.RESOURCE_BUSY,
                message='處理中，請稍後再試',
            )

        try:
            with transaction.atomic():
                # 2. 查詢並鎖定 proxy account
                proxy_account = (
                    ProviderProxyAccount.objects.select_for_update()
                    .filter(current_member=member, provider__platform=platform)
                    .first()
                )

                if not proxy_account:
                    return ServiceResult(
                        success=False,
                        error_code=ResponseCode.RESOURCE_NOT_FOUND,
                        message='用戶沒有分配的 proxy account',
                    )

                proxy_account_code = proxy_account.code

                # 3. 釋放 proxy account
                proxy_account.current_member = None
                proxy_account.save()

                # 4. 刪除快取
                MemberProviderProxyAccountCache.delete_cache(platform, member.id)

            return ServiceResult(
                success=True,
                data={
                    'released_proxy_account': proxy_account_code,
                    'message': '成功釋放 proxy account',
                },
            )

        except Exception as e:
            return ServiceResult(
                success=False,
                error_code=ResponseCode.INTERNAL_ERROR,
                message=f"釋放 proxy account 時發生錯誤: {str(e)}",
            )
        finally:
            # 5. 釋放鎖
            MemberProviderProxyAccountCache.release_lock(platform, member.id)

    @staticmethod
    def _allocate_proxy_account():
        """分配策略：使用資料庫鎖避免競爭條件"""
        return (
            ProviderProxyAccount.objects.select_for_update(skip_locked=True)
            .filter(
                provider__platform=SpotifyProxyAccountService.PLATFORM,
                is_active=True,
                current_member__isnull=True,  # 沒有被任何用戶使用
            )
            .first()
        )

    @staticmethod
    def _get_proxy_account_data_with_token(
        proxy_account, force_refresh_from_provider=False
    ):
        """取得 proxy account 資料並包含 access token"""
        handler = SpotifyAPIProviderHandler(
            proxy_account.provider, proxy_account=proxy_account
        )

        if force_refresh_from_provider:
            access_token = handler.refresh_token()
        else:
            access_token = handler.get_access_token()

        return {
            'proxy_account_code': proxy_account.code,
            'provider_code': proxy_account.provider.code,
            'access_token': access_token,
        }
