"""Read and parse occupied TCP and UDP ports using iproute2's ``ss`` tool."""

from __future__ import annotations

from dataclasses import dataclass
import re
import subprocess


SS_COMMAND = ("ss", "-H", "-lntup")


@dataclass(frozen=True, slots=True)
class PortEntry:
    protocol: str
    port: int
    address: str
    state: str
    process: str | None
    pid: int | None

    @property
    def process_label(self) -> str:
        if self.process and self.pid is not None:
            return f"{self.process}  ·  PID {self.pid}"
        if self.process:
            return self.process
        return "Process hidden"


class ScanError(RuntimeError):
    """Raised when the system socket scan cannot be completed."""


_PROCESS_RE = re.compile(
    r'\("(?P<name>(?:\\.|[^"\\])*)",pid=(?P<pid>\d+),fd=\d+'
)


def _parse_endpoint(endpoint: str) -> tuple[str, int] | None:
    """Return a display address and port from an ss endpoint."""
    if ":" not in endpoint:
        return None

    address, raw_port = endpoint.rsplit(":", 1)
    try:
        port = int(raw_port)
    except ValueError:
        return None

    # ss wraps the IPv6 portion in brackets and can then append a scope such
    # as ``%wlan0`` outside the closing bracket.
    if address.startswith("[") and "]" in address:
        bracket = address.index("]")
        address = address[1:bracket] + address[bracket + 1 :]

    display_address = {
        "0.0.0.0": "All interfaces (IPv4)",
        "::": "All interfaces (IPv6)",
        "*": "All interfaces",
    }.get(address, address)
    return display_address, port


def _parse_process(raw: str) -> tuple[str | None, int | None]:
    match = _PROCESS_RE.search(raw)
    if not match:
        return None, None
    name = bytes(match.group("name"), "utf-8").decode("unicode_escape")
    return name, int(match.group("pid"))


def parse_ss_output(output: str) -> list[PortEntry]:
    """Parse the stable, numeric output produced by ``ss -H -lntup``."""
    entries: list[PortEntry] = []
    for line in output.splitlines():
        columns = line.split(maxsplit=6)
        if len(columns) < 6:
            continue

        protocol, raw_state = columns[0].lower(), columns[1].upper()
        if protocol not in {"tcp", "udp"}:
            continue

        endpoint = _parse_endpoint(columns[4])
        if endpoint is None:
            continue
        address, port = endpoint
        process, pid = _parse_process(columns[6] if len(columns) == 7 else "")

        if protocol == "tcp":
            state = "Listening" if raw_state == "LISTEN" else raw_state.title()
        else:
            state = "Bound"

        entries.append(
            PortEntry(
                protocol=protocol.upper(),
                port=port,
                address=address,
                state=state,
                process=process,
                pid=pid,
            )
        )

    return sorted(
        entries,
        key=lambda item: (item.port, item.protocol, item.address, item.pid or -1),
    )


def scan_ports(as_admin: bool = False, timeout: int = 15) -> list[PortEntry]:
    """Run a socket scan. Admin mode delegates authentication to polkit."""
    command = (*(("pkexec",) if as_admin else ()), *SS_COMMAND)
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        missing = "pkexec" if as_admin else "ss"
        raise ScanError(f"Required command ‘{missing}’ was not found.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ScanError("The port scan timed out.") from exc

    if result.returncode != 0:
        detail = result.stderr.strip()
        if as_admin and result.returncode in {126, 127}:
            detail = "Administrator authentication was cancelled."
        raise ScanError(detail or "The port scan could not be completed.")

    return parse_ss_output(result.stdout)
