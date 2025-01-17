import socket


def get_ownip():
    local_addrs = socket.gethostbyname_ex(socket.gethostname())[-1]
    for addr in local_addrs:
        if not addr.startswith('127'):
            return addr
    return '127.0.0.1'


def get_hexid(byteid):
    if len(byteid) > 0:
        return byteid[1:].hex()
    return ''
