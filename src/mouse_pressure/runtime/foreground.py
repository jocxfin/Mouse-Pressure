"""Read the foreground application without retaining process handles."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import PureWindowsPath


def foreground_executable() -> str | None:
    user = ctypes.windll.user32
    kernel = ctypes.windll.kernel32
    user.GetForegroundWindow.restype = wintypes.HWND
    user.GetWindowThreadProcessId.argtypes = [
        wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
    ]
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]

    hwnd = user.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value or pid.value == os.getpid():
        return None
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if not handle:
        return None
    try:
        buffer = ctypes.create_unicode_buffer(2048)
        length = wintypes.DWORD(len(buffer))
        if not kernel.QueryFullProcessImageNameW(
            handle, 0, buffer, ctypes.byref(length)
        ):
            return None
        return PureWindowsPath(buffer.value).name.casefold()
    finally:
        kernel.CloseHandle(handle)


def mouse_buttons_down() -> bool:
    user = ctypes.windll.user32
    return any(user.GetAsyncKeyState(key) & 0x8000 for key in (0x01, 0x02))
