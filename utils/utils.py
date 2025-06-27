import importlib


def get_class_from_path(path):
    module_path, class_name = path.rsplit('.', 1)
    module = importlib.import_module(module_path)
    handler_class = getattr(module, class_name)
    return handler_class
