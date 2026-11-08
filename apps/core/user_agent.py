"""
Zero-dependency User-Agent string parser for activity logs.
Extracts browser name, major version, operating system, and device type.
"""
import re


def parse_user_agent(ua_string: str | None) -> dict:
    if not ua_string or not isinstance(ua_string, str):
        return {
            "browser_name": "Unknown",
            "browser_version": "",
            "os_name": "Unknown",
            "device_type": "Unknown",
        }

    ua = ua_string.strip()
    lower_ua = ua.lower()

    # 1. Device Type
    device_type = "Unknown"
    if "ipad" in lower_ua or "tablet" in lower_ua or ("android" in lower_ua and "mobile" not in lower_ua):
        device_type = "Tablet"
    elif any(kw in lower_ua for kw in ("mobile", "iphone", "ipod", "android", "blackberry", "webos", "windows phone")):
        device_type = "Mobile"
    elif any(kw in lower_ua for kw in ("windows", "macintosh", "mac os", "linux", "cros", "x11")):
        device_type = "Desktop"

    # 2. Operating System
    os_name = "Unknown"
    if "windows nt 10.0" in lower_ua:
        os_name = "Windows"
    elif "windows nt 6.3" in lower_ua:
        os_name = "Windows 8.1"
    elif "windows nt 6.2" in lower_ua:
        os_name = "Windows 8"
    elif "windows nt 6.1" in lower_ua:
        os_name = "Windows 7"
    elif "windows nt" in lower_ua:
        os_name = "Windows"
    elif "iphone" in lower_ua or "ipad" in lower_ua or "ipod" in lower_ua:
        os_match = re.search(r"os\s+([\d_]+)", lower_ua)
        os_version = os_match.group(1).replace("_", ".") if os_match else ""
        os_name = f"iOS {os_version}".strip() if os_version else "iOS"
    elif "mac os x" in lower_ua or "macintosh" in lower_ua:
        os_match = re.search(r"mac os x\s+([\d_]+)", lower_ua)
        os_version = os_match.group(1).replace("_", ".") if os_match else ""
        os_name = f"macOS {os_version}".strip() if os_version else "macOS"
    elif "android" in lower_ua:
        os_match = re.search(r"android\s+([\d.]+)", lower_ua)
        os_version = os_match.group(1) if os_match else ""
        os_name = f"Android {os_version}".strip() if os_version else "Android"
    elif "cros" in lower_ua:
        os_name = "ChromeOS"
    elif "linux" in lower_ua:
        os_name = "Linux"

    # If device_type is still Unknown but OS was identified
    if device_type == "Unknown":
        if os_name in ("Windows", "macOS", "Linux", "ChromeOS"):
            device_type = "Desktop"
        elif "Android" in os_name or "iOS" in os_name:
            device_type = "Mobile"

    # 3. Browser & Version
    browser_name = "Unknown"
    browser_version = ""

    # Known specialized clients first
    if "postmanruntime" in lower_ua:
        browser_name = "Postman"
        match = re.search(r"postmanruntime/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "curl" in lower_ua:
        browser_name = "curl"
        match = re.search(r"curl/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "python-requests" in lower_ua:
        browser_name = "Python Requests"
        match = re.search(r"python-requests/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "edg/" in lower_ua or "edge/" in lower_ua:
        browser_name = "Edge"
        match = re.search(r"edg(?:e)?/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "opr/" in lower_ua or "opera" in lower_ua:
        browser_name = "Opera"
        match = re.search(r"(?:opr|opera)/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "samsungbrowser/" in lower_ua:
        browser_name = "Samsung Internet"
        match = re.search(r"samsungbrowser/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "chrome/" in lower_ua or "crios/" in lower_ua:
        browser_name = "Chrome"
        match = re.search(r"(?:chrome|crios)/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "firefox/" in lower_ua or "fxios/" in lower_ua:
        browser_name = "Firefox"
        match = re.search(r"(?:firefox|fxios)/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "safari/" in lower_ua and "version/" in lower_ua:
        browser_name = "Safari"
        match = re.search(r"version/([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]
    elif "trident/" in lower_ua or "msie" in lower_ua:
        browser_name = "Internet Explorer"
        match = re.search(r"(?:msie\s+|rv:)([\d.]+)", lower_ua)
        if match:
            browser_version = match.group(1).split(".")[0]

    return {
        "browser_name": browser_name,
        "browser_version": browser_version,
        "os_name": os_name,
        "device_type": device_type,
    }
