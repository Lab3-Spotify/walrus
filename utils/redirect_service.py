from urllib.parse import urlencode

from django.shortcuts import redirect

from walrus import settings


class RedirectService:
    """重定向服務類，提供統一的重定向方法"""

    @staticmethod
    def redirect(url, **params):
        """
        重定向到指定 URL，支援查詢參數

        Args:
            url (str): 目標 URL
            **params: 查詢參數

        Returns:
            HttpResponseRedirect: Django 重定向響應
        """
        if params:
            query_string = urlencode(params)
            url = f"{url}?{query_string}"
        return redirect(url)

    @staticmethod
    def redirect_to_frontend(path, **params):
        """
        重定向到前端頁面

        Args:
            path (str): 前端路徑（不包含域名）
            **params: 查詢參數

        Returns:
            HttpResponseRedirect: Django 重定向響應
        """
        full_url = f"{settings.HERON_BASE_URL}{path}"
        return RedirectService.redirect(full_url, **params)

    @staticmethod
    def spotify_callback(status=None, error=None):
        """
        重定向到 Spotify 回調頁面

        Args:
            status (str, optional): 授權狀態 ('success', 'failed')
            error (str, optional): 錯誤類型

        Returns:
            HttpResponseRedirect: Django 重定向響應
        """
        if error:
            return RedirectService.redirect_to_frontend(
                '/spotify-callback', error=error
            )
        return RedirectService.redirect_to_frontend(
            '/spotify-callback', **{'auth-status': status}
        )
