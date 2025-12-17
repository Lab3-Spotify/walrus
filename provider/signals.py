"""
Provider app signals

處理 proxy account 相關的 signal，確保快取一致性
"""
import logging

from django.db.models.signals import pre_save
from django.dispatch import receiver

from provider.caches import MemberProviderProxyAccountCache
from provider.models import ProviderProxyAccount

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=ProviderProxyAccount)
def clear_proxy_account_cache_on_release(sender, instance, **kwargs):
    """
    當 ProviderProxyAccount 的 current_member 改變時清除快取

    使用場景：
    - Admin 在 Django Admin 中手動 release proxy account
    - 其他直接修改 current_member 的情況

    注意：Service 層的 release_proxy_account 已經處理快取清除，
    這個 signal 主要是防止繞過 Service 層直接修改的情況
    """
    # 如果是新建的實例，不需要處理
    if instance.pk is None:
        return

    try:
        # 獲取資料庫中的舊值
        old_instance = ProviderProxyAccount.objects.get(pk=instance.pk)
        old_member = old_instance.current_member
        new_member = instance.current_member

        # 如果 current_member 沒有改變，不需要處理
        if old_member == new_member:
            return

        # 如果舊的 member 存在且被改變（釋放或轉移），清除該 member 的快取
        if old_member:
            platform = old_instance.provider.platform
            MemberProviderProxyAccountCache.delete_cache(platform, old_member.id)
            logger.info(
                f"Cleared proxy account cache for member {old_member.id} "
                f"(platform: {platform}, proxy_account: {instance.code})"
            )

    except ProviderProxyAccount.DoesNotExist:
        # 理論上不應該發生，但為了安全起見
        logger.warning(
            f"ProviderProxyAccount with pk={instance.pk} not found in signal handler"
        )
