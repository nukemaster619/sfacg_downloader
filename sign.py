import hashlib

from config import DEVICE_TOKEN, SALT

def get_sign(nonce: str, timestamp: int, device_token: str = DEVICE_TOKEN, salt: str = SALT) -> str:
    long_nonce = (nonce * 4).encode("ascii")
    def index_calc(index: int) -> int:
        value = long_nonce[index]
        return value - (value // 0x24) * 0x24
    offset1 = index_calc(1)
    offset2 = index_calc(2)
    offset3 = index_calc(3)
    offset4 = index_calc(4)
    nonce_reorder = (
        long_nonce[offset1:offset1 + 13]
        + long_nonce[offset2:offset2 + 16]
        + long_nonce[offset3:offset3 + 36]
        + long_nonce[offset4:offset4 + 36]
    )
    auth_string = (str(timestamp) + salt + device_token + nonce).encode("ascii")
    result = "".join(chr((auth_string[index] + nonce_reorder[index]) >> 1) for index in range(101))
    lengths = [13, 16, 36, 36]
    a = result[0:lengths[0]]
    b = result[lengths[0]:lengths[0] + lengths[1]]
    c = result[lengths[0] + lengths[1]:lengths[0] + lengths[1] + lengths[2]]
    d = result[lengths[0] + lengths[1] + lengths[2]:]
    reordered = d + a + c + b
    final_chars: list[str] = []
    for char in reordered:
        code = ord(char)
        if code < 0x30:
            shifted = code + 19
            final_chars.append(chr(0x39 if 0x39 < shifted < 0x41 else shifted))
        elif 0x39 < code < 0x41:
            final_chars.append(chr(code + 19))
        elif 0x5A < code < 0x61:
            final_chars.append(chr(code + 19))
        else:
            final_chars.append(char)
    return hashlib.md5("".join(final_chars).encode("utf-8")).hexdigest().upper()
