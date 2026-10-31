"""Find a Reachy Mini daemon on the laptop's local network."""

from concurrent.futures import ThreadPoolExecutor, as_completed
import ipaddress
import json
import os
import socket
from urllib.request import urlopen


def _robot_status(host, timeout=0.7):
    try:
        with urlopen(f"http://{host}:8000/api/daemon/status", timeout=timeout) as response:
            return json.load(response).get("robot_name") == "reachy_mini"
    except (OSError, ValueError, TimeoutError):
        return False


def _local_ipv4():
    # A UDP connect selects the active route without sending a packet.
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]


def resolve_robot_host(explicit=None):
    """Return (host, source); explicit > REACHY_HOST > private .local > /24 scan."""
    if explicit:
        return explicit, "--host"
    if os.environ.get("REACHY_HOST", "").strip():
        return os.environ["REACHY_HOST"].strip(), "REACHY_HOST"

    try:
        addresses = socket.getaddrinfo("reachy-mini.local", 8000, family=socket.AF_INET)
        if any(ipaddress.ip_address(item[4][0]).is_private for item in addresses):
            return "reachy-mini.local", "로컬 이름"
    except OSError:
        pass

    try:
        local = ipaddress.ip_address(_local_ipv4())
        subnet = ipaddress.ip_network(f"{local}/24", strict=False)
    except (OSError, ValueError) as exc:
        raise RuntimeError("노트북의 로컬 IPv4 주소를 찾지 못했습니다") from exc

    hosts = (str(ip) for ip in subnet.hosts() if ip != local)
    with ThreadPoolExecutor(max_workers=64) as pool:
        futures = {pool.submit(_robot_status, host): host for host in hosts}
        for future in as_completed(futures):
            if future.result():
                host = futures[future]
                pool.shutdown(wait=False, cancel_futures=True)
                return host, f"{subnet} 검색"
    raise RuntimeError(f"{subnet}에서 Reachy Mini 데몬을 찾지 못했습니다")
