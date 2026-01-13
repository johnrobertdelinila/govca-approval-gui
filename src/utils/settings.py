"""
Settings persistence for GovCA Approval Automation.
Stores user preferences like default domain.
"""

import json
import os

SETTINGS_FILE = os.path.expanduser("~/.govca_approval_settings.json")

# Complete list of GovCA domains
DOMAIN_LIST = [
    # NCR
    "NCR00Sign", "NCR00Auth",
    # CAR
    "CAR00Sign", "CAR00Auth",
    # Regions 1-13
    "Region1Sign", "Region1Auth",
    "Region2Sign", "Region2Auth",
    "Region3Sign", "Region3Auth",
    "Region4ASign", "Region4AAuth",
    "Region4BSign", "Region4BAuth",
    "Region5Sign", "Region5Auth",
    "Region6Sign", "Region6Auth",
    "Region7Sign", "Region7Auth",
    "Region8Sign", "Region8Auth",
    "Region9Sign", "Region9Auth",
    "Region10Sign", "Region10Auth",
    "Region11Sign", "Region11Auth",
    "Region12Sign", "Region12Auth",
    "Region13Sign", "Region13Auth",
    # BARMM
    "BARMMSign", "BARMMAuth",
    # Batch Sign domains
    "BatchSign", "BatchSignCAR",
    "BatchSignRegion1", "BatchSignRegion2", "BatchSignRegion3",
    "BatchSignRegion4A", "BatchSignRegion4B",
    "BatchSignRegion5", "BatchSignRegion6", "BatchSignRegion7",
    "BatchSignRegion8", "BatchSignRegion9", "BatchSignRegion10",
    "BatchSignRegion11", "BatchSignRegion12",
    # Special
    "MainSSLDomain", "PhilSignDomainSign", "TestCertificateSign",
]


def load_settings():
    """Load settings from file"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"default_domain": "NCR00Sign"}


def save_settings(settings):
    """Save settings to file"""
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except IOError:
        pass


def get_default_domain():
    """Get the default domain from settings"""
    return load_settings().get("default_domain", "NCR00Sign")


def set_default_domain(domain):
    """Set the default domain in settings"""
    settings = load_settings()
    settings["default_domain"] = domain
    save_settings(settings)
