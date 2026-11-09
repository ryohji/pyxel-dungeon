"""Keep the keyboard in plain Latin input while the game window is in front.

With a Japanese (or other composing) input method switched on, held keys
such as W and Shift pile up in an invisible, never-committed composition
and the game slows to a crawl. Pyxel has no setting for this, so:

  macOS    switch to the ASCII-capable input source while the game app is
           active, and put the player's own source back when it is not
           (or when the game ends).
  Windows  detach the input method from the game window, and reattach it
           when the game ends. (Not tested here.)
  others   nothing (Linux input methods vary; the Web build is the
           browser's business).

Every call is best effort: if anything is missing, it quietly does nothing.
"""

import atexit
import ctypes
import ctypes.util
import sys


class _Mac:
    def __init__(self):
        carbon = ctypes.cdll.LoadLibrary(ctypes.util.find_library("Carbon"))
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
        vp = ctypes.c_void_p
        for name in ("TISCopyCurrentKeyboardInputSource", "TISCopyCurrentASCIICapableKeyboardInputSource"):
            getattr(carbon, name).restype = vp
        carbon.TISGetInputSourceProperty.restype = vp
        carbon.TISGetInputSourceProperty.argtypes = [vp, vp]
        carbon.TISSelectInputSource.argtypes = [vp]
        cf.CFRelease.argtypes = [vp]
        cf.CFRetain.argtypes = [vp]
        cf.CFRetain.restype = vp
        objc.objc_getClass.restype = vp
        objc.objc_getClass.argtypes = [ctypes.c_char_p]
        objc.sel_registerName.restype = vp
        objc.sel_registerName.argtypes = [ctypes.c_char_p]
        send_obj = ctypes.CFUNCTYPE(vp, vp, vp)(("objc_msgSend", objc))
        send_bool = ctypes.CFUNCTYPE(ctypes.c_bool, vp, vp)(("objc_msgSend", objc))
        app = send_obj(objc.objc_getClass(b"NSApplication"), objc.sel_registerName(b"sharedApplication"))
        is_active = objc.sel_registerName(b"isActive")

        self.carbon, self.cf = carbon, cf
        self.ascii_key = vp.in_dll(carbon, "kTISPropertyInputSourceIsASCIICapable")
        self.true = vp.in_dll(cf, "kCFBooleanTrue")
        self.active = lambda: bool(app) and send_bool(app, is_active)
        self.saved = None  # the player's own source while we hold ASCII

    def _is_ascii(self, src):
        return self.carbon.TISGetInputSourceProperty(src, self.ascii_key) == self.true.value

    def tick(self):
        if self.active():
            cur = self.carbon.TISCopyCurrentKeyboardInputSource()
            if cur and not self._is_ascii(cur):
                if self.saved is None:
                    self.saved = cur  # keep our reference: we hand it back later
                else:
                    self.cf.CFRelease(cur)  # switched back mid-game: just undo it again
                ascii_src = self.carbon.TISCopyCurrentASCIICapableKeyboardInputSource()
                if ascii_src:
                    self.carbon.TISSelectInputSource(ascii_src)
                    self.cf.CFRelease(ascii_src)
            elif cur:
                self.cf.CFRelease(cur)
        else:
            self.restore()

    def restore(self):
        if self.saved is not None:
            self.carbon.TISSelectInputSource(self.saved)
            self.cf.CFRelease(self.saved)
            self.saved = None


class _Windows:
    def __init__(self, title):
        user32 = ctypes.windll.user32
        imm32 = ctypes.windll.imm32
        user32.FindWindowW.restype = ctypes.c_void_p
        imm32.ImmAssociateContext.restype = ctypes.c_void_p
        imm32.ImmAssociateContext.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        self.find = lambda: user32.FindWindowW(None, title)
        self.imm32 = imm32
        self.hwnd = None
        self.saved = None

    def tick(self):
        if self.hwnd is None:
            self.hwnd = self.find()
            if self.hwnd:
                self.saved = self.imm32.ImmAssociateContext(self.hwnd, None)

    def restore(self):
        if self.hwnd and self.saved:
            self.imm32.ImmAssociateContext(self.hwnd, self.saved)
            self.saved = None


class LatinInput:
    """Call tick() about once a second from the game loop."""

    def __init__(self, title):
        self.impl = None
        try:
            if sys.platform == "darwin":
                self.impl = _Mac()
            elif sys.platform == "win32":
                self.impl = _Windows(title)
        except Exception:
            self.impl = None
        if self.impl is not None:
            atexit.register(self.restore)

    def tick(self):
        if self.impl is None:
            return
        try:
            self.impl.tick()
        except Exception:
            self.impl = None

    def restore(self):
        if self.impl is None:
            return
        try:
            self.impl.restore()
        except Exception:
            pass
