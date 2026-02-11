"""
GovCA Approval Bot - Core automation logic.
Refactored for GUI integration with callback-based logging and progress reporting.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
import threading
import shutil
import tempfile
import os
from datetime import datetime

# Handle imports for both package and direct execution
try:
    from .browser import find_firefox_profile, get_bundled_geckodriver
except ImportError:
    from browser import find_firefox_profile, get_bundled_geckodriver

# Import wakepy for sleep prevention (optional dependency)
try:
    from wakepy import keep
    WAKEPY_AVAILABLE = True
except ImportError:
    WAKEPY_AVAILABLE = False


class DummyContext:
    """No-op context manager used when wakepy is not installed"""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


class OperationCancelledException(Exception):
    """Raised when user cancels the operation"""
    pass


class GovCAApprovalBot:
    """
    Core automation bot for GovCA approval processes.
    Supports callback-based logging and progress reporting for GUI integration.
    """

    def __init__(self, firefox_profile_path=None, log_callback=None, progress_callback=None, cancel_event=None, auth_method=None):
        """
        Initialize the bot with optional GUI callbacks.

        Args:
            firefox_profile_path: Path to Firefox profile (auto-detected if None)
            log_callback: Function to call for logging (message, level)
            progress_callback: Function to call for progress updates (current, total, message)
            cancel_event: threading.Event to signal cancellation
            auth_method: Authentication method - "Soft Token (Select Certificate)" or "Thales Token (Hardware)"
        """
        self.driver = None
        self.wait = None
        self.firefox_profile_path = firefox_profile_path
        self.log_callback = log_callback or self._default_log
        self.progress_callback = progress_callback or (lambda *args: None)
        self.cancel_event = cancel_event or threading.Event()
        self.auth_method = auth_method or "Soft Token (Select Certificate)"

    def _default_log(self, message, level="INFO"):
        """Default logging to console"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def log(self, message, level="INFO"):
        """Log a message through the callback"""
        self.log_callback(message, level)

    def check_cancelled(self):
        """Check if operation was cancelled and raise exception if so"""
        if self.cancel_event.is_set():
            raise OperationCancelledException("Operation cancelled by user")

    def interruptible_sleep(self, seconds):
        """Sleep that checks cancel_event every 0.5s."""
        elapsed = 0.0
        while elapsed < seconds:
            self.check_cancelled()
            wait_time = min(0.5, seconds - elapsed)
            if self.cancel_event.wait(wait_time):
                raise OperationCancelledException("Operation cancelled by user")
            elapsed += wait_time

    def cancellable_wait(self, timeout, condition, message=""):
        """WebDriverWait that checks cancel_event every 2s between attempts."""
        elapsed = 0.0
        while elapsed < timeout:
            self.check_cancelled()
            wait_time = min(2, timeout - elapsed)
            try:
                return WebDriverWait(self.driver, wait_time).until(condition)
            except TimeoutException:
                elapsed += wait_time
        raise TimeoutException(message or f"Timed out after {timeout}s")

    def report_progress(self, current, total, message="", phase=None, total_phases=None, phase_label=None):
        """Report progress through the callback with optional phase info"""
        self.progress_callback(current, total, message, phase, total_phases, phase_label)

    def wait_for_page_ready(self, timeout=30):
        """Wait for page to be fully loaded (document ready + no pending AJAX)"""
        def page_is_ready(driver):
            script = """
            // Check document ready state
            if (document.readyState !== 'complete') return false;

            // Check for jQuery AJAX (if present)
            if (typeof jQuery !== 'undefined' && jQuery.active > 0) return false;

            // Check for any DataTables processing
            var processing = document.querySelector('.dataTables_processing');
            if (processing && processing.style.display !== 'none' &&
                window.getComputedStyle(processing).display !== 'none') return false;

            return true;
            """
            return driver.execute_script(script)

        self.check_cancelled()
        self.cancellable_wait(timeout, page_is_ready, "Page did not become ready")

    def _get_table_fingerprint(self):
        """Get a fingerprint of the table content to detect when data actually changes"""
        script = """
        try {
            var fingerprint = {
                checkbox_count: 0,
                first_row_text: '',
                last_row_text: '',
                total_text_length: 0
            };

            // Get all checkbox rows
            var checkboxes = document.querySelectorAll('input.chkBatch[name="chkBatch"], input[type="checkbox"][name="chkBatch"]');
            fingerprint.checkbox_count = checkboxes.length;

            if (checkboxes.length > 0) {
                // Get first row text
                var firstRow = checkboxes[0].closest('tr');
                if (firstRow) {
                    fingerprint.first_row_text = firstRow.innerText.substring(0, 100);
                }

                // Get last row text
                var lastRow = checkboxes[checkboxes.length - 1].closest('tr');
                if (lastRow) {
                    fingerprint.last_row_text = lastRow.innerText.substring(0, 100);
                }
            }

            // Get total visible text length in table body
            var tbody = document.querySelector('table tbody, .dataTable tbody');
            if (tbody) {
                fingerprint.total_text_length = tbody.innerText.length;
            }

            return JSON.stringify(fingerprint);
        } catch(e) {
            return null;
        }
        """
        try:
            return self.driver.execute_script(script)
        except:
            return None

    def _get_table_state(self):
        """Capture current table state for change detection"""
        script = """
        var state = {
            processing_visible: false,
            checkbox_count: 0,
            first_checkbox_id: '',
            empty_indicator: false
        };

        // Check processing indicator
        var processing = document.querySelector('.dataTables_processing');
        if (processing) {
            var style = window.getComputedStyle(processing);
            state.processing_visible = (style.display !== 'none' && style.visibility !== 'hidden');
        }

        // Count checkboxes with class chkBatch (matches actual HTML structure)
        var checkboxes = document.querySelectorAll('input.chkBatch[name="chkBatch"]');
        state.checkbox_count = checkboxes.length;

        // Get first checkbox ID for fingerprint
        if (checkboxes.length > 0) {
            state.first_checkbox_id = checkboxes[0].id || '';
        }

        // Check for empty indicator
        var emptyCell = document.querySelector('.dataTables_empty, td.dataTables_empty');
        if (emptyCell && emptyCell.offsetParent !== null) {
            state.empty_indicator = true;
        }

        return JSON.stringify(state);
        """
        try:
            return self.driver.execute_script(script)
        except:
            return None

    def wait_for_table_loaded(self, timeout=30, previous_state=None):
        """
        Wait for the search results table to finish loading.

        Args:
            timeout: Maximum seconds to wait
            previous_state: If provided, wait for table state to change first
                           (ensures search has actually started)

        Returns:
            True when data rows are present, False when table is empty.
        """
        self.log("Waiting for search results to load...")
        self.check_cancelled()

        # Phase 1: If previous_state provided, wait for table state to CHANGE
        # This ensures the search has actually started before checking results
        if previous_state is not None:
            phase1_timeout = min(10, timeout // 2)
            start_time = time.time()
            state_changed = False

            while time.time() - start_time < phase1_timeout:
                self.check_cancelled()
                current_state = self._get_table_state()

                # Check if state has changed from previous
                if current_state != previous_state:
                    self.log("Detected table state change (search started)")
                    state_changed = True
                    break

                # Also check if loading indicator appeared (clear sign search started)
                loading_visible = self.driver.execute_script("""
                    var processing = document.querySelector('.dataTables_processing');
                    if (processing) {
                        var style = window.getComputedStyle(processing);
                        return (style.display !== 'none' && style.visibility !== 'hidden');
                    }
                    return (typeof jQuery !== 'undefined' && jQuery.active > 0);
                """)
                if loading_visible:
                    self.log("Detected loading indicator (search started)")
                    state_changed = True
                    break

                time.sleep(0.3)

            if not state_changed:
                self.log("No state change detected, continuing to wait...", "WARNING")

        def table_is_ready(driver):
            script = """
            // Ensure document and body are available (page may be transitioning)
            if (!document || !document.body) {
                return null;  // Still loading/transitioning
            }

            // FIRST: Check for loading indicators - if loading, wait
            var processing = document.querySelector('.dataTables_processing');
            if (processing) {
                var style = window.getComputedStyle(processing);
                if (style.display !== 'none' && style.visibility !== 'hidden') {
                    return null;  // Still loading
                }
            }

            if (typeof jQuery !== 'undefined' && jQuery.active > 0) {
                return null;  // AJAX still running
            }

            // SECOND: Check for the EXACT checkboxes that search_pending_users will count
            // Use class selector which matches the actual HTML: <input class="chkBatch" name="chkBatch" ...>
            var checkboxes = document.querySelectorAll('input.chkBatch[name="chkBatch"]');
            var visibleCount = 0;
            for (var j = 0; j < checkboxes.length; j++) {
                if (checkboxes[j].offsetParent !== null) {
                    visibleCount++;
                }
            }
            if (visibleCount > 0) {
                return 'has_data';  // Data found
            }

            // THIRD: Check for empty table indicators
            var emptyText = document.body ? document.body.innerText : '';
            if (emptyText.includes('No data available') ||
                emptyText.includes('No matching records') ||
                emptyText.includes('No records found') ||
                emptyText.includes('Records not found')) {
                return 'empty';
            }

            var emptyCell = document.querySelector('.dataTables_empty, td.dataTables_empty');
            if (emptyCell && emptyCell.offsetParent !== null) {
                return 'empty';
            }

            return null;  // Still loading/initializing
            """
            try:
                return driver.execute_script(script)
            except Exception as e:
                # Handle cases where page is transitioning (document.body is null)
                if "document.body is null" in str(e) or "can't access property" in str(e):
                    return None  # Treat as still loading
                raise

        # Phase 2: Wait for table to finish loading
        try:
            self.cancellable_wait(timeout,
                lambda d: table_is_ready(d) is not None,
                f"Table did not load within {timeout}s"
            )
            initial_result = table_is_ready(self.driver)

            # Phase 3: Stability check - verify result doesn't change
            # This catches delayed DOM rendering after AJAX completes
            # IMPORTANT: Do stability check for BOTH 'empty' AND 'has_data'
            self.log(f"Initial result: {initial_result}, verifying stability...")
            stability_checks = 5  # Increased from 3
            check_interval = 1.0  # Increased from 0.5 seconds

            # Get initial table fingerprint for change detection
            initial_fingerprint = self._get_table_fingerprint()

            for i in range(stability_checks):
                self.interruptible_sleep(check_interval)
                self.check_cancelled()

                # Check for loading indicator reappearing
                loading_visible = self.driver.execute_script("""
                    var processing = document.querySelector('.dataTables_processing');
                    if (processing) {
                        var style = window.getComputedStyle(processing);
                        return (style.display !== 'none' && style.visibility !== 'hidden');
                    }
                    return (typeof jQuery !== 'undefined' && jQuery.active > 0);
                """)
                if loading_visible:
                    self.log(f"Loading indicator visible (check {i+1}/{stability_checks}), waiting...")
                    continue

                current_result = table_is_ready(self.driver)
                current_fingerprint = self._get_table_fingerprint()

                # Check if result changed
                if current_result != initial_result:
                    self.log(f"Result changed: {initial_result} -> {current_result}")
                    if current_result == 'has_data':
                        # Wait additional time for data to fully render
                        self.interruptible_sleep(2)
                        self.log("Search results loaded", "SUCCESS")
                        return True
                    elif current_result == 'empty':
                        continue  # Keep checking, might still be loading
                    initial_result = current_result

                # Check if table data changed (fingerprint changed)
                if current_fingerprint != initial_fingerprint:
                    self.log(f"Table data changed (check {i+1}/{stability_checks})")
                    initial_fingerprint = current_fingerprint
                    # Data is still changing, reset stability counter
                    continue

            # Final check after stability period
            # First, ensure loading indicator is not visible (wait up to 30 seconds)
            loading_wait_start = time.time()
            loading_wait_timeout = 30  # seconds
            while time.time() - loading_wait_start < loading_wait_timeout:
                loading_visible = self.driver.execute_script("""
                    var processing = document.querySelector('.dataTables_processing');
                    if (processing) {
                        var style = window.getComputedStyle(processing);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            return true;
                        }
                    }
                    return (typeof jQuery !== 'undefined' && jQuery.active > 0);
                """)
                if not loading_visible:
                    break
                self.log("Waiting for loading indicator to disappear...")
                self.interruptible_sleep(1)
                self.check_cancelled()

            final_result = table_is_ready(self.driver)

            if final_result == 'has_data':
                # Extra wait to ensure data is fully rendered
                self.interruptible_sleep(2)
                self.log("Search results loaded", "SUCCESS")
                return True
            elif final_result == 'empty':
                self.log("Table loaded (no data)", "INFO")
                return False
            else:
                # Still loading after all checks - wait more
                self.log("Table still loading, waiting additional time...")
                self.interruptible_sleep(5)
                final_final = table_is_ready(self.driver)
                if final_final == 'has_data':
                    self.log("Search results loaded (delayed)", "SUCCESS")
                    return True
                self.log("Table loaded (no data after extended wait)", "INFO")
                return False

        except TimeoutException:
            self.log(f"Table did not load within {timeout} seconds", "WARNING")
            return False

    def _cleanup_profile_locks(self, profile_path):
        """Remove stale profile lock files to allow Selenium access"""
        lock_files = [".parentlock", "parent.lock", "lock"]
        for lock_file in lock_files:
            lock_path = os.path.join(profile_path, lock_file)
            try:
                if os.path.exists(lock_path):
                    os.remove(lock_path)
                    self.log(f"Removed lock file: {lock_file}")
            except Exception as e:
                self.log(f"Could not remove {lock_file}: {e}", "WARNING")

    def _ensure_safenet_module(self, profile_path):
        """Ensure SafeNet eToken PKCS#11 module is registered in Firefox profile"""
        pkcs11_path = os.path.join(profile_path, "pkcs11.txt")
        safenet_lib = "/usr/local/lib/libeToken.dylib"

        # Check if SafeNet driver exists
        if not os.path.exists(safenet_lib):
            self.log("SafeNet eToken driver not found at expected path", "WARNING")
            return

        # Read current pkcs11.txt
        content = ""
        if os.path.exists(pkcs11_path):
            with open(pkcs11_path, 'r') as f:
                content = f.read()

        # Check if SafeNet already registered
        if "libeToken" in content or "SafeNet" in content:
            self.log("SafeNet module already registered")
            return

        # Append SafeNet module configuration
        safenet_config = f"""
library={safenet_lib}
name=SafeNet eToken PKCS#11
NSS=Flags=optimizeSpace slotParams=(1={{slotFlags=[RSA,ECC] askpw=any timeout=30}})
"""
        with open(pkcs11_path, 'a') as f:
            f.write(safenet_config)
        self.log("Registered SafeNet eToken module", "SUCCESS")

    def setup_browser(self):
        """Setup Firefox browser with existing profile to use installed P12 certificate"""
        self.check_cancelled()

        # Skip if browser already exists and is responsive
        if self.driver:
            try:
                _ = self.driver.current_url  # Test if browser is alive
                self.log("Reusing existing browser session")
                return
            except:
                self.log("Previous browser session died, starting new one...")
                self.driver = None

        options = Options()

        # Use existing Firefox profile where P12 certificate is installed
        if self.firefox_profile_path:
            profile_path = self.firefox_profile_path
        else:
            profile_path = find_firefox_profile()

        if profile_path:
            self.log(f"Using Firefox profile: {profile_path}")
            # Clean up lock files to allow access
            self._cleanup_profile_locks(profile_path)

            # Configure based on authentication method
            if self.auth_method == "Thales Token (Hardware)":
                self.log("Using Thales Token (Hardware) authentication")
                # Ensure SafeNet eToken PKCS#11 module is registered
                self._ensure_safenet_module(profile_path)
            else:
                self.log("Using Soft Token (Certificate) authentication")

            options.add_argument("-profile")
            options.add_argument(profile_path)
        else:
            self.log("Could not find Firefox profile. Certificate authentication may fail.", "WARNING")

        # Set preferences for certificate handling based on auth method
        if self.auth_method == "Soft Token (Select Certificate)":
            # Allow user to select which certificate to use (for multiple users on same Mac)
            options.set_preference("security.default_personal_cert", "Ask Every Time")
            self.log("Certificate selection: User will be prompted to select certificate")
        else:
            # Auto-select certificate (for hardware token)
            options.set_preference("security.default_personal_cert", "Select Automatically")
        options.set_preference("webdriver_accept_untrusted_certs", True)
        options.set_preference("accept_untrusted_certs", True)
        options.set_preference("marionette.port", 0)

        # Additional SSL/TLS preferences for government sites
        options.set_preference("security.enterprise_roots.enabled", True)  # Trust system CA certs
        options.set_preference("security.cert_pinning.enforcement_level", 0)  # Disable cert pinning
        options.set_preference("security.mixed_content.block_active_content", False)
        options.set_preference("security.ssl.enable_ocsp_stapling", False)  # Skip OCSP if problematic
        options.set_preference("network.stricttransportsecurity.preloadlist", False)
        options.set_preference("security.tls.version.min", 1)  # Allow TLS 1.0+ for older gov systems
        options.set_preference("security.ssl.require_safe_negotiation", False)

        # Increase timeouts for hardware token PIN entry
        options.set_preference("network.http.connection-timeout", 90)
        options.set_preference("network.http.response.timeout", 90)
        options.set_preference("security.OCSP.timeoutMilliseconds.hard", 30000)

        # PKCS#11 module handling for hardware tokens (SafeNet eToken)
        options.set_preference("security.osclientcerts.autoload", True)
        options.set_preference("security.remember_cert_checkbox_default_setting", False)

        # Disable caching that can interfere with hardware tokens
        options.set_preference("browser.cache.disk.enable", False)
        options.set_preference("browser.cache.memory.enable", False)
        options.set_preference("browser.cache.offline.enable", False)
        options.set_preference("network.http.use-cache", False)

        # Initialize Firefox driver
        self.log("Starting Firefox...")

        try:
            # Check for bundled geckodriver
            geckodriver_path = get_bundled_geckodriver()
            if geckodriver_path:
                service = Service(executable_path=geckodriver_path)
                self.driver = webdriver.Firefox(options=options, service=service)
            else:
                # Try system geckodriver
                self.driver = webdriver.Firefox(options=options)

            self.wait = WebDriverWait(self.driver, 30)

            # Give browser a moment to stabilize before maximizing
            self.interruptible_sleep(1)

            # Verify browser is still alive before maximizing
            try:
                _ = self.driver.current_url  # Test if browser context is valid
                self.driver.maximize_window()
            except Exception as max_err:
                # Browser may have closed (certificate dialog dismissed, etc.)
                self.log(f"Browser window unavailable: {max_err}", "WARNING")
                self.log("Browser may have closed unexpectedly. Retrying...", "WARNING")
                # Clean up and raise to trigger retry at higher level
                try:
                    self.driver.quit()
                except:
                    pass
                self.driver = None
                raise Exception("Browser closed unexpectedly after start. Please ensure Firefox is not already running and try again.")

            self.log("Firefox started successfully", "SUCCESS")
            # Allow initialization based on auth method
            if self.auth_method == "Thales Token (Hardware)":
                self.log("Waiting for SafeNet eToken to initialize...")
                self.interruptible_sleep(3)
            else:
                self.log("Ready for certificate selection...")
                self.interruptible_sleep(1)

        except Exception as e:
            error_msg = str(e)
            self.log(f"Error starting Firefox: {e}", "ERROR")
            if "Browsing context has been discarded" in error_msg or "Browser closed unexpectedly" in error_msg:
                self.log("Troubleshooting:", "INFO")
                self.log("1. Close ALL Firefox windows completely", "INFO")
                self.log("2. Wait a few seconds and try again", "INFO")
                if self.auth_method == "Thales Token (Hardware)":
                    self.log("3. If using eToken, ensure it is properly connected", "INFO")
                else:
                    self.log("3. Ensure your certificate is installed in Firefox", "INFO")
            else:
                self.log("Troubleshooting:", "INFO")
                self.log("1. Close Firefox if open", "INFO")
                self.log("2. Ensure geckodriver is installed", "INFO")
            raise

    def navigate_to_govca(self):
        """Navigate to GovCA URL with retry logic for SSL errors"""
        self.check_cancelled()
        max_retries = 2

        for attempt in range(max_retries):
            try:
                self.log("Navigating to GovCA...")
                self.driver.get("https://govca.npki.gov.ph:8443/SecureTMSWebMgr/")

                if self.auth_method == "Soft Token (Select Certificate)":
                    self.log("Please select your certificate from the dialog", "WARNING")
                    self.log("Waiting for certificate selection (10 seconds)...")
                    self.interruptible_sleep(10)  # Give more time for user to select certificate
                else:
                    self.log("If certificate dialog appears, select your certificate", "WARNING")
                    self.log("Waiting 5 seconds...")
                    self.interruptible_sleep(5)

                self.check_cancelled()

                if "400" in self.driver.title or "Bad Request" in self.driver.page_source:
                    self.log("Certificate authentication failed!", "ERROR")
                    return False

                self.log("Successfully connected to GovCA", "SUCCESS")
                return True

            except Exception as e:
                error_msg = str(e)
                if "nssFailure" in error_msg or "neterror" in error_msg:
                    if attempt < max_retries - 1:
                        self.log(f"SSL/certificate error, retrying... ({attempt + 1}/{max_retries})", "WARNING")
                        self.interruptible_sleep(5)
                        continue
                    else:
                        self.log(f"SSL authentication failed after {max_retries} attempts", "ERROR")
                        if self.auth_method == "Thales Token (Hardware)":
                            self.log("Please ensure your SafeNet eToken is properly connected", "INFO")
                        else:
                            self.log("Please ensure your certificate is valid and properly installed in Firefox", "INFO")
                        raise
                else:
                    raise

        return False

    def select_domain(self, domain_name="NCR00Sign"):
        """Select domain from dropdown"""
        self.check_cancelled()
        self.log(f"Selecting domain: {domain_name}")

        try:
            domain_dropdown = self.wait.until(
                EC.presence_of_element_located((By.ID, "selSwitchDomain"))
            )

            select = Select(domain_dropdown)
            select.select_by_visible_text(domain_name)
            self.log(f"Domain '{domain_name}' selected", "SUCCESS")

            self.log("Waiting for page to reload...")
            self.wait_for_page_ready(timeout=30)
            self.log("Page reload complete", "SUCCESS")
            return True

        except Exception as e:
            self.log(f"Error selecting domain: {e}", "ERROR")
            return False

    def get_counterpart_domain(self, domain):
        """Get the counterpart domain (Sign <-> Auth)"""
        if "Sign" in domain:
            return domain.replace("Sign", "Auth")
        elif "Auth" in domain:
            return domain.replace("Auth", "Sign")
        return None

    def navigate_to_user_list(self):
        """Navigate to User List page"""
        self.check_cancelled()
        self.log("Navigating to User List...")

        try:
            base_url = self.driver.current_url.split('?')[0]
            user_list_url = base_url + "?m=user&c=user_list"
            self.driver.get(user_list_url)
            self.wait_for_page_ready(timeout=30)

            if "user_list" in self.driver.current_url:
                self.log("User List page loaded", "SUCCESS")
                return True
            else:
                self.log("Could not verify User List page", "ERROR")
                return False

        except Exception as e:
            self.log(f"Error navigating to User List: {e}", "ERROR")
            return False

    def navigate_to_approval_request_list(self):
        """Navigate to Approval Request List page"""
        self.check_cancelled()
        self.log("Navigating to Approval Request List...")

        try:
            base_url = self.driver.current_url.split('?')[0]
            approval_request_url = base_url + "?m=approval&c=approve_list"
            self.driver.get(approval_request_url)
            self.interruptible_sleep(3)

            self.check_cancelled()

            if "approve_list" in self.driver.current_url:
                self.log("Approval Request List page loaded", "SUCCESS")
                return True
            else:
                self.log("Verifying page load...")
                self.interruptible_sleep(2)
                if "approve_list" in self.driver.current_url or ("approval" in self.driver.current_url and "c=approve" in self.driver.current_url):
                    self.log("Approval Request List page loaded", "SUCCESS")
                    return True
                else:
                    self.log("Could not verify Approval Request List page", "ERROR")
                    return False

        except Exception as e:
            self.log(f"Error navigating to Approval Request List: {e}", "ERROR")
            return False

    def navigate_to_assign_user_group(self):
        """Navigate to Assign User Group page"""
        self.check_cancelled()
        self.log("Navigating to Assign User Group page...")

        try:
            base_url = self.driver.current_url.split('?')[0]
            assign_group_url = base_url + "?m=user&c=user_group"
            self.driver.get(assign_group_url)
            self.interruptible_sleep(3)

            self.check_cancelled()

            if "user_group" in self.driver.current_url:
                self.log("Assign User Group page loaded", "SUCCESS")
                return True
            else:
                self.log("Verifying page load...")
                self.interruptible_sleep(2)
                if "user_group" in self.driver.current_url:
                    self.log("Assign User Group page loaded", "SUCCESS")
                    return True
                else:
                    self.log("Could not verify Assign User Group page", "ERROR")
                    return False

        except Exception as e:
            self.log(f"Error navigating to Assign User Group: {e}", "ERROR")
            return False

    def search_pending_users(self):
        """Search for pending users"""
        self.check_cancelled()
        self.log("Searching for pending users...")

        try:
            # Set User Status filter to "Pending"
            self.log("Setting User Status filter to 'Pending'...")

            max_filter_retries = 3
            filter_set = False

            for filter_attempt in range(max_filter_retries):
                try:
                    self.check_cancelled()
                    self.cancellable_wait(10,
                        EC.presence_of_element_located((By.ID, "cmbStatus"))
                    )
                    self.interruptible_sleep(1)

                    status_dropdown = self.driver.find_element(By.ID, "cmbStatus")
                    select = Select(status_dropdown)

                    try:
                        select.select_by_value("4")  # Pending
                    except:
                        select.select_by_visible_text("Pending")

                    self.log("User Status set to 'Pending'", "SUCCESS")
                    filter_set = True
                    self.interruptible_sleep(1)
                    break

                except Exception as e:
                    if filter_attempt < max_filter_retries - 1:
                        self.log(f"Could not set filter (attempt {filter_attempt + 1}/{max_filter_retries}): {e}", "WARNING")
                        self.interruptible_sleep(2)
                    else:
                        self.log(f"Failed to set User Status filter after {max_filter_retries} attempts", "WARNING")

            if not filter_set:
                self.log("Pending filter not applied - results may include non-pending users", "WARNING")

            self.check_cancelled()

            # Capture current table state before clicking search
            # This allows us to detect when the search actually starts
            previous_state = self._get_table_state()

            # Click Search button
            search_button = self.driver.find_element(By.ID, "btnSearch")
            search_button.click()
            self.log("Search button clicked", "SUCCESS")

            # Wait for table to load, passing previous state for change detection
            if self.wait_for_table_loaded(timeout=30, previous_state=previous_state):
                # Count the checkboxes (table has data)
                # Use class selector matching actual HTML: <input class="chkBatch" name="chkBatch" ...>
                checkboxes = self.driver.find_elements(
                    By.CSS_SELECTOR, "input.chkBatch[name='chkBatch']"
                )
                visible_count = sum(1 for cb in checkboxes if cb.is_displayed() and cb.is_enabled())

                if visible_count > 0:
                    self.log(f"Found {visible_count} user(s) with pending approval", "SUCCESS")
                    return True

            self.log("No pending users found", "WARNING")
            return False

        except Exception as e:
            self.log(f"Error searching for users: {e}", "ERROR")
            return False

    def select_all_pending_users(self):
        """Select all checkboxes for pending approval users"""
        self.check_cancelled()
        self.log("Selecting users for approval...")

        try:
            self.interruptible_sleep(2)

            # Try "Select All" checkbox first
            try:
                select_all = self.driver.find_element(By.ID, "chkAllBatch")
                if select_all.is_displayed() and select_all.is_enabled():
                    self.driver.execute_script("arguments[0].click();", select_all)
                    self.log("Clicked 'Select All' checkbox", "SUCCESS")
                    self.interruptible_sleep(1)

                    checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']:checked")
                    selected_count = len([cb for cb in checkboxes if cb.get_attribute('id') not in ['showAdmin', 'chkAllBatch']])

                    if selected_count > 0:
                        self.log(f"{selected_count} user(s) selected", "SUCCESS")
                        return selected_count
                    else:
                        self.log("Select All didn't work, trying individual selection...", "WARNING")
            except Exception as e:
                self.log(f"Could not use Select All: {e}", "WARNING")

            self.check_cancelled()

            # Fallback: Select individual checkboxes
            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']")

            if not checkboxes:
                self.log("No checkboxes found", "ERROR")
                return 0

            selected_count = 0
            for checkbox in checkboxes:
                self.check_cancelled()
                try:
                    if checkbox.is_displayed() and checkbox.is_enabled():
                        if not checkbox.is_selected():
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                            time.sleep(0.3)
                            self.driver.execute_script("arguments[0].click();", checkbox)
                            selected_count += 1
                except:
                    continue

            if selected_count > 0:
                self.log(f"{selected_count} user(s) selected", "SUCCESS")
            else:
                self.log("Could not select any users", "ERROR")

            return selected_count

        except Exception as e:
            self.log(f"Error selecting checkboxes: {e}", "ERROR")
            return 0

    def select_specific_users(self, usernames):
        """Select only specific users by username"""
        self.check_cancelled()
        self.log(f"Selecting specific users: {', '.join(usernames[:5])}{'...' if len(usernames) > 5 else ''}")

        try:
            selected_count = 0
            matched_users = set()
            not_found_users = set(usernames)
            current_page = 1
            max_pages = 50

            while current_page <= max_pages:
                self.check_cancelled()
                self.log(f"Checking Page {current_page}...")

                self.interruptible_sleep(5)

                try:
                    self.cancellable_wait(15,
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']"))
                    )
                except:
                    # No checkboxes found = no more pending users
                    self.log("No more pending users found", "INFO")
                    break

                checkbox_count = len(self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']"))
                self.log(f"Found {checkbox_count} data rows on page {current_page}")

                self.interruptible_sleep(3)

                # Get usernames on current page
                page_usernames = []
                try:
                    checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']")
                    for cb in checkboxes:
                        try:
                            row = cb.find_element(By.XPATH, "./ancestor::tr[1]")
                            cells = row.find_elements(By.XPATH, "./td")
                            if 3 <= len(cells) <= 15:
                                for cell in cells[1:6]:  # Check more cells
                                    cell_text = cell.text.strip()
                                    if cell_text and '_' in cell_text and len(cell_text) < 100:
                                        page_usernames.append(cell_text)
                                        break
                        except:
                            continue
                except:
                    pass

                # Log some sample usernames for debugging
                if page_usernames:
                    sample = page_usernames[:5]
                    self.log(f"Sample usernames on page: {', '.join(sample)}", "DEBUG")

                # Check for matches
                matches_on_page = [u for u in page_usernames if u in usernames]

                if matches_on_page:
                    self.log(f"Found {len(matches_on_page)} matching user(s) on page {current_page}!", "SUCCESS")

                    for i in range(checkbox_count):
                        self.check_cancelled()
                        try:
                            checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']")
                            if i >= len(checkboxes):
                                break

                            checkbox = checkboxes[i]
                            row = checkbox.find_element(By.XPATH, "./ancestor::tr[1]")
                            cells = row.find_elements(By.XPATH, "./td")

                            if len(cells) < 3 or len(cells) > 15:
                                continue

                            found_username = None
                            for cell in cells:
                                try:
                                    cell_text = cell.text.strip()
                                    if cell_text in usernames and len(cell_text) < 100:
                                        found_username = cell_text
                                        break
                                except:
                                    continue

                            if found_username and found_username not in matched_users:
                                try:
                                    checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']")
                                    if i < len(checkboxes):
                                        cb = checkboxes[i]
                                        if cb.is_displayed() and cb.is_enabled() and not cb.is_selected():
                                            self.driver.execute_script("arguments[0].scrollIntoView(true);", cb)
                                            time.sleep(0.2)
                                            self.driver.execute_script("arguments[0].click();", cb)
                                            selected_count += 1
                                            matched_users.add(found_username)
                                            not_found_users.discard(found_username)
                                            self.log(f"Selected: {found_username}", "SUCCESS")
                                except Exception as click_err:
                                    self.log(f"Could not click checkbox for {found_username}: {click_err}", "WARNING")

                        except:
                            continue

                    # IMPORTANT: After selecting users on this page, RETURN immediately
                    # so they can be batch processed. Navigating to next page would LOSE
                    # the checkbox selections from this page!
                    if selected_count > 0:
                        self.log(f"Selected {selected_count} user(s) on page {current_page} - ready for batch processing", "SUCCESS")
                        # Return now - caller will process these, then call again for remaining users
                        break

                    # Only check if all users found when none were selected on this page
                    if len(not_found_users) == 0:
                        self.log("All target users have been found!", "SUCCESS")
                        break
                else:
                    self.log(f"No matching users on page {current_page}", "INFO")

                # Only go to next page if NO users were selected on current page
                # (selections are lost when navigating, so we must process first)
                if selected_count == 0 and len(not_found_users) > 0:
                    if self.has_next_page():
                        if self.go_to_next_page():
                            current_page += 1
                            continue
                        else:
                            self.log("Failed to navigate to next page", "WARNING")
                            break
                    else:
                        self.log("No more pages to check", "INFO")
                        break
                else:
                    break

            if not_found_users and selected_count == 0:
                self.log(f"Users not found: {', '.join(sorted(list(not_found_users)[:10]))}", "WARNING")

            if selected_count > 0:
                self.log(f"Total selected: {selected_count} user(s)", "SUCCESS")
            else:
                self.log("Could not select any of the specified users", "WARNING")

            return selected_count, matched_users

        except Exception as e:
            self.log(f"Error selecting specific users: {e}", "ERROR")
            return 0, set()

    def has_next_page(self):
        """Check if there's a Next page button"""
        self.check_cancelled()
        try:
            # Wait for page to be ready before checking pagination
            try:
                self.cancellable_wait(10,
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
                self.cancellable_wait(5,
                    lambda d: d.execute_script("return document.body !== null")
                )
            except:
                self.log("Page not ready for pagination check, waiting...", "DEBUG")
                self.interruptible_sleep(3)

            # Scroll to bottom of page to reveal pagination controls
            try:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except Exception as scroll_err:
                self.log(f"Could not scroll: {scroll_err}", "DEBUG")
            self.interruptible_sleep(2)

            # Try multiple selectors for pagination
            next_selectors = [
                "//a[.//img[contains(@src, 'next_page')]]",
                "//a[.//img[contains(@src, 'next')]]",
                "//a[.//img[contains(@src, 'Next')]]",
                "//a[contains(@href, 'page') and contains(text(), 'Next')]",
                "//a[contains(text(), 'Next')]",
                "//a[contains(text(), '>>')]",
                "//a[text()='>']",
                "//input[@type='button' and contains(@value, 'Next')]",
                "//button[contains(text(), 'Next')]",
                "//a[contains(@class, 'next')]",
                "//a[contains(@class, 'Next')]",
                "//a[contains(@onclick, 'next')]",
                "//a[contains(@onclick, 'Next')]",
                "//a[contains(@onclick, 'page')]",
                "//img[contains(@src, 'next')]/..",
                "//img[contains(@src, 'Next')]/..",
                "//a[contains(@title, 'Next')]",
                "//a[contains(@title, 'next')]",
                "//span[contains(@class, 'next')]/a",
                "//td[contains(@class, 'pag')]//a[contains(text(), '>')]",
                "//div[contains(@class, 'pag')]//a[contains(text(), '>')]",
            ]

            for selector in next_selectors:
                self.check_cancelled()
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            self.log(f"Found pagination element: {selector}", "DEBUG")
                            return True
                except:
                    continue

            # Also check for page number links (e.g., if we're on page 1 and page 2 exists)
            try:
                page_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, 'page=2') or contains(@onclick, 'page') or contains(@onclick, '(2)')]")
                for link in page_links:
                    if link.is_displayed():
                        self.log("Found page 2 link", "DEBUG")
                        return True
            except:
                pass

            # Check for numbered pagination links
            try:
                numbered_pages = self.driver.find_elements(By.XPATH, "//a[string-length(text()) <= 3 and number(text()) > 1]")
                for link in numbered_pages:
                    if link.is_displayed():
                        link_text = link.text.strip()
                        if link_text.isdigit() and int(link_text) > 1:
                            self.log(f"Found page {link_text} link", "DEBUG")
                            return True
            except:
                pass

            # Debug: log all links that might be pagination
            try:
                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                pagination_hints = []
                for link in all_links[-20:]:  # Check last 20 links (likely at bottom)
                    try:
                        href = link.get_attribute('href') or ''
                        onclick = link.get_attribute('onclick') or ''
                        text = link.text.strip()
                        if 'page' in href.lower() or 'page' in onclick.lower() or text in ['>', '>>', 'Next', '2', '3']:
                            pagination_hints.append(f"'{text}' (href={href[:50] if href else 'none'})")
                    except:
                        continue
                if pagination_hints:
                    self.log(f"Potential pagination links: {', '.join(pagination_hints[:5])}", "DEBUG")
            except:
                pass

            self.log("No pagination controls found", "DEBUG")
            return False
        except Exception as e:
            self.log(f"Error checking pagination: {e}", "DEBUG")
            return False

    def go_to_next_page(self):
        """Navigate to next page by clicking the pagination button"""
        self.check_cancelled()
        try:
            next_btn = None

            # Try multiple selectors for the next button
            next_selectors = [
                "//a[.//img[contains(@src, 'next_page')]]",
                "//a[.//img[contains(@src, 'next')]]",
                "//a[contains(@href, 'page') and contains(text(), 'Next')]",
                "//a[contains(text(), 'Next')]",
                "//a[contains(text(), '>>')]",
                "//input[@type='button' and contains(@value, 'Next')]",
                "//button[contains(text(), 'Next')]",
                "//a[contains(@class, 'next')]",
                "//a[contains(@onclick, 'next')]",
                "//img[contains(@src, 'next')]/..",
                "//a[contains(@title, 'Next')]",
            ]

            for selector in next_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            next_btn = elem
                            self.log(f"Using pagination: {selector}", "DEBUG")
                            break
                    if next_btn:
                        break
                except:
                    continue

            if not next_btn:
                self.log("Could not find next page button", "WARNING")
                return False

            # Capture table state BEFORE clicking (for change detection)
            previous_state = self._get_table_state()
            fingerprint_before = self._get_table_fingerprint()

            # Scroll the button into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            time.sleep(0.5)

            # Try clicking up to 3 times, verifying page actually changed
            for attempt in range(3):
                self.check_cancelled()
                try:
                    self.driver.execute_script("arguments[0].click();", next_btn)
                except:
                    next_btn.click()

                self.log("Clicked next page button", "SUCCESS")

                # Wait for AJAX table load (handles loading indicator + jQuery.active)
                self.wait_for_table_loaded(timeout=30, previous_state=previous_state)

                # Verify page content actually changed
                fingerprint_after = self._get_table_fingerprint()
                if fingerprint_before != fingerprint_after:
                    return True  # Page actually changed

                self.log(f"Page content unchanged after click (attempt {attempt + 1}/3), retrying...", "WARNING")
                self.interruptible_sleep(2)

                # Re-find the button (may have gone stale)
                next_btn = None
                for selector in next_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for elem in elements:
                            if elem.is_displayed() and elem.is_enabled():
                                next_btn = elem
                                break
                        if next_btn:
                            break
                    except:
                        continue

                if not next_btn:
                    break

            self.log("Page did not change after clicking next button", "WARNING")
            return False

        except Exception as e:
            self.log(f"Could not navigate to next page: {e}", "WARNING")
            return False

    def detect_error_page(self):
        """Detect if current page is an error page"""
        try:
            page_source = self.driver.page_source.lower()
            title = self.driver.title.lower()

            if "502" in title or "bad gateway" in page_source:
                return True, "502 Bad Gateway"
            if "503" in title or "service unavailable" in page_source:
                return True, "503 Service Unavailable"
            if "504" in title or "gateway timeout" in page_source:
                return True, "504 Gateway Timeout"
            if "500" in title or "internal server error" in page_source:
                return True, "500 Internal Server Error"

            return False, None
        except:
            return False, None

    def approve_users(self, comment="Approved via automation"):
        """Add comment and click Approve button - loops until all users approved"""
        self.check_cancelled()
        self.log("Starting approval process...")

        try:
            # Click Batch Response button
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.interruptible_sleep(1)

            batch_respond_button = self.driver.find_element(By.ID, "btnBatchRespond")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", batch_respond_button)
            time.sleep(0.5)

            url_before_batch = self.driver.current_url
            batch_respond_button.click()
            self.log("Batch Response button clicked", "SUCCESS")

            # Wait for dialog/popup
            self.log("Waiting for approval dialog...")
            original_window = self.driver.current_window_handle

            try:
                def approval_page_loaded(driver):
                    if len(driver.window_handles) > 1:
                        return True
                    current_url = driver.current_url
                    if current_url != url_before_batch:
                        if "m=approval" in current_url or "c=approve_mgmt" in current_url:
                            return driver.execute_script("return document.readyState") == "complete"
                    return False

                self.cancellable_wait(15, approval_page_loaded)

                all_windows = self.driver.window_handles
                if len(all_windows) > 1:
                    self.log("Detected popup window, switching to it...")
                    for window in all_windows:
                        if window != original_window:
                            self.driver.switch_to.window(window)
                            break

                    self.cancellable_wait(10,
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                else:
                    self.log("Navigated to approval page", "SUCCESS")

            except Exception as e:
                self.log(f"Navigation wait timeout: {e}", "WARNING")

            self.cancellable_wait(15,
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            self.check_cancelled()

            # Check for error page
            is_error, error_type = self.detect_error_page()
            if is_error:
                self.log(f"Error page detected: {error_type}", "ERROR")
                return False

            # Loop through all approval requests
            approved_count = 0
            request_number = 1

            while True:
                self.check_cancelled()
                self.log(f"Processing Request #{request_number}...")
                # Use indeterminate progress (-1 total) since we don't know total requests upfront
                self.report_progress(request_number, -1, f"Processing request #{request_number}")

                # Add comment
                try:
                    comment_field = self.cancellable_wait(15,
                        EC.presence_of_element_located((By.ID, "txtComment"))
                    )
                    WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "txtComment"))
                    )

                    if not comment_field.get_attribute('value') or request_number == 1:
                        comment_field.clear()
                        time.sleep(0.2)
                        comment_field.send_keys(comment)
                        self.log(f"Comment added: '{comment}'", "SUCCESS")
                    else:
                        self.log("Comment already filled", "SUCCESS")
                except Exception as e:
                    self.log(f"Could not find comment field: {e}", "WARNING")

                self.check_cancelled()

                # Click Approve button
                try:
                    approve_button = self.cancellable_wait(15,
                        EC.element_to_be_clickable((By.ID, "btnApprove"))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", approve_button)
                    time.sleep(0.5)

                    url_before_approve = self.driver.current_url
                    approve_button.click()
                    self.log("Approve button clicked", "SUCCESS")
                    approved_count += 1

                    # Handle alert
                    try:
                        WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                        alert = self.driver.switch_to.alert
                        self.log(f"Alert: {alert.text}", "WARNING")
                        alert.accept()
                        self.log("Alert accepted", "SUCCESS")
                    except:
                        pass

                except Exception as e:
                    self.log(f"Could not find Approve button: {e}", "ERROR")
                    if request_number == 1:
                        self.log("Failed to start approval process", "ERROR")
                        return False
                    break

                # Wait for page transition
                self.log("Waiting for page transition...")
                self.interruptible_sleep(7)

                self.check_cancelled()

                # Wait for page ready
                try:
                    self.cancellable_wait(20,
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                    self.interruptible_sleep(2)
                except:
                    self.interruptible_sleep(5)

                # Check for completion
                current_url = self.driver.current_url

                # Look for Next Request button (works on both success page and batch page)
                next_request_found = False
                next_request_button = None

                # Debug: Log all buttons on page
                try:
                    all_buttons = self.driver.find_elements(By.XPATH, "//input[@type='button'] | //input[@type='submit'] | //button")
                    button_values = []
                    for btn in all_buttons[:10]:  # Limit to first 10
                        try:
                            val = btn.get_attribute('value') or btn.text or btn.get_attribute('id')
                            if val:
                                button_values.append(val)
                        except:
                            pass
                    if button_values:
                        self.log(f"Buttons on page: {', '.join(button_values)}", "INFO")
                except:
                    pass

                for poll_attempt in range(15):
                    self.check_cancelled()
                    try:
                        candidates = []
                        # Multiple selector variations for "Next Request" button
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[@value='Next Request']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Next')][@type='button']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Next')][@type='submit']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')]"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Continue')]"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnNext"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnNextRequest"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]"))
                        # Also check for OK/Continue buttons (sometimes on success page)
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[@value='OK']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//button[contains(text(), 'OK')]"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnOK"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnContinue"))

                        for candidate in candidates:
                            try:
                                if candidate.is_displayed() and candidate.is_enabled():
                                    next_request_button = candidate
                                    next_request_found = True
                                    self.log(f"Found next button: {candidate.get_attribute('value') or candidate.text}", "DEBUG")
                                    break
                            except:
                                continue

                        if next_request_found:
                            break

                        if poll_attempt < 14:
                            self.interruptible_sleep(2)  # Wait between polls
                    except:
                        if poll_attempt < 14:
                            self.interruptible_sleep(2)

                if next_request_found and next_request_button:
                    self.log("Found Next Request button - clicking...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_request_button)
                    time.sleep(0.3)
                    next_request_button.click()
                    self.log("Clicked Next Request button", "SUCCESS")

                    try:
                        self.cancellable_wait(15,
                            EC.presence_of_element_located((By.ID, "txtComment"))
                        )
                        self.cancellable_wait(10,
                            lambda driver: driver.execute_script("return document.readyState") == "complete"
                        )
                        self.log("Approval form loaded", "SUCCESS")
                    except:
                        self.interruptible_sleep(3)

                    request_number += 1
                    continue

                # Check if Approve button still exists (auto-loaded next request)
                try:
                    approve_btn = self.driver.find_element(By.ID, "btnApprove")
                    comment_field = self.driver.find_elements(By.ID, "txtComment")
                    if comment_field and approve_btn.is_displayed() and approve_btn.is_enabled():
                        fresh_url = self.driver.current_url
                        if "infoMsg" not in fresh_url:
                            self.log("Next request loaded automatically - continuing...", "SUCCESS")
                            request_number += 1
                            continue
                except:
                    pass

                # Check for definitive exit conditions
                try:
                    cancel_exists = len(self.driver.find_elements(By.XPATH, "//input[@value='Cancel']")) > 0
                    approve_exists = len(self.driver.find_elements(By.ID, "btnApprove")) > 0

                    if cancel_exists and not approve_exists:
                        self.log("Found Cancel button only - all requests processed", "SUCCESS")
                        break

                    if not cancel_exists and not approve_exists:
                        self.log("All requests processed", "SUCCESS")
                        break

                    # Approve button exists — page may still be loading. Wait and retry.
                    if approve_exists:
                        self.log("Approve button detected, waiting for page to stabilize...", "WARNING")
                        self.interruptible_sleep(5)
                        try:
                            approve_btn = self.driver.find_element(By.ID, "btnApprove")
                            comment_field = self.driver.find_elements(By.ID, "txtComment")
                            if comment_field and approve_btn.is_displayed() and approve_btn.is_enabled():
                                fresh_url = self.driver.current_url
                                if "infoMsg" not in fresh_url:
                                    self.log("Next request loaded after extended wait - continuing...", "SUCCESS")
                                    request_number += 1
                                    continue
                        except:
                            pass
                except:
                    pass

                self.log("Could not find next action - batch complete", "SUCCESS")
                break

            self.log(f"Successfully approved {approved_count} user(s)!", "SUCCESS")
            self.report_progress(approved_count, approved_count, "Completed")
            return approved_count

        except OperationCancelledException:
            raise
        except Exception as e:
            self.log(f"Error during approval: {e}", "ERROR")
            return 0

    def reject_users(self, comment="Rejected via automation"):
        """Add comment and click Reject button - loops until all users rejected"""
        self.check_cancelled()
        self.log("Starting rejection process...")

        try:
            # Click Batch Response button
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.interruptible_sleep(1)

            batch_respond_button = self.driver.find_element(By.ID, "btnBatchRespond")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", batch_respond_button)
            time.sleep(0.5)

            url_before_batch = self.driver.current_url
            batch_respond_button.click()
            self.log("Batch Response button clicked", "SUCCESS")

            # Wait for dialog/popup
            self.log("Waiting for rejection dialog...")
            original_window = self.driver.current_window_handle

            try:
                def rejection_page_loaded(driver):
                    if len(driver.window_handles) > 1:
                        return True
                    current_url = driver.current_url
                    if current_url != url_before_batch:
                        if "m=approval" in current_url or "c=approve_mgmt" in current_url:
                            return driver.execute_script("return document.readyState") == "complete"
                    return False

                self.cancellable_wait(15, rejection_page_loaded)

                all_windows = self.driver.window_handles
                if len(all_windows) > 1:
                    self.log("Detected popup window, switching to it...")
                    for window in all_windows:
                        if window != original_window:
                            self.driver.switch_to.window(window)
                            break

                    self.cancellable_wait(10,
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                else:
                    self.log("Navigated to rejection page", "SUCCESS")

            except Exception as e:
                self.log(f"Navigation wait timeout: {e}", "WARNING")

            self.cancellable_wait(15,
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            self.check_cancelled()

            # Check for error page
            is_error, error_type = self.detect_error_page()
            if is_error:
                self.log(f"Error page detected: {error_type}", "ERROR")
                return False

            # Loop through all rejection requests
            rejected_count = 0
            request_number = 1

            while True:
                self.check_cancelled()
                self.log(f"Processing Rejection Request #{request_number}...")
                self.report_progress(rejected_count, -1, f"Processing rejection #{request_number}")

                # Add comment
                try:
                    comment_field = self.cancellable_wait(15,
                        EC.presence_of_element_located((By.ID, "txtComment"))
                    )
                    WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.ID, "txtComment"))
                    )

                    if not comment_field.get_attribute('value') or request_number == 1:
                        comment_field.clear()
                        time.sleep(0.2)
                        comment_field.send_keys(comment)
                        self.log(f"Comment added: '{comment}'", "SUCCESS")
                    else:
                        self.log("Comment already filled", "SUCCESS")
                except Exception as e:
                    self.log(f"Could not find comment field: {e}", "WARNING")

                self.check_cancelled()

                # Click Reject button
                try:
                    reject_button = self.cancellable_wait(15,
                        EC.element_to_be_clickable((By.ID, "btnReject"))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", reject_button)
                    time.sleep(0.5)

                    url_before_reject = self.driver.current_url
                    reject_button.click()
                    self.log("Reject button clicked", "SUCCESS")
                    rejected_count += 1

                    # Handle alert
                    try:
                        WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                        alert = self.driver.switch_to.alert
                        self.log(f"Alert: {alert.text}", "WARNING")
                        alert.accept()
                        self.log("Alert accepted", "SUCCESS")
                    except:
                        pass

                except Exception as e:
                    self.log(f"Could not find Reject button: {e}", "ERROR")
                    if request_number == 1:
                        self.log("Failed to start rejection process", "ERROR")
                        return False
                    break

                # Wait for page transition
                self.log("Waiting for page transition...")
                self.interruptible_sleep(7)

                self.check_cancelled()

                # Wait for page ready
                try:
                    self.cancellable_wait(20,
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                    self.interruptible_sleep(2)
                except:
                    self.interruptible_sleep(5)

                # Check for completion
                current_url = self.driver.current_url

                # Check for completion
                current_url = self.driver.current_url

                # Look for Next Request button (works on both success page and batch page)
                next_request_found = False
                next_request_button = None

                # Debug: Log all buttons on page
                try:
                    all_buttons = self.driver.find_elements(By.XPATH, "//input[@type='button'] | //input[@type='submit'] | //button")
                    button_values = []
                    for btn in all_buttons[:10]:  # Limit to first 10
                        try:
                            val = btn.get_attribute('value') or btn.text or btn.get_attribute('id')
                            if val:
                                button_values.append(val)
                        except:
                            pass
                    if button_values:
                        self.log(f"Buttons on page: {', '.join(button_values)}", "INFO")
                except:
                    pass

                for poll_attempt in range(15):
                    self.check_cancelled()
                    try:
                        candidates = []
                        # Multiple selector variations for "Next Request" button
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[@value='Next Request']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Next')][@type='button']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Next')][@type='submit']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//button[contains(text(), 'Next')]"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Continue')]"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnNext"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnNextRequest"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Next')]"))
                        # Also check for OK/Continue buttons (sometimes on success page)
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[@value='OK']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//button[contains(text(), 'OK')]"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnOK"))
                        candidates.extend(self.driver.find_elements(By.ID, "btnContinue"))

                        for candidate in candidates:
                            try:
                                if candidate.is_displayed() and candidate.is_enabled():
                                    next_request_button = candidate
                                    next_request_found = True
                                    self.log(f"Found next button: {candidate.get_attribute('value') or candidate.text}", "DEBUG")
                                    break
                            except:
                                continue

                        if next_request_found:
                            break

                        if poll_attempt < 14:
                            self.interruptible_sleep(2)  # Wait between polls
                    except:
                        if poll_attempt < 14:
                            self.interruptible_sleep(2)

                if next_request_found and next_request_button:
                    self.log("Found Next Request button - clicking...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_request_button)
                    time.sleep(0.3)
                    next_request_button.click()
                    self.log("Clicked Next Request button", "SUCCESS")

                    try:
                        self.cancellable_wait(15,
                            EC.presence_of_element_located((By.ID, "txtComment"))
                        )
                        self.cancellable_wait(10,
                            lambda driver: driver.execute_script("return document.readyState") == "complete"
                        )
                        self.log("Rejection form loaded", "SUCCESS")
                    except:
                        self.interruptible_sleep(3)

                    request_number += 1
                    continue

                # Check if Reject button still exists (auto-loaded next request)
                try:
                    reject_btn = self.driver.find_element(By.ID, "btnReject")
                    comment_field = self.driver.find_elements(By.ID, "txtComment")
                    if comment_field and reject_btn.is_displayed() and reject_btn.is_enabled():
                        fresh_url = self.driver.current_url
                        if "infoMsg" not in fresh_url:
                            self.log("Next request loaded automatically - continuing...", "SUCCESS")
                            request_number += 1
                            continue
                except:
                    pass

                # Check for definitive exit conditions
                try:
                    cancel_exists = len(self.driver.find_elements(By.XPATH, "//input[@value='Cancel']")) > 0
                    reject_exists = len(self.driver.find_elements(By.ID, "btnReject")) > 0

                    if cancel_exists and not reject_exists:
                        self.log("Found Cancel button only - all requests processed", "SUCCESS")
                        break

                    if not cancel_exists and not reject_exists:
                        self.log("All requests processed", "SUCCESS")
                        break

                    # Reject button exists — page may still be loading. Wait and retry.
                    if reject_exists:
                        self.log("Reject button detected, waiting for page to stabilize...", "WARNING")
                        self.interruptible_sleep(5)
                        try:
                            reject_btn = self.driver.find_element(By.ID, "btnReject")
                            comment_field = self.driver.find_elements(By.ID, "txtComment")
                            if comment_field and reject_btn.is_displayed() and reject_btn.is_enabled():
                                fresh_url = self.driver.current_url
                                if "infoMsg" not in fresh_url:
                                    self.log("Next request loaded after extended wait - continuing...", "SUCCESS")
                                    request_number += 1
                                    continue
                        except:
                            pass
                except:
                    pass

                self.log("Could not find next action - batch complete", "SUCCESS")
                break

            self.log(f"Successfully rejected {rejected_count} user(s)!", "SUCCESS")
            self.report_progress(rejected_count, rejected_count, "Completed")
            return rejected_count

        except OperationCancelledException:
            raise
        except Exception as e:
            self.log(f"Error during rejection: {e}", "ERROR")
            return 0

    def get_all_groups(self):
        """Get all groups from dropdown with retry logic"""
        self.check_cancelled()
        self.log("Retrieving available groups...")

        # Wait for page to be fully ready
        self.interruptible_sleep(3)

        # Try CSS selector first (fastest approach based on what works)
        group_dropdown = None
        try:
            group_dropdown = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "select[name*='group' i], select[id*='group' i]"))
            )
            self.log("Found group dropdown by CSS selector")
        except:
            pass

        # If CSS selector fails, try specific IDs with short timeout
        if not group_dropdown:
            possible_ids = ["cboGroup", "cmbGroup", "selGroup", "group", "groupId"]
            for element_id in possible_ids:
                try:
                    group_dropdown = WebDriverWait(self.driver, 2).until(
                        EC.presence_of_element_located((By.ID, element_id))
                    )
                    self.log(f"Found group dropdown with ID: {element_id}")
                    break
                except:
                    continue

        if not group_dropdown:
            # Debug: log available select elements
            try:
                selects = self.driver.find_elements(By.TAG_NAME, "select")
                self.log(f"Found {len(selects)} select elements on page", "WARNING")
                for i, sel in enumerate(selects[:5]):  # Log first 5
                    sel_id = sel.get_attribute('id') or 'no-id'
                    sel_name = sel.get_attribute('name') or 'no-name'
                    self.log(f"  Select {i+1}: id='{sel_id}', name='{sel_name}'", "WARNING")
            except:
                pass
            self.log("Could not find group dropdown", "ERROR")
            return []

        try:
            select = Select(group_dropdown)

            groups = []
            for option in select.options:
                value = option.get_attribute('value')
                text = option.text.strip()
                if value and text and value != "":
                    groups.append({'value': value, 'name': text})

            self.log(f"Found {len(groups)} group(s)", "SUCCESS")
            return groups

        except Exception as e:
            self.log(f"Error retrieving groups: {e}", "ERROR")
            return []

    def get_all_domains(self):
        """Get all domains from dropdown"""
        self.check_cancelled()
        self.log("Retrieving available domains...")

        try:
            domain_dropdown = self.wait.until(
                EC.presence_of_element_located((By.ID, "selSwitchDomain"))
            )
            select = Select(domain_dropdown)

            domains = []
            for option in select.options:
                text = option.text.strip()
                if text:
                    domains.append(text)

            self.log(f"Found {len(domains)} domain(s)", "SUCCESS")
            return domains

        except Exception as e:
            self.log(f"Error retrieving domains: {e}", "ERROR")
            return []

    def _find_group_dropdown(self):
        """Find the group dropdown using flexible element finding"""
        # Try multiple possible element IDs
        for element_id in ["cboGroup", "cmbGroup", "selGroup", "group", "groupId"]:
            try:
                return self.driver.find_element(By.ID, element_id)
            except:
                continue

        # Fallback to CSS selector
        try:
            return self.driver.find_element(By.CSS_SELECTOR, "select[name*='group' i], select[id*='group' i]")
        except:
            return None

    def _find_user_dropdown(self):
        """Find the user dropdown using flexible element finding"""
        # Try the specific User Group Available User dropdown first, then other common IDs
        for element_id in ["cboUGAvUser", "cboUser", "cmbUser", "selUser", "user", "userId"]:
            try:
                dropdown = self.driver.find_element(By.ID, element_id)
                if dropdown:
                    return dropdown
            except:
                continue

        # Fallback to CSS selector - be more specific for user group page
        selectors = [
            "select#cboUGAvUser",  # Most specific
            "select[name='cboUGAvUser']",
            "select[name*='AvUser' i]",  # Available User
            "select[name*='user' i]",
            "select[id*='user' i]"
        ]
        for selector in selectors:
            try:
                return self.driver.find_element(By.CSS_SELECTOR, selector)
            except:
                continue

        return None

    def _get_user_dropdown_state(self):
        """Capture current user dropdown state for change detection"""
        script = """
        var state = {
            option_count: 0,
            first_option_text: '',
            ajax_active: false
        };

        // Check AJAX status
        if (typeof jQuery !== 'undefined' && jQuery.active > 0) {
            state.ajax_active = true;
        }

        // Find user dropdown (multiple possible IDs)
        var dropdown = document.getElementById('cboUGAvUser') ||
                       document.querySelector("select[name*='AvUser' i]") ||
                       document.querySelector("select[name*='user' i]");

        if (dropdown) {
            state.option_count = dropdown.options.length;
            if (dropdown.options.length > 0) {
                state.first_option_text = dropdown.options[0].text || '';
            }
        }

        return JSON.stringify(state);
        """
        try:
            return self.driver.execute_script(script)
        except:
            return None

    def _wait_for_user_dropdown_loaded(self, timeout=60, previous_state=None):
        """
        Wait for user dropdown to finish loading via AJAX.
        Uses 3-phase strategy: detect start, wait completion, verify stability.

        Args:
            timeout: Maximum seconds to wait
            previous_state: State captured before group selection (for change detection)

        Returns the dropdown element when ready, or None if timeout.
        """
        start_time = time.time()

        # Phase 1: Wait for AJAX to START (state change detection)
        if previous_state is not None:
            phase1_timeout = min(10, timeout // 3)
            self.log("Phase 1: Waiting for AJAX to start...")
            ajax_started = False

            while time.time() - start_time < phase1_timeout:
                self.check_cancelled()
                current_state = self._get_user_dropdown_state()

                # Check if state changed (AJAX started or completed)
                if current_state != previous_state:
                    self.log("Detected dropdown state change")
                    ajax_started = True
                    break

                # Check if AJAX is active
                try:
                    ajax_active = self.driver.execute_script("""
                        return (typeof jQuery !== 'undefined' && jQuery.active > 0);
                    """)
                    if ajax_active:
                        self.log("Detected active AJAX request")
                        ajax_started = True
                        break
                except:
                    pass

                time.sleep(0.3)

            if not ajax_started:
                self.log("No AJAX detected, checking if data already present...", "WARNING")

        # Phase 2: Wait for AJAX to COMPLETE
        self.log("Phase 2: Waiting for AJAX to complete...")
        phase2_start = time.time()
        phase2_timeout = timeout - (phase2_start - start_time)

        while time.time() - phase2_start < phase2_timeout:
            self.check_cancelled()

            try:
                ajax_active = self.driver.execute_script("""
                    if (typeof jQuery !== 'undefined' && jQuery.active > 0) return true;
                    if (typeof $ !== 'undefined' && $.active > 0) return true;
                    return false;
                """)
            except:
                ajax_active = False

            if not ajax_active:
                self.log("AJAX completed")
                break

            time.sleep(0.5)

        # Phase 3: Verify dropdown has options with stability check
        self.log("Phase 3: Verifying dropdown options...")
        stability_checks = 3
        check_interval = 1.0
        last_count = -1
        stable_count = 0
        last_status_log = 0

        remaining_timeout = timeout - (time.time() - start_time)
        phase3_start = time.time()

        while time.time() - phase3_start < remaining_timeout:
            self.check_cancelled()

            # First, check if AJAX is active and wait for it to complete
            try:
                ajax_active = self.driver.execute_script("""
                    return (typeof jQuery !== 'undefined' && jQuery.active > 0);
                """)
            except:
                ajax_active = False

            if ajax_active:
                # Wait for this AJAX request to complete
                ajax_wait_start = time.time()
                self.log("Waiting for AJAX request to complete...")

                while time.time() - ajax_wait_start < 30:  # Wait up to 30s for AJAX
                    self.check_cancelled()
                    try:
                        still_active = self.driver.execute_script("""
                            return (typeof jQuery !== 'undefined' && jQuery.active > 0);
                        """)
                    except:
                        still_active = False

                    if not still_active:
                        self.log("AJAX request completed")
                        self.interruptible_sleep(1)  # Brief delay for DOM to update
                        break

                    # Log progress every 5 seconds
                    elapsed = int(time.time() - ajax_wait_start)
                    if elapsed > 0 and elapsed % 5 == 0 and elapsed != last_status_log:
                        self.log(f"Still waiting for AJAX... ({elapsed}s)")
                        last_status_log = elapsed

                    time.sleep(0.5)
                else:
                    self.log("AJAX taking too long, checking options anyway...", "WARNING")

                stable_count = 0  # Reset stability after AJAX activity

            # Now check dropdown options
            dropdown = self._find_user_dropdown()
            current_count = 0

            if dropdown:
                try:
                    select = Select(dropdown)
                    # Count valid options (non-empty)
                    for opt in select.options:
                        text = opt.text.strip() if opt.text else ""
                        val = opt.get_attribute('value') or ""
                        if text or val:
                            current_count += 1
                except:
                    pass

            # Log status periodically
            elapsed_phase3 = time.time() - phase3_start
            if elapsed_phase3 - last_status_log >= 5:
                self.log(f"Dropdown has {current_count} option(s), waiting for stability...")
                last_status_log = elapsed_phase3

            if current_count > 0:
                if current_count == last_count:
                    stable_count += 1
                    if stable_count >= stability_checks:
                        self.log(f"Found {current_count} user(s) (stable)")
                        return dropdown
                else:
                    stable_count = 1
                    last_count = current_count
                    self.log(f"Found {current_count} option(s), verifying stability...")
            else:
                # Reset if count is 0
                stable_count = 0
                last_count = -1

            self.interruptible_sleep(check_interval)

        self.log("Timeout waiting for users", "WARNING")
        return self._find_user_dropdown()

    def assign_users_to_group(self, group_value, group_name):
        """Assign all available users to a group in batches of 20"""
        self.check_cancelled()
        self.log(f"Assigning users to group: {group_name}")

        BATCH_SIZE = 20

        try:
            # Select group
            group_dropdown = self._find_group_dropdown()
            if not group_dropdown:
                self.log("Could not find group dropdown", "ERROR")
                return 0

            group_select = Select(group_dropdown)

            # Capture state BEFORE group selection
            previous_state = self._get_user_dropdown_state()

            group_select.select_by_value(group_value)
            self.log(f"Selected group: {group_name}", "SUCCESS")

            # Wait for AJAX and user dropdown to load with state change detection
            self.interruptible_sleep(1)  # Brief wait for JavaScript event handlers
            user_dropdown = self._wait_for_user_dropdown_loaded(timeout=60, previous_state=previous_state)
            if not user_dropdown:
                self.log("Could not find user dropdown", "ERROR")
                return 0

            user_select = Select(user_dropdown)
            all_options = user_select.options

            # DEBUG: Log dropdown info
            self.log(f"User dropdown found with {len(all_options)} total options")

            # Count valid users (skip only empty placeholders)
            valid_user_indices = []
            for idx, opt in enumerate(all_options):
                text = opt.text.strip() if opt.text else ""
                val = opt.get_attribute('value') or ""
                # Skip only if BOTH text and value are empty (placeholder)
                if not text and not val:
                    continue
                # This is a valid user
                valid_user_indices.append(idx)
                # Log first few users for debugging
                if len(valid_user_indices) <= 3:
                    self.log(f"  User {idx}: text='{text[:30] if text else ''}' val='{val[:20] if val else ''}'")

            total_users = len(valid_user_indices)

            if total_users <= 0:
                self.log(f"No users available for group {group_name}", "WARNING")
                return 0

            self.log(f"Found {total_users} user(s) to assign")

            assigned = 0
            batch_num = 0

            while True:
                self.check_cancelled()
                batch_num += 1

                # Re-query user dropdown
                user_dropdown = self._find_user_dropdown()
                if not user_dropdown:
                    self.log("User dropdown not found", "WARNING")
                    break

                user_select = Select(user_dropdown)
                options = user_select.options

                # Collect valid user indices (skip only empty placeholders)
                valid_indices = []
                for idx, opt in enumerate(options):
                    text = opt.text.strip() if opt.text else ""
                    val = opt.get_attribute('value') or ""
                    # Skip only if BOTH text and value are empty (placeholder)
                    if not text and not val:
                        continue
                    valid_indices.append(idx)

                if not valid_indices:
                    self.log("No more users to assign")
                    break

                # Select up to BATCH_SIZE users
                batch_indices = valid_indices[:BATCH_SIZE]
                batch_count = len(batch_indices)
                self.log(f"Batch {batch_num}: Selecting {batch_count} user(s)...")

                # Clear previous selection
                try:
                    user_select.deselect_all()
                except:
                    pass

                # Select multiple users
                for idx in batch_indices:
                    try:
                        user_select.select_by_index(idx)
                    except:
                        continue

                time.sleep(0.5)

                # Click Add button
                add_button = self.driver.find_element(By.ID, "btnAdd")
                add_button.click()
                time.sleep(0.5)

                # Handle confirmation dialog
                try:
                    alert = WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                    alert.accept()
                    self.log(f"Confirmed assignment of {batch_count} user(s)", "SUCCESS")
                except:
                    try:
                        ok_button = self.driver.find_element(By.XPATH,
                            "//button[contains(text(),'OK') or contains(text(),'Confirm') or contains(text(),'Yes')]")
                        ok_button.click()
                        self.log(f"Confirmed assignment of {batch_count} user(s)", "SUCCESS")
                    except:
                        pass

                self.interruptible_sleep(2)
                assigned += batch_count
                self.report_progress(assigned, total_users, f"Assigned {assigned}/{total_users} users")

                # Re-select group after batch
                self.interruptible_sleep(1)
                previous_state = self._get_user_dropdown_state()
                group_dropdown = self._find_group_dropdown()
                if group_dropdown:
                    group_select = Select(group_dropdown)
                    group_select.select_by_value(group_value)
                self.interruptible_sleep(1)
                # Wait with state detection for next batch
                user_dropdown = self._wait_for_user_dropdown_loaded(timeout=60, previous_state=previous_state)

            self.log(f"Assigned {assigned} user(s) to {group_name}", "SUCCESS")
            return assigned

        except Exception as e:
            self.log(f"Error assigning users to group: {e}", "ERROR")
            return 0

    def close_browser(self):
        """Close the browser"""
        if self.driver:
            try:
                self.driver.quit()
                self.log("Browser closed", "SUCCESS")
            except:
                pass
            self.driver = None

    def update_callbacks(self, log_callback=None, progress_callback=None, cancel_event=None, auth_method=None):
        """
        Update callbacks on existing bot instance.
        Allows reusing bot while updating GUI callbacks for new workflow.
        """
        if log_callback:
            self.log_callback = log_callback
        if progress_callback:
            self.progress_callback = progress_callback
        if cancel_event:
            self.cancel_event = cancel_event
        if auth_method:
            self.auth_method = auth_method

    def is_session_valid(self):
        """
        Check if the current browser session is still valid and logged in.

        Returns:
            True if browser is responsive and logged into GovCA, False otherwise
        """
        if not self.driver:
            return False

        try:
            # Test if browser is responsive
            _ = self.driver.current_url

            # Check if we're still on GovCA site
            current_url = self.driver.current_url
            if "govca.npki.gov.ph" not in current_url:
                return False

            # Check if domain dropdown exists (indicates logged in)
            # This is a reliable indicator that authentication is still valid
            try:
                domain_dropdown = self.driver.find_element(By.ID, "selSwitchDomain")
                if domain_dropdown.is_displayed():
                    return True
            except:
                pass

            return False

        except Exception:
            # Browser is not responsive or crashed
            return False

    def ensure_valid_session(self):
        """
        Ensure a valid GovCA session exists.

        - If session is valid, reuse it
        - If session is invalid, re-authenticate

        Returns:
            True if session is now valid, False if authentication failed
        """
        if self.is_session_valid():
            self.log("Reusing existing browser session", "SUCCESS")
            return True

        # Session invalid - need to re-authenticate
        self.log("Session expired or invalid, re-authenticating...")

        # Close any existing dead browser
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

        # Setup new browser and authenticate
        self.setup_browser()
        return self.navigate_to_govca()

    # ==================== WORKFLOW METHODS ====================

    def run_approval_process(self, domain="NCR00Sign", comment="Approved via automation",
                             process_counterpart=True, specific_users=None):
        """
        Run the complete approval process (Workflow 1: Add User Batch Approval)
        """
        try:
            self.log("=" * 50)
            self.log("GovCA Approval Automation - Add User")
            self.log("=" * 50)

            # Determine number of phases
            total_phases = 2 if process_counterpart else 1
            current_phase = 1

            # Report initial phase
            self.report_progress(0, 0, "Connecting...", phase=current_phase, total_phases=total_phases, phase_label=domain)

            # Use session persistence - reuse existing session or re-authenticate
            if not self.ensure_valid_session():
                self.log("Failed to connect", "ERROR")
                return False

            self.check_cancelled()

            if not self.select_domain(domain):
                self.log("Failed to select domain", "ERROR")
                return False

            if not self.navigate_to_user_list():
                self.log("Failed to navigate to User List", "ERROR")
                return False

            self.report_progress(0, -1, "Searching for users...", phase=current_phase, total_phases=total_phases, phase_label=domain)

            if not self.search_pending_users():
                self.log(f"No pending users found in {domain}", "WARNING")

                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        self.log(f"Trying counterpart domain: {counterpart}")
                        # Skip to phase 2 since phase 1 had no users
                        current_phase = 2
                        self.report_progress(0, -1, "Searching...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                        if not self.select_domain(counterpart):
                            return False

                        self.interruptible_sleep(3)

                        if not self.navigate_to_user_list():
                            return False

                        if not self.search_pending_users():
                            self.log(f"No pending users in {counterpart} either", "WARNING")
                            self.report_progress(1, 1, "Completed - No users found", phase=total_phases, total_phases=total_phases, phase_label="")
                            return True

                        domain = counterpart
                        process_counterpart = False
                    else:
                        return False
                else:
                    return False

            # Select and approve users
            total_approved = 0

            if specific_users:
                suffix = "_Sign" if "Sign" in domain else "_Auth"
                usernames_to_approve = set(f"{user}{suffix}" for user in specific_users)
                self.log(f"Mode: Specific users - {len(usernames_to_approve)} target(s)")
                total_users = len(usernames_to_approve)

                # Report with known total
                self.report_progress(0, total_users, f"0/{total_users} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

                # Loop to process batches (since selections are lost on page navigation)
                batch_number = 1
                max_batches = 20  # Safety limit

                while batch_number <= max_batches and usernames_to_approve:
                    self.check_cancelled()
                    self.log(f"--- Batch {batch_number}: {len(usernames_to_approve)} user(s) remaining ---")

                    # Select users on current page
                    selected, matched = self.select_specific_users(list(usernames_to_approve))

                    if selected > 0:
                        self.log(f"{selected} user(s) ready for approval (Batch {batch_number})", "SUCCESS")

                        approved_count = self.approve_users(comment)
                        if approved_count and approved_count > 0:
                            total_approved += approved_count
                            # Remove processed users from the list
                            usernames_to_approve -= matched
                            self.log(f"Batch {batch_number}: Approved {approved_count} users", "SUCCESS")
                            # Update progress
                            self.report_progress(total_approved, total_users, f"{total_approved}/{total_users} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

                            if usernames_to_approve:
                                # More users to process - navigate back to user list
                                self.log(f"Remaining users: {len(usernames_to_approve)}")
                                self.interruptible_sleep(2)

                                # Navigate back to search for more users
                                if not self.navigate_to_user_list():
                                    self.log("Failed to navigate back to User List", "ERROR")
                                    break

                                if not self.search_pending_users():
                                    self.log("No more pending users found", "INFO")
                                    break

                                batch_number += 1
                            else:
                                self.log("All specified users have been processed!", "SUCCESS")
                                break
                        else:
                            self.log(f"Batch {batch_number} approval failed", "ERROR")
                            break
                    else:
                        self.log(f"No matching users found (Batch {batch_number})", "WARNING")
                        break

            else:
                self.log("Mode: All pending users")
                selected = self.select_all_pending_users()

                if selected > 0:
                    self.log(f"{selected} user(s) ready for approval", "SUCCESS")
                    self.report_progress(0, selected, f"0/{selected} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

                    approved_count = self.approve_users(comment)
                    if approved_count and approved_count > 0:
                        total_approved = approved_count
                        self.report_progress(approved_count, selected, f"{approved_count}/{selected} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

            if total_approved > 0:
                self.log(f"Successfully approved {total_approved} users in {domain}!", "SUCCESS")

                # Process counterpart (Phase 2)
                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        current_phase = 2
                        self.log("=" * 50)
                        self.log(f"Processing counterpart domain: {counterpart}")
                        self.log("=" * 50)
                        self.report_progress(0, -1, "Switching domain...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                        if self.select_domain(counterpart):
                            self.interruptible_sleep(3)
                            if self.navigate_to_user_list() and self.search_pending_users():
                                if specific_users:
                                    suffix = "_Sign" if "Sign" in counterpart else "_Auth"
                                    remaining = set(f"{user}{suffix}" for user in specific_users)
                                    counterpart_total = len(remaining)
                                    counterpart_approved = 0
                                    self.report_progress(0, counterpart_total, f"0/{counterpart_total} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                                    batch_number = 1
                                    while batch_number <= 20 and remaining:
                                        self.check_cancelled()
                                        sel, matched = self.select_specific_users(list(remaining))
                                        if sel > 0:
                                            approved = self.approve_users(comment)
                                            if approved:
                                                counterpart_approved += approved
                                            remaining -= matched
                                            self.report_progress(counterpart_approved, counterpart_total, f"{counterpart_approved}/{counterpart_total} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                                            if remaining:
                                                self.interruptible_sleep(2)
                                                if not self.navigate_to_user_list() or not self.search_pending_users():
                                                    break
                                                batch_number += 1
                                            else:
                                                break
                                        else:
                                            break
                                else:
                                    sel = self.select_all_pending_users()
                                    if sel > 0:
                                        self.report_progress(0, sel, f"0/{sel} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                                        approved = self.approve_users(comment)
                                        if approved:
                                            self.report_progress(approved, sel, f"{approved}/{sel} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                            else:
                                self.log(f"No pending users in {counterpart}", "INFO")

                # Final completion
                self.report_progress(1, 1, "Completed", phase=total_phases, total_phases=total_phases, phase_label="")
                return True
            else:
                self.log(f"No users selected in {domain}", "WARNING")

                # Try counterpart domain if enabled
                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        current_phase = 2
                        self.log("=" * 50)
                        self.log(f"Trying counterpart domain: {counterpart}")
                        self.log("=" * 50)
                        self.report_progress(0, -1, "Searching...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                        if self.select_domain(counterpart):
                            self.interruptible_sleep(3)
                            if self.navigate_to_user_list() and self.search_pending_users():
                                if specific_users:
                                    suffix = "_Sign" if "Sign" in counterpart else "_Auth"
                                    usernames = [f"{user}{suffix}" for user in specific_users]
                                    sel, _ = self.select_specific_users(usernames)
                                else:
                                    sel = self.select_all_pending_users()

                                if sel > 0:
                                    self.report_progress(0, sel, f"0/{sel} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                                    approved = self.approve_users(comment)
                                    if approved and approved > 0:
                                        self.log(f"Successfully approved {approved} users in {counterpart}!", "SUCCESS")
                                        self.report_progress(1, 1, "Completed", phase=total_phases, total_phases=total_phases, phase_label="")
                                        return True

                self.report_progress(1, 1, "Completed - No users", phase=total_phases, total_phases=total_phases, phase_label="")
                return False

        except OperationCancelledException:
            self.log("Cancelled by user", "WARNING")
            return False
        except WebDriverException as e:
            if self.cancel_event.is_set():
                self.log("Operation cancelled by user", "WARNING")
            else:
                self.log(f"Browser error: {e}", "ERROR")
            return False
        except Exception as e:
            if self.cancel_event.is_set():
                self.log("Operation cancelled by user", "WARNING")
            else:
                self.log(f"Unexpected error: {e}", "ERROR")
            return False

    def run_rejection_process(self, domain="NCR00Sign", comment="Rejected via automation",
                              process_counterpart=True, specific_users=None):
        """
        Run the complete rejection process (Workflow 1: Add User Batch Rejection)
        Similar to approval but clicks Reject instead of Approve.
        """
        try:
            self.log("=" * 50)
            self.log("GovCA Rejection Automation - Add User (REJECT)")
            self.log("=" * 50)

            # Determine number of phases
            total_phases = 2 if process_counterpart else 1
            current_phase = 1

            # Report initial phase
            self.report_progress(0, 0, "Connecting...", phase=current_phase, total_phases=total_phases, phase_label=domain)

            # Use session persistence - reuse existing session or re-authenticate
            if not self.ensure_valid_session():
                self.log("Failed to connect", "ERROR")
                return False

            self.check_cancelled()

            if not self.select_domain(domain):
                self.log("Failed to select domain", "ERROR")
                return False

            if not self.navigate_to_user_list():
                self.log("Failed to navigate to User List", "ERROR")
                return False

            self.report_progress(0, -1, "Searching for users...", phase=current_phase, total_phases=total_phases, phase_label=domain)

            if not self.search_pending_users():
                self.log(f"No pending users found in {domain}", "WARNING")

                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        self.log(f"Trying counterpart domain: {counterpart}")
                        current_phase = 2
                        self.report_progress(0, -1, "Searching...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                        if not self.select_domain(counterpart):
                            return False

                        self.interruptible_sleep(3)

                        if not self.navigate_to_user_list():
                            return False

                        if not self.search_pending_users():
                            self.log(f"No pending users in {counterpart} either", "WARNING")
                            self.report_progress(1, 1, "Completed - No users found", phase=total_phases, total_phases=total_phases, phase_label="")
                            return True

                        domain = counterpart
                        process_counterpart = False
                    else:
                        return False
                else:
                    return False

            # Select and reject users
            total_rejected = 0

            if specific_users:
                suffix = "_Sign" if "Sign" in domain else "_Auth"
                usernames_to_reject = set(f"{user}{suffix}" for user in specific_users)
                self.log(f"Mode: Specific users for REJECTION - {len(usernames_to_reject)} target(s)")
                total_users = len(usernames_to_reject)
                self.report_progress(0, total_users, f"0/{total_users} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

                # Loop to process batches (since selections are lost on page navigation)
                batch_number = 1
                max_batches = 20  # Safety limit

                while batch_number <= max_batches and usernames_to_reject:
                    self.check_cancelled()
                    self.log(f"--- Batch {batch_number}: {len(usernames_to_reject)} user(s) remaining ---")

                    # Select users on current page
                    selected, matched = self.select_specific_users(list(usernames_to_reject))

                    if selected > 0:
                        self.log(f"{selected} user(s) ready for REJECTION (Batch {batch_number})", "WARNING")

                        rejected_count = self.reject_users(comment)
                        if rejected_count and rejected_count > 0:
                            total_rejected += rejected_count
                            # Remove processed users from the list
                            usernames_to_reject -= matched
                            self.log(f"Batch {batch_number}: REJECTED {rejected_count} users", "SUCCESS")
                            self.report_progress(total_rejected, total_users, f"{total_rejected}/{total_users} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

                            if usernames_to_reject:
                                # More users to process - navigate back to user list
                                self.log(f"Remaining users: {len(usernames_to_reject)}")
                                self.interruptible_sleep(2)

                                # Navigate back to search for more users
                                if not self.navigate_to_user_list():
                                    self.log("Failed to navigate back to User List", "ERROR")
                                    break

                                if not self.search_pending_users():
                                    self.log("No more pending users found", "INFO")
                                    break

                                batch_number += 1
                            else:
                                self.log("All specified users have been processed!", "SUCCESS")
                                break
                        else:
                            self.log(f"Batch {batch_number} rejection failed", "ERROR")
                            break
                    else:
                        self.log(f"No matching users found (Batch {batch_number})", "WARNING")
                        break

            else:
                self.log("Mode: All pending users for REJECTION")
                selected = self.select_all_pending_users()

                if selected > 0:
                    self.log(f"{selected} user(s) ready for REJECTION", "WARNING")
                    self.report_progress(0, selected, f"0/{selected} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

                    rejected_count = self.reject_users(comment)
                    if rejected_count and rejected_count > 0:
                        total_rejected = rejected_count
                        self.report_progress(rejected_count, selected, f"{rejected_count}/{selected} users", phase=current_phase, total_phases=total_phases, phase_label=domain)

            if total_rejected > 0:
                self.log(f"Successfully REJECTED {total_rejected} users in {domain}!", "SUCCESS")

                # Process counterpart (Phase 2)
                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        current_phase = 2
                        self.log("=" * 50)
                        self.log(f"Processing counterpart domain for REJECTION: {counterpart}")
                        self.log("=" * 50)
                        self.report_progress(0, -1, "Switching domain...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                        if self.select_domain(counterpart):
                            self.interruptible_sleep(3)
                            if self.navigate_to_user_list() and self.search_pending_users():
                                if specific_users:
                                    suffix = "_Sign" if "Sign" in counterpart else "_Auth"
                                    remaining = set(f"{user}{suffix}" for user in specific_users)
                                    counterpart_total = len(remaining)
                                    counterpart_rejected = 0
                                    self.report_progress(0, counterpart_total, f"0/{counterpart_total} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                                    batch_number = 1
                                    while batch_number <= 20 and remaining:
                                        self.check_cancelled()
                                        sel, matched = self.select_specific_users(list(remaining))
                                        if sel > 0:
                                            rejected = self.reject_users(comment)
                                            if rejected:
                                                counterpart_rejected += rejected
                                            remaining -= matched
                                            self.report_progress(counterpart_rejected, counterpart_total, f"{counterpart_rejected}/{counterpart_total} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                                            if remaining:
                                                self.interruptible_sleep(2)
                                                if not self.navigate_to_user_list() or not self.search_pending_users():
                                                    break
                                                batch_number += 1
                                            else:
                                                break
                                        else:
                                            break
                                else:
                                    sel = self.select_all_pending_users()
                                    if sel > 0:
                                        self.report_progress(0, sel, f"0/{sel} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                                        rejected = self.reject_users(comment)
                                        if rejected:
                                            self.report_progress(rejected, sel, f"{rejected}/{sel} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                self.report_progress(1, 1, "Completed", phase=total_phases, total_phases=total_phases, phase_label="")
                return True
            else:
                self.log(f"No users selected in {domain}", "WARNING")

                # Try counterpart domain if enabled
                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        current_phase = 2
                        self.log("=" * 50)
                        self.log(f"Trying counterpart domain for REJECTION: {counterpart}")
                        self.log("=" * 50)
                        self.report_progress(0, -1, "Searching...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)

                        if self.select_domain(counterpart):
                            self.interruptible_sleep(3)
                            if self.navigate_to_user_list() and self.search_pending_users():
                                if specific_users:
                                    suffix = "_Sign" if "Sign" in counterpart else "_Auth"
                                    usernames = [f"{user}{suffix}" for user in specific_users]
                                    sel, _ = self.select_specific_users(usernames)
                                else:
                                    sel = self.select_all_pending_users()

                                if sel > 0:
                                    self.report_progress(0, sel, f"0/{sel} users", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                                    rejected = self.reject_users(comment)
                                    if rejected and rejected > 0:
                                        self.log(f"Successfully REJECTED {rejected} users in {counterpart}!", "SUCCESS")
                                        self.report_progress(1, 1, "Completed", phase=total_phases, total_phases=total_phases, phase_label="")
                                        return True

                self.report_progress(1, 1, "Completed - No users", phase=total_phases, total_phases=total_phases, phase_label="")
                return False

        except OperationCancelledException:
            self.log("Cancelled by user", "WARNING")
            return False
        except WebDriverException as e:
            if self.cancel_event.is_set():
                self.log("Operation cancelled by user", "WARNING")
            else:
                self.log(f"Browser error: {e}", "ERROR")
            return False
        except Exception as e:
            if self.cancel_event.is_set():
                self.log("Operation cancelled by user", "WARNING")
            else:
                self.log(f"Unexpected error: {e}", "ERROR")
            return False

    def run_revoke_certificate_approval(self, domain="NCR00Sign", comment="Approved via automation", process_counterpart=False):
        """
        Run revoke certificate approval process (Workflow 2)
        """
        try:
            self.log("=" * 50)
            self.log("GovCA Approval Automation - Revoke Certificate")
            self.log("=" * 50)

            # Determine number of phases
            total_phases = 2 if process_counterpart else 1
            current_phase = 1

            self.report_progress(0, 0, "Connecting...", phase=current_phase, total_phases=total_phases, phase_label=domain)

            # Use session persistence - reuse existing session or re-authenticate
            if not self.ensure_valid_session():
                return False

            # Process primary domain
            self.report_progress(0, -1, "Processing...", phase=current_phase, total_phases=total_phases, phase_label=domain)
            primary_count = self._process_revoke_for_domain(domain, comment, current_phase, total_phases)

            # Process counterpart domain if enabled
            if process_counterpart:
                counterpart = self.get_counterpart_domain(domain)
                if counterpart:
                    current_phase = 2
                    self.log("=" * 50)
                    self.log(f"Processing counterpart domain: {counterpart}")
                    self.log("=" * 50)
                    self.report_progress(0, -1, "Switching domain...", phase=current_phase, total_phases=total_phases, phase_label=counterpart)
                    counterpart_count = self._process_revoke_for_domain(counterpart, comment, current_phase, total_phases)
                    self.log(f"Total approved: {primary_count + counterpart_count} revoke request(s)!", "SUCCESS")
                else:
                    self.log(f"Successfully approved {primary_count} revoke request(s)!", "SUCCESS")
            else:
                self.log(f"Successfully approved {primary_count} revoke request(s)!", "SUCCESS")

            self.report_progress(1, 1, "Completed", phase=total_phases, total_phases=total_phases, phase_label="")
            return True

        except OperationCancelledException:
            self.log("Cancelled by user", "WARNING")
            return False
        except WebDriverException as e:
            if self.cancel_event.is_set():
                self.log("Operation cancelled by user", "WARNING")
            else:
                self.log(f"Browser error: {e}", "ERROR")
            return False
        except Exception as e:
            if self.cancel_event.is_set():
                self.log("Operation cancelled by user", "WARNING")
            else:
                self.log(f"Unexpected error: {e}", "ERROR")
            return False

    def _process_revoke_for_domain(self, domain, comment, phase=1, total_phases=1):
        """
        Process revoke certificate approvals for a single domain.
        Returns the number of approved requests.
        """
        if not self.select_domain(domain):
            return 0

        if not self.navigate_to_approval_request_list():
            return 0

        # Search for revoke certificate requests
        self.log("Searching for Revoke Certificate requests...")

        try:
            # Set approval type filter
            approval_type_dropdown = None

            for dropdown_id in ["cboApprovalType", "cmbApprovalType", "selApprovalType"]:
                try:
                    approval_type_dropdown = self.driver.find_element(By.ID, dropdown_id)
                    break
                except:
                    continue

            if approval_type_dropdown:
                select = Select(approval_type_dropdown)
                try:
                    select.select_by_value("7")
                except:
                    select.select_by_visible_text("Revoke Certificate")

            self.interruptible_sleep(1)

            # Capture table state before search
            previous_state = self._get_table_state()

            # Click search
            search_button = self.driver.find_element(By.ID, "btnSearch")
            search_button.click()

            # Wait for filtered results to load
            self.wait_for_table_loaded(timeout=30, previous_state=previous_state)

        except Exception as e:
            self.log(f"Error searching: {e}", "ERROR")
            return 0

        # Process requests one by one
        approved_count = 0
        request_number = 1

        while True:
            self.check_cancelled()
            self.log(f"Processing Request #{request_number}...")
            self.report_progress(request_number, -1, f"Processing request #{request_number}", phase=phase, total_phases=total_phases, phase_label=domain)

            self.interruptible_sleep(2)

            respond_buttons = self.driver.find_elements(By.XPATH, "//a[text()='Respond']")
            if not respond_buttons:
                respond_buttons = self.driver.find_elements(By.XPATH, "//a[contains(text(), 'Respond')]")

            if not respond_buttons:
                page_source = self.driver.page_source.lower()
                if "records not found" in page_source or "no records" in page_source:
                    self.log("No more requests - all processed", "SUCCESS")
                else:
                    self.log("No more Respond buttons found", "SUCCESS")
                break

            self.log(f"Found {len(respond_buttons)} pending request(s)")

            respond_button = respond_buttons[0]
            self.driver.execute_script("arguments[0].scrollIntoView(true);", respond_button)
            time.sleep(0.5)
            respond_button.click()
            self.log("Clicked Respond button", "SUCCESS")

            # Wait for approval page
            self.interruptible_sleep(5)

            try:
                comment_field = self.cancellable_wait(15,
                    EC.presence_of_element_located((By.ID, "txtComment"))
                )
                comment_field.clear()
                comment_field.send_keys(comment)
                self.log(f"Comment added: '{comment}'", "SUCCESS")

                approve_button = self.driver.find_element(By.ID, "btnApprove")
                approve_button.click()
                self.log("Approve button clicked", "SUCCESS")

                try:
                    WebDriverWait(self.driver, 2).until(EC.alert_is_present())
                    alert = self.driver.switch_to.alert
                    alert.accept()
                except:
                    pass

                approved_count += 1
                self.interruptible_sleep(3)

            except Exception as e:
                self.log(f"Error approving request: {e}", "ERROR")
                break

            # Navigate back to list
            if not self.navigate_to_approval_request_list():
                break

            # Re-search with Revoke Certificate filter
            try:
                # Re-find the approval type dropdown (old reference is stale after navigation)
                approval_type_dropdown = None
                for dropdown_id in ["cboApprovalType", "cmbApprovalType", "selApprovalType"]:
                    try:
                        approval_type_dropdown = self.driver.find_element(By.ID, dropdown_id)
                        break
                    except:
                        continue

                if approval_type_dropdown:
                    select = Select(approval_type_dropdown)
                    try:
                        select.select_by_value("7")  # Revoke Certificate
                    except:
                        select.select_by_visible_text("Revoke Certificate")

                self.interruptible_sleep(1)
                previous_state = self._get_table_state()
                search_button = self.driver.find_element(By.ID, "btnSearch")
                search_button.click()
                self.wait_for_table_loaded(timeout=30, previous_state=previous_state)
            except:
                pass

            request_number += 1

        self.log(f"Approved {approved_count} revoke request(s) in {domain}", "SUCCESS")
        return approved_count

    def run_assign_user_group(self, domain="NCR00Sign"):
        """
        Run assign user group process (Workflow 3)
        """
        context = keep.running() if WAKEPY_AVAILABLE else DummyContext()

        with context:
            try:
                self.log("=" * 50)
                self.log(f"GovCA - Assign User Group: {domain}")
                self.log("=" * 50)

                # Single phase for single domain
                self.report_progress(0, 0, "Connecting...", phase=1, total_phases=1, phase_label=domain)

                if not WAKEPY_AVAILABLE:
                    self.log("wakepy not installed - computer may sleep during long operations", "WARNING")

                # Use session persistence - reuse existing session or re-authenticate
                if not self.ensure_valid_session():
                    return False

                if not self.select_domain(domain):
                    return False

                if not self.navigate_to_assign_user_group():
                    return False

                # Get all groups
                groups = self.get_all_groups()
                if not groups:
                    self.log("No groups found", "ERROR")
                    return False

                self.log(f"Will process {len(groups)} group(s)")

                total_assigned = 0
                for i, group in enumerate(groups):
                    self.check_cancelled()
                    self.log(f"Processing Group {i+1}/{len(groups)}: {group['name']}")
                    self.report_progress(i, len(groups), f"Group: {group['name']}", phase=1, total_phases=1, phase_label=domain)

                    assigned = self.assign_users_to_group(group['value'], group['name'])
                    total_assigned += assigned

                self.log("=" * 50)
                self.log(f"Completed! Total assigned: {total_assigned}", "SUCCESS")
                self.log("=" * 50)
                self.report_progress(len(groups), len(groups), "Completed", phase=1, total_phases=1, phase_label="")

                return True

            except OperationCancelledException:
                self.log("Cancelled by user", "WARNING")
                return False
            except WebDriverException as e:
                if self.cancel_event.is_set():
                    self.log("Operation cancelled by user", "WARNING")
                else:
                    self.log(f"Browser error: {e}", "ERROR")
                return False
            except Exception as e:
                if self.cancel_event.is_set():
                    self.log("Operation cancelled by user", "WARNING")
                else:
                    self.log(f"Unexpected error: {e}", "ERROR")
                return False

    def run_assign_user_groups_all_domains(self):
        """
        Run assign user groups across ALL domains (Workflow 4)
        """
        context = keep.running() if WAKEPY_AVAILABLE else DummyContext()

        with context:
            try:
                self.log("=" * 50)
                self.log("GovCA - Assign User Groups (ALL DOMAINS)")
                self.log("=" * 50)

                self.report_progress(0, 0, "Connecting...", phase=1, total_phases=1, phase_label="All Domains")

                if not WAKEPY_AVAILABLE:
                    self.log("wakepy not installed - computer may sleep during long operations", "WARNING")
                    self.log("Install with: pip install wakepy", "INFO")

                # Use session persistence - reuse existing session or re-authenticate
                if not self.ensure_valid_session():
                    return False

                # Get all domains
                domains = self.get_all_domains()
                if not domains:
                    self.log("No domains found", "ERROR")
                    return False

                total_domains = len(domains)
                self.log(f"Will process {total_domains} domain(s)")

                total_domains_processed = 0
                total_groups_processed = 0
                skipped_domains = []

                for d_idx, domain in enumerate(domains):
                    self.check_cancelled()
                    self.log("=" * 50)
                    self.log(f"Domain {d_idx+1}/{total_domains}: {domain}")
                    self.log("=" * 50)
                    # Use domain index as phase for all-domains mode
                    self.report_progress(d_idx, total_domains, f"Domain {d_idx+1}/{total_domains}", phase=d_idx+1, total_phases=total_domains, phase_label=domain)

                    try:
                        if not self.select_domain(domain):
                            skipped_domains.append((domain, "Failed to select"))
                            continue

                        if not self.navigate_to_assign_user_group():
                            skipped_domains.append((domain, "Failed to navigate"))
                            continue

                        groups = self.get_all_groups()
                        if not groups:
                            skipped_domains.append((domain, "No groups found"))
                            continue

                        self.log(f"Found {len(groups)} group(s) in {domain}")

                        for g_idx, group in enumerate(groups):
                            self.check_cancelled()
                            self.log(f"  Group {g_idx+1}/{len(groups)}: {group['name']}")
                            self.assign_users_to_group(group['value'], group['name'])
                            total_groups_processed += 1

                        total_domains_processed += 1

                    except Exception as e:
                        self.log(f"Error processing {domain}: {e}", "ERROR")
                        skipped_domains.append((domain, str(e)))
                        continue

                self.log("=" * 50)
                self.log("ALL DOMAINS COMPLETED!", "SUCCESS")
                self.log(f"Domains processed: {total_domains_processed}/{total_domains}")
                self.log(f"Total groups processed: {total_groups_processed}")
                if skipped_domains:
                    self.log(f"Skipped domains: {len(skipped_domains)}", "WARNING")
                    for d, reason in skipped_domains:
                        self.log(f"  - {d}: {reason}", "WARNING")
                self.log("=" * 50)
                self.report_progress(total_domains, total_domains, "Completed", phase=total_domains, total_phases=total_domains, phase_label="")

                return True

            except OperationCancelledException:
                self.log("Cancelled by user", "WARNING")
                return False
            except WebDriverException as e:
                if self.cancel_event.is_set():
                    self.log("Operation cancelled by user", "WARNING")
                else:
                    self.log(f"Browser error: {e}", "ERROR")
                return False
            except Exception as e:
                if self.cancel_event.is_set():
                    self.log("Operation cancelled by user", "WARNING")
                else:
                    self.log(f"Unexpected error: {e}", "ERROR")
                return False
