import ctypes
import os

# 路径完全由 Python 字面量控制,避免 shell 转义吃掉反斜杠。
# \\?\ 前缀让 Win32 跳过设备名解析,按字面路径处理。
prefix = "\\\\?\\"
plain = r"D:\project\technical-article-curation\nul"
bypass = prefix + plain

DeleteFileW = ctypes.windll.kernel32.DeleteFileW
DeleteFileW.argtypes = [ctypes.c_wchar_p]
DeleteFileW.restype = ctypes.c_bool

print("bypass path repr:", repr(bypass))
print("lexists before:", os.path.lexists(plain))

ok = DeleteFileW(bypass)
err = ctypes.windll.kernel32.GetLastError()
print("DeleteFileW ok=", ok, "last_error=", err)
print("lexists after:", os.path.lexists(plain))
