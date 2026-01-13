# Core automation modules
try:
    from .bot import GovCAApprovalBot
    from .browser import find_firefox_profile, get_bundled_geckodriver
except ImportError:
    from bot import GovCAApprovalBot
    from browser import find_firefox_profile, get_bundled_geckodriver
