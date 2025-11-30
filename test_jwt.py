try:
    import jwt
    print("JWT模块导入成功")
except ImportError:
    print("JWT模块导入失败")
    raise