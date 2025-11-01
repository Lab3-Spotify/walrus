from django.contrib import admin

from .models import MemberAPIToken, ProviderProxyAccount, ProviderProxyAccountAPIToken


@admin.register(MemberAPIToken)
class MemberAPITokenAdmin(admin.ModelAdmin):
    list_display = ('member', 'provider', 'expires_at', 'created_at', 'updated_at')
    list_filter = ('provider', 'created_at')
    search_fields = ('member__username', 'member__email', 'provider__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(ProviderProxyAccount)
class ProviderProxyAccountAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'code',
        'provider',
        'current_member',
        'is_active',
        'created_at',
    )
    list_filter = ('provider', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'current_member__username')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ProviderProxyAccountAPIToken)
class ProviderProxyAccountAPITokenAdmin(admin.ModelAdmin):
    list_display = ('proxy_account', 'expires_at', 'created_at', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('proxy_account__name', 'proxy_account__code')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
