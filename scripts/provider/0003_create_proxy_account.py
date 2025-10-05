from provider.models import Provider, ProviderProxyAccount, ProviderProxyAccountAPIToken
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        # 找到測試專用的 provider (familiarity-playlist1)
        try:
            test_provider = Provider.objects.get(code='familiarity-playlist1')
        except Provider.DoesNotExist:
            print(
                "❌ Test provider 'familiarity-playlist1' not found. Please run provider creation scripts first."
            )
            return

        print(
            f"📋 Creating proxy account for test provider: {test_provider.name} ({test_provider.code})"
        )

        proxy_account_code = 'pony_test_proxy_1'

        # 檢查是否已經存在
        if ProviderProxyAccount.objects.filter(code=proxy_account_code).exists():
            print(f"⚠️  Proxy account {proxy_account_code} already exists")
            return

        # 創建 ProviderProxyAccount
        proxy_account = ProviderProxyAccount.objects.create(
            name='Pony Test Proxy Account',
            code=proxy_account_code,
            provider=test_provider,
            is_active=True,
            description='Test proxy account for playback control',
        )

        # 創建對應的 ProviderProxyAccountAPIToken（先不設定 token，等手動補）
        proxy_token = ProviderProxyAccountAPIToken.objects.create(
            proxy_account=proxy_account,
            _access_token='',  # 空的，等手動設定
            _refresh_token='',  # 空的，等手動設定
            expires_at=None,  # 等手動設定
        )

        print(f"✅ Created proxy account: {proxy_account_code}")
        print(f"   - Name: {proxy_account.name}")
        print(f"   - Provider: {test_provider.name}")
        print(f"   - Proxy Account ID: {proxy_account.id}")
        print(f"   - Token ID: {proxy_token.id}")

        print(f"\n📋 Next steps:")
        print(
            '1. Use Django admin or shell to set access_token and refresh_token for the ProviderProxyAccountAPIToken'
        )
        print('2. Set proper expires_at datetime')
        print(f"\nTo set token manually:")
        print(f"token = ProviderProxyAccountAPIToken.objects.get(id={proxy_token.id})")
        print("token.access_token = 'your_access_token_here'")
        print("token.refresh_token = 'your_refresh_token_here'")
        print('token.expires_at = timezone.now() + timezone.timedelta(hours=1)')
        print('token.save()')
