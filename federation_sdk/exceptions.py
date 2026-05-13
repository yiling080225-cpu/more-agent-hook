class FederationError(Exception):
    """SDK 所有异常的基类。"""
    pass


class ConnectionError(FederationError):
    """无法连接到 Gateway。"""
    pass


class TimeoutError(FederationError):
    """请求超时。"""
    pass


class NotFoundError(FederationError):
    """资源不存在 (404)。"""
    pass


class TaskFailedError(FederationError):
    """远程任务执行失败。"""
    pass


class ValidationError(FederationError):
    """参数校验失败。"""
    pass
