import socket
import sys
import argparse

HOST = '127.0.0.1'
PORT = 8888
WRAM_SIZE = 32768
WRAM_START = 0xC000

def get_wram():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect((HOST, PORT))
        s.sendall(b'\x01')
        chunks = []
        bytes_recd = 0
        while bytes_recd < WRAM_SIZE:
            chunk = s.recv(min(WRAM_SIZE - bytes_recd, 4096))
            if not chunk: break
            chunks.append(chunk)
            bytes_recd += len(chunk)
        s.close()
        return b''.join(chunks)
    except Exception as e:
        print(f"Error connecting to emulator: {e}")
        sys.exit(1)

def offset_to_addr(offset):
    # Standard GBC WRAM mapping used in Client
    if 0 <= offset < 0x1000:
        return offset + 0xC000
    elif 0x1000 <= offset < 0x2000:
        return (offset - 0x1000) + 0xD000
    return offset # Banks or other regions if any

def main():
    parser = argparse.ArgumentParser(description='Find hex patterns in emulator WRAM')
    parser.add_argument('hex_string', help='Hex string to search for (e.g., "53" or "53512F")')
    parser.add_argument('--context', type=int, default=8, help='Number of bytes of context to show')
    args = parser.parse_args()

    try:
        pattern = bytes.fromhex(args.hex_string)
    except ValueError:
        print("Invalid hex string. Please use format like \"53\" or \"53512F\"")
        return

    print(f"Searching for pattern: {pattern.hex(' ').upper()}")
    data = get_wram()
    print(f"Captured {len(data)} bytes of WRAM.")

    count = 0
    idx = data.find(pattern)
    while idx != -1:
        addr = offset_to_addr(idx)
        start_ctx = max(0, idx - args.context)
        end_ctx = min(len(data), idx + len(pattern) + args.context)
        
        ctx_bytes = data[start_ctx:end_ctx]
        ctx_hex = ctx_bytes.hex(' ').upper()
        
        # Highlight pattern in context
        pattern_hex = pattern.hex(' ').upper()
        highlighted = ctx_hex.replace(pattern_hex, f"[{pattern_hex}]")
        
        print(f"Found at GBC Address: {hex(addr)} (Offset: {hex(idx)})")
        print(f"  Context: ... {highlighted} ...")
        
        count += 1
        idx = data.find(pattern, idx + 1)

    print(f"\nTotal matches found: {count}")

if __name__ == '__main__':
    main()
