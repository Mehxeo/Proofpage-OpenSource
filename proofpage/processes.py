"""Check process liveness without sending a signal on Windows."""
import os


def check_process(pid):
    if not pid or pid < 0:
        raise ProcessLookupError(pid)
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
        except PermissionError:
            pass  # A process we cannot signal still exists.
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE, no terminate rights
    if not handle:
        error = ctypes.get_last_error()
        if error == 5:  # Access denied: conservatively consider it alive.
            return
        if error == 87:  # Invalid PID
            raise ProcessLookupError(pid)
        raise ctypes.WinError(error)
    try:
        state = kernel.WaitForSingleObject(handle, 0)
        if state == 0:
            raise ProcessLookupError(pid)
        if state != 258:  # WAIT_TIMEOUT: the process has not exited.
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        kernel.CloseHandle(handle)
