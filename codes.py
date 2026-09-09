"""邀请码生成工具。"""

import random
import string

# 去掉容易看错的字符：0/O/1/I/L
ALPHABET = "".join(c for c in string.ascii_uppercase + string.digits if c not in "0O1IL")


def gen_invite_code(length: int = 8, exists=None) -> str:
    """生成一个不重复的邀请码。exists 为判断重复的回调。"""
    for _ in range(50):
        code = "".join(random.choice(ALPHABET) for _ in range(length))
        if exists is None or not exists(code):
            return code
    # 极端情况下兜底
    return "".join(random.choice(ALPHABET) for _ in range(length + 4))
