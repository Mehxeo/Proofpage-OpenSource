"""Ed25519 signatures (RFC 8032) using only the Python standard library.

This follows the RFC's reference algorithm. It is deterministic but not constant-time, which is acceptable for a
signing key used by one local workspace; when the `cryptography` package is installed it is used instead and
produces identical signatures.
"""
import hashlib

P = 2 ** 255 - 19
L = 2 ** 252 + 27742317777372353535851937790883648493
D = -121665 * pow(121666, P - 2, P) % P
SQRT_M1 = pow(2, (P - 1) // 4, P)


def _sha512_int(data):
    return int.from_bytes(hashlib.sha512(data).digest(), 'little')


def _add(a, b):
    x = (a[1] - a[0]) * (b[1] - b[0]) % P
    y = (a[1] + a[0]) * (b[1] + b[0]) % P
    t = 2 * a[3] * b[3] * D % P
    z = 2 * a[2] * b[2] % P
    e, f, g, h = y - x, z - t, z + t, y + x
    return (e * f % P, g * h % P, f * g % P, e * h % P)


def _multiply(scalar, point):
    result = (0, 1, 1, 0)
    while scalar:
        if scalar & 1:
            result = _add(result, point)
        point = _add(point, point)
        scalar >>= 1
    return result


def _equal(a, b):
    return (a[0] * b[2] - b[0] * a[2]) % P == 0 and (a[1] * b[2] - b[1] * a[2]) % P == 0


def _recover_x(y, sign):
    if y >= P:
        return None
    x2 = (y * y - 1) * pow(D * y * y + 1, P - 2, P) % P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (P + 3) // 8, P)
    if (x * x - x2) % P:
        x = x * SQRT_M1 % P
    if (x * x - x2) % P:
        return None
    return P - x if (x & 1) != sign else x


_GY = 4 * pow(5, P - 2, P) % P
_GX = _recover_x(_GY, 0)
G = (_GX, _GY, 1, _GX * _GY % P)


def _compress(point):
    inverse = pow(point[2], P - 2, P)
    x, y = point[0] * inverse % P, point[1] * inverse % P
    return (y | ((x & 1) << 255)).to_bytes(32, 'little')


def _decompress(data):
    if len(data) != 32:
        return None
    y = int.from_bytes(data, 'little')
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % P)


def _expand(seed):
    if len(seed) != 32:
        raise ValueError('Ed25519 private keys are 32 bytes.')
    digest = hashlib.sha512(seed).digest()
    scalar = int.from_bytes(digest[:32], 'little')
    scalar &= (1 << 254) - 8
    scalar |= 1 << 254
    return scalar, digest[32:]


def _library():
    try:
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization
        return ed25519, serialization
    except ImportError:
        return None


def public_key(seed):
    library = _library()
    if library:
        ed25519, serialization = library
        key = ed25519.Ed25519PrivateKey.from_private_bytes(seed).public_key()
        return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    scalar, _ = _expand(seed)
    return _compress(_multiply(scalar, G))


def sign(seed, message):
    library = _library()
    if library:
        return library[0].Ed25519PrivateKey.from_private_bytes(seed).sign(message)
    scalar, prefix = _expand(seed)
    public = _compress(_multiply(scalar, G))
    r = _sha512_int(prefix + message) % L
    encoded_r = _compress(_multiply(r, G))
    h = _sha512_int(encoded_r + public + message) % L
    return encoded_r + ((r + h * scalar) % L).to_bytes(32, 'little')


def verify(public, message, signature):
    if len(public) != 32 or len(signature) != 64:
        return False
    point = _decompress(public)
    r = _decompress(signature[:32])
    s = int.from_bytes(signature[32:], 'little')
    if point is None or r is None or s >= L:
        return False
    h = _sha512_int(signature[:32] + public + message) % L
    return _equal(_multiply(s, G), _add(r, _multiply(h, point)))
