"""Optional libheif fallback when the Pillow plugin is unavailable."""
import ctypes as C
from ctypes.util import find_library
from PIL import Image

class _Error(C.Structure):
    _fields_ = [('code', C.c_int), ('subcode', C.c_int), ('message', C.c_char_p)]

def decode(data: bytes, max_pixels: int):
    path = find_library('heif')
    if not path:
        raise RuntimeError('HEIC input requires pillow-heif (requirements-heic.txt) or system libheif.')
    lib = C.CDLL(path)
    P, I = C.c_void_p, C.c_int
    def bind(name, result, *args):
        f = getattr(lib, 'heif_' + name)
        f.restype, f.argtypes = result, args
        return f
    alloc = bind('context_alloc', P)
    free = bind('context_free', None, P)
    limit = bind('context_set_maximum_image_size_limit', None, P, I)
    read = bind('context_read_from_memory_without_copy', _Error, P, P, C.c_size_t, P)
    primary = bind('context_get_primary_image_handle', _Error, P, C.POINTER(P))
    release = bind('image_handle_release', None, P)
    width = bind('image_handle_get_width', I, P)
    height = bind('image_handle_get_height', I, P)
    alpha = bind('image_handle_has_alpha_channel', I, P)
    unpack = bind('decode_image', _Error, P, C.POINTER(P), I, I, P)
    image_release = bind('image_release', None, P)
    decoded_width = bind('image_get_width', I, P, I)
    decoded_height = bind('image_get_height', I, P, I)
    plane = bind('image_get_plane_readonly', P, P, I, C.POINTER(I))
    def check(err):
        if err.code:
            raise ValueError('libheif: ' + (err.message or b'decode failure').decode(errors='replace'))
    ctx, handle, image = alloc(), P(), P()
    if not ctx:
        raise RuntimeError('Could not allocate HEIC decoder.')
    try:
        limit(ctx, 12000)
        buffer = C.c_char_p(data)
        check(read(ctx, C.cast(buffer, P), len(data), None))
        check(primary(ctx, C.byref(handle)))
        w, h = width(handle), height(handle)
        if min(w, h) < 1 or w*h > max_pixels or max(w,h)>12000:
            raise ValueError('HEIC image exceeds pixel limit.')
        has_alpha = bool(alpha(handle))
        mode = 'RGBA' if has_alpha else 'RGB'
        check(unpack(handle, C.byref(image), 1, 11 if has_alpha else 10, None))
        w, h = decoded_width(image, 10), decoded_height(image, 10)
        stride = I()
        addr = plane(image, 10, C.byref(stride))
        if min(w,h)<1 or w*h>max_pixels or max(w,h)>12000 or not addr or stride.value < w*len(mode):
            raise ValueError('Invalid decoded HEIC dimensions.')
        return Image.frombytes(mode, (w,h), C.string_at(addr,stride.value*h), 'raw', mode, stride.value, 1)
    finally:
        if image: image_release(image)
        if handle: release(handle)
        free(ctx)
