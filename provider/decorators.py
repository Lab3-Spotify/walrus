from functools import wraps


def member_only(func):
    """
    裝飾器：限制方法只能由 member accounts 使用

    Usage:
        @member_only
        def some_method(self):
            pass
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'member') or not self.member:
            raise ValueError(f"{func.__name__} is only available for member accounts")
        return func(self, *args, **kwargs)

    return wrapper


def proxy_account_only(func):
    """
    裝飾器：限制方法只能由 proxy accounts 使用

    Usage:
        @proxy_only
        def some_method(self):
            pass
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'proxy_account') or not self.proxy_account:
            raise ValueError(f"{func.__name__} is only available for proxy accounts")
        return func(self, *args, **kwargs)

    return wrapper
