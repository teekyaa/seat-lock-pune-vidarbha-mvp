import secrets

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L


def short_code(length=6):
    return "".join(secrets.choice(ALPHABET) for _ in range(length))
