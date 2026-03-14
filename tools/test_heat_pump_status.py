#!/usr/bin/env python3
"""
Standalone diagnostic script for LocalTuya Heat Pump connection issues.

Usage:
    python tools/test_heat_pump_status.py --host 192.168.68.52 \\
        --device-id bff61d6d17fb8a70daxn4y --local-key "YOUR_KEY"
    python tools/test_heat_pump_status.py --host 192.168.68.52 \\
        --device-id xxx --local-key xxx --ports 6668,6669,8681 --versions 3.3,3.4

Run from project root. Requires: pip install cryptography
"""
import argparse
import asyncio
import importlib.util
import logging
import sys
from pathlib import Path

# Load pytuya directly without homeassistant (avoids homeassistant dependency)
try:
    _pytuya_path = (
        Path(__file__).resolve().parent.parent
        / "custom_components"
        / "localtuya"
        / "pytuya"
        / "__init__.py"
    )
    _spec = importlib.util.spec_from_file_location("pytuya", _pytuya_path)
    pytuya = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(pytuya)
except ModuleNotFoundError as e:
    print(f"Missing dependency: {e}. Run: pip install cryptography")
    sys.exit(1)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
_LOGGER = logging.getLogger("test_heat_pump")


async def test_connection(host, device_id, local_key, port, version, timeout=5):
    """Try connecting and fetching status on a single port/version."""
    _LOGGER.info(
        "Trying host=%s port=%s version=%s device_id=%s",
        host,
        port,
        version,
        device_id[:8] + "..." + device_id[-4:] if len(device_id) > 12 else device_id,
    )
    try:
        protocol = await pytuya.connect(
            host,
            device_id,
            local_key,
            float(version),
            enable_debug=True,
            port=port,
            timeout=timeout,
        )
        _LOGGER.info("Connected on port %s, fetching status...", port)
        status = await protocol.status()
        await protocol.close()
        _LOGGER.info("Status: %s", status)
        return status
    except (ConnectionRefusedError, ConnectionResetError, OSError) as ex:
        _LOGGER.warning("Connection failed on port %s: %s", port, ex)
        raise
    except asyncio.TimeoutError as ex:
        _LOGGER.warning("Timeout on port %s: %s", port, ex)
        raise
    except Exception as ex:
        _LOGGER.exception("Unexpected error: %s", ex)
        raise


async def main():
    parser = argparse.ArgumentParser(description="Test Tuya device connection")
    parser.add_argument("--host", required=True, help="Device IP address")
    parser.add_argument("--device-id", required=True, help="Tuya device ID")
    parser.add_argument("--local-key", required=True, help="Tuya local key")
    parser.add_argument(
        "--ports",
        default="6668,6669,8681",
        help="Comma-separated ports to try (default: 6668,6669,8681)",
    )
    parser.add_argument(
        "--versions",
        default="3.4",
        help="Comma-separated protocol versions (default: 3.4)",
    )
    parser.add_argument("--timeout", type=int, default=5, help="Connection timeout")
    args = parser.parse_args()

    ports = [int(p.strip()) for p in args.ports.split(",")]
    versions = [v.strip() for v in args.versions.split(",")]

    last_error = None
    for version in versions:
        for port in ports:
            try:
                status = await test_connection(
                    args.host,
                    args.device_id,
                    args.local_key,
                    port,
                    version,
                    args.timeout,
                )
                _LOGGER.info(
                    "SUCCESS: Connected on port %s with version %s. DPS: %s",
                    port,
                    version,
                    status,
                )
                return 0
            except (ConnectionRefusedError, ConnectionResetError, OSError) as ex:
                last_error = ex
                continue
            except asyncio.TimeoutError as ex:
                last_error = ex
                continue

    _LOGGER.error("All attempts failed. Last error: %s", last_error)
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
