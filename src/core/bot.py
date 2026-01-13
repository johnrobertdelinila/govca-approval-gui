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
from selenium.common.exceptions import TimeoutException
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

    def __init__(self, firefox_profile_path=None, log_callback=None, progress_callback=None, cancel_event=None):
        """
        Initialize the bot with optional GUI callbacks.

        Args:
            firefox_profile_path: Path to Firefox profile (auto-detected if None)
            log_callback: Function to call for logging (message, level)
            progress_callback: Function to call for progress updates (current, total, message)
            cancel_event: threading.Event to signal cancellation
        """
        self.driver = None
        self.wait = None
        self.firefox_profile_path = firefox_profile_path
        self.log_callback = log_callback or self._default_log
        self.progress_callback = progress_callback or (lambda *args: None)
        self.cancel_event = cancel_event or threading.Event()

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

    def report_progress(self, current, total, message=""):
        """Report progress through the callback"""
        self.progress_callback(current, total, message)

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
        WebDriverWait(self.driver, timeout).until(page_is_ready)

    def wait_for_table_loaded(self, timeout=30):
        """
        Wait for the search results table to finish loading.
        Returns True when data rows are present, False when table is empty.
        """
        # Phase 1: Wait for AJAX to start (brief delay so old data clears)
        time.sleep(1)

        def table_is_ready(driver):
            script = """
            // Check if any loading indicator is visible
            var processing = document.querySelector('.dataTables_processing');
            if (processing) {
                var style = window.getComputedStyle(processing);
                if (style.display !== 'none' && style.visibility !== 'hidden') {
                    return null;  // Still loading
                }
            }

            // Check for jQuery AJAX in progress
            if (typeof jQuery !== 'undefined' && jQuery.active > 0) {
                return null;  // AJAX still running
            }

            // Try multiple checkbox selectors (GovCA may use different names)
            var checkboxSelectors = [
                'input[type="checkbox"][name="chkBatch"]',
                'input[type="checkbox"][name*="chk"]',
                'table tbody input[type="checkbox"]'
            ];

            for (var i = 0; i < checkboxSelectors.length; i++) {
                var checkboxes = document.querySelectorAll(checkboxSelectors[i]);
                // Filter to only visible checkboxes
                var visibleCount = 0;
                for (var j = 0; j < checkboxes.length; j++) {
                    if (checkboxes[j].offsetParent !== null) {
                        visibleCount++;
                    }
                }
                if (visibleCount > 0) {
                    return 'has_data';
                }
            }

            // Check for empty table indicators via text
            var emptyText = document.body.innerText;
            if (emptyText.includes('No data available') ||
                emptyText.includes('No matching records') ||
                emptyText.includes('No records found')) {
                return 'empty';
            }

            // Check for DataTables empty class
            var emptyCell = document.querySelector('.dataTables_empty, td.dataTables_empty');
            if (emptyCell && emptyCell.offsetParent !== null) {
                return 'empty';
            }

            return null;  // Still loading
            """
            return driver.execute_script(script)

        self.log("Waiting for search results to load...")
        self.check_cancelled()

        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: table_is_ready(d) is not None
            )
            final_result = table_is_ready(self.driver)

            if final_result == 'has_data':
                self.log("Search results loaded", "SUCCESS")
                return True
            else:
                self.log("Table loaded (no data)", "INFO")
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
            # Clean up lock files to allow access (required for hardware tokens)
            self._cleanup_profile_locks(profile_path)
            # Ensure SafeNet eToken PKCS#11 module is registered
            self._ensure_safenet_module(profile_path)
            options.add_argument("-profile")
            options.add_argument(profile_path)
        else:
            self.log("Could not find Firefox profile. Certificate authentication may fail.", "WARNING")

        # Set preferences for certificate handling
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
            self.driver.maximize_window()
            self.log("Firefox started successfully", "SUCCESS")
            # Allow PKCS#11 module and hardware token to fully initialize
            self.log("Waiting for SafeNet eToken to initialize...")
            time.sleep(3)

        except Exception as e:
            self.log(f"Error starting Firefox: {e}", "ERROR")
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

                self.log("If certificate dialog appears, select your certificate", "WARNING")
                self.log("Waiting 5 seconds...")
                time.sleep(5)

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
                        time.sleep(5)
                        continue
                    else:
                        self.log(f"SSL authentication failed after {max_retries} attempts", "ERROR")
                        self.log("Please ensure your SafeNet eToken is properly connected", "INFO")
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
            time.sleep(3)

            self.check_cancelled()

            if "approve_list" in self.driver.current_url:
                self.log("Approval Request List page loaded", "SUCCESS")
                return True
            else:
                self.log("Verifying page load...")
                time.sleep(2)
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
            time.sleep(3)

            self.check_cancelled()

            if "user_group" in self.driver.current_url:
                self.log("Assign User Group page loaded", "SUCCESS")
                return True
            else:
                self.log("Verifying page load...")
                time.sleep(2)
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
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "cmbStatus"))
                    )
                    time.sleep(1)

                    status_dropdown = self.driver.find_element(By.ID, "cmbStatus")
                    select = Select(status_dropdown)

                    try:
                        select.select_by_value("4")  # Pending
                    except:
                        select.select_by_visible_text("Pending")

                    self.log("User Status set to 'Pending'", "SUCCESS")
                    filter_set = True
                    time.sleep(1)
                    break

                except Exception as e:
                    if filter_attempt < max_filter_retries - 1:
                        self.log(f"Could not set filter (attempt {filter_attempt + 1}/{max_filter_retries}): {e}", "WARNING")
                        time.sleep(2)
                    else:
                        self.log(f"Failed to set User Status filter after {max_filter_retries} attempts", "WARNING")

            if not filter_set:
                self.log("Pending filter not applied - results may include non-pending users", "WARNING")

            self.check_cancelled()

            # Click Search button
            search_button = self.driver.find_element(By.ID, "btnSearch")
            search_button.click()
            self.log("Search button clicked", "SUCCESS")

            # Wait for table to load using event-driven detection
            if self.wait_for_table_loaded(timeout=30):
                # Count the checkboxes (table has data)
                checkboxes = self.driver.find_elements(
                    By.CSS_SELECTOR, "#tblUser tbody input[type='checkbox'][name='chkBatch']"
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
            time.sleep(2)

            # Try "Select All" checkbox first
            try:
                select_all = self.driver.find_element(By.ID, "chkAllBatch")
                if select_all.is_displayed() and select_all.is_enabled():
                    self.driver.execute_script("arguments[0].click();", select_all)
                    self.log("Clicked 'Select All' checkbox", "SUCCESS")
                    time.sleep(1)

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

                time.sleep(5)

                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']"))
                    )
                except:
                    # No checkboxes found = no more pending users
                    self.log("No more pending users found", "INFO")
                    break

                checkbox_count = len(self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']"))
                self.log(f"Found {checkbox_count} data rows on page {current_page}")

                time.sleep(3)

                # Get usernames on current page
                page_usernames = []
                try:
                    checkboxes = self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox'][name='chkBatch']")
                    for cb in checkboxes:
                        try:
                            row = cb.find_element(By.XPATH, "./ancestor::tr[1]")
                            cells = row.find_elements(By.XPATH, "./td")
                            if 3 <= len(cells) <= 15:
                                for cell in cells[1:4]:
                                    cell_text = cell.text.strip()
                                    if cell_text and '_' in cell_text and len(cell_text) < 100:
                                        page_usernames.append(cell_text)
                                        break
                        except:
                            continue
                except:
                    pass

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

                    break
                else:
                    self.log(f"No matching users on page {current_page}", "WARNING")

                    if self.has_next_page():
                        if self.go_to_next_page():
                            current_page += 1
                            continue
                        else:
                            self.log("Failed to navigate to next page", "ERROR")
                            break
                    else:
                        self.log("No more pages to check", "INFO")
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
        try:
            next_btn = self.driver.find_element(By.XPATH, "//a[.//img[contains(@src, 'next_page')]]")
            return next_btn.is_displayed()
        except:
            return False

    def go_to_next_page(self):
        """Navigate to next page by clicking the pagination button"""
        try:
            next_btn = self.driver.find_element(By.XPATH, "//a[.//img[contains(@src, 'next_page')]]")
            if not next_btn.is_displayed():
                return False

            # Scroll the button into view
            self.driver.execute_script("arguments[0].scrollIntoView(true);", next_btn)
            time.sleep(0.5)

            # Use Selenium's native click
            next_btn.click()
            time.sleep(5)

            # Wait for page to be ready
            WebDriverWait(self.driver, 10).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            return True

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
            time.sleep(1)

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

                WebDriverWait(self.driver, 15).until(approval_page_loaded)

                all_windows = self.driver.window_handles
                if len(all_windows) > 1:
                    self.log("Detected popup window, switching to it...")
                    for window in all_windows:
                        if window != original_window:
                            self.driver.switch_to.window(window)
                            break

                    WebDriverWait(self.driver, 10).until(
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                else:
                    self.log("Navigated to approval page", "SUCCESS")

            except Exception as e:
                self.log(f"Navigation wait timeout: {e}", "WARNING")

            WebDriverWait(self.driver, 15).until(
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
                self.report_progress(approved_count, -1, f"Processing request #{request_number}")

                # Add comment
                try:
                    comment_field = WebDriverWait(self.driver, 15).until(
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
                    approve_button = WebDriverWait(self.driver, 15).until(
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
                time.sleep(7)

                self.check_cancelled()

                # Wait for page ready
                try:
                    WebDriverWait(self.driver, 20).until(
                        lambda driver: driver.execute_script("return document.readyState") == "complete"
                    )
                    time.sleep(2)
                except:
                    time.sleep(5)

                # Check for completion
                current_url = self.driver.current_url

                if "infoMsg" in current_url:
                    self.log("Redirected to success page - batch complete", "SUCCESS")
                    break

                if "batch=1" not in current_url:
                    self.log("No longer in batch mode - batch complete", "SUCCESS")
                    break

                # Look for Next Request button
                next_request_found = False
                next_request_button = None

                for poll_attempt in range(5):
                    self.check_cancelled()
                    try:
                        candidates = []
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[@value='Next Request']"))
                        candidates.extend(self.driver.find_elements(By.XPATH, "//input[contains(@value, 'Next')][@type='button']"))

                        for candidate in candidates:
                            try:
                                if candidate.is_displayed() and candidate.is_enabled():
                                    next_request_button = candidate
                                    next_request_found = True
                                    break
                            except:
                                continue

                        if next_request_found:
                            break

                        if poll_attempt < 4:
                            time.sleep(3)
                    except:
                        if poll_attempt < 4:
                            time.sleep(3)

                if next_request_found and next_request_button:
                    self.log("Found Next Request button - clicking...")
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", next_request_button)
                    time.sleep(0.3)
                    next_request_button.click()
                    self.log("Clicked Next Request button", "SUCCESS")

                    try:
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_element_located((By.ID, "txtComment"))
                        )
                        WebDriverWait(self.driver, 10).until(
                            lambda driver: driver.execute_script("return document.readyState") == "complete"
                        )
                        self.log("Approval form loaded", "SUCCESS")
                    except:
                        time.sleep(3)

                    request_number += 1
                    continue

                # Check if Approve button still exists (auto-loaded next request)
                try:
                    approve_btn = self.driver.find_element(By.ID, "btnApprove")
                    comment_field = self.driver.find_elements(By.ID, "txtComment")
                    if comment_field and approve_btn.is_displayed() and approve_btn.is_enabled():
                        if "batch=1" in current_url and "infoMsg" not in current_url:
                            self.log("Next request loaded automatically - continuing...", "SUCCESS")
                            request_number += 1
                            continue
                except:
                    pass

                # Check for cancel only
                try:
                    cancel_exists = len(self.driver.find_elements(By.XPATH, "//input[@value='Cancel']")) > 0
                    approve_exists = len(self.driver.find_elements(By.ID, "btnApprove")) > 0

                    if cancel_exists and not approve_exists:
                        self.log("Found Cancel button only - all requests processed", "SUCCESS")
                        break

                    if not approve_exists:
                        self.log("All requests processed", "SUCCESS")
                        break
                except:
                    pass

                self.log("Could not find next action - batch complete", "SUCCESS")
                break

            self.log(f"Successfully approved {approved_count} user(s)!", "SUCCESS")
            self.report_progress(approved_count, approved_count, "Completed")
            return True

        except OperationCancelledException:
            raise
        except Exception as e:
            self.log(f"Error during approval: {e}", "ERROR")
            return False

    def get_all_groups(self):
        """Get all groups from dropdown with retry logic"""
        self.check_cancelled()
        self.log("Retrieving available groups...")

        # Wait for page to be fully ready
        time.sleep(3)

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
            group_select.select_by_value(group_value)
            self.log(f"Selected group: {group_name}", "SUCCESS")

            time.sleep(5)  # Reduced from 10
            self.check_cancelled()

            # Wait for user dropdown to populate (reduced wait time for faster processing)
            max_wait = 15  # Reduced from 60
            waited = 0
            dropdown_found = False
            while waited < max_wait:
                self.check_cancelled()
                try:
                    user_dropdown = self._find_user_dropdown()
                    if user_dropdown:
                        dropdown_found = True
                        user_select = Select(user_dropdown)
                        # Count options with either value OR text
                        valid_count = 0
                        for opt in user_select.options:
                            text = opt.text.strip() if opt.text else ""
                            val = opt.get_attribute('value') or ""
                            # Skip only if BOTH text and value are empty (placeholder)
                            if not text and not val:
                                continue
                            valid_count += 1
                        if valid_count > 0:
                            break
                        # Dropdown found but empty - give a few more seconds then move on
                        if waited >= 5:
                            break
                except:
                    pass
                time.sleep(2)  # Reduced from 5
                waited += 2

            # Get user dropdown and count users
            user_dropdown = self._find_user_dropdown()
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

                time.sleep(2)
                assigned += batch_count
                self.report_progress(assigned, total_users, f"Assigned {assigned}/{total_users} users")

                # Re-select group
                time.sleep(1)
                group_dropdown = self._find_group_dropdown()
                if group_dropdown:
                    group_select = Select(group_dropdown)
                    group_select.select_by_value(group_value)
                time.sleep(3)

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

            self.setup_browser()

            if not self.navigate_to_govca():
                self.log("Failed to connect", "ERROR")
                return False

            self.check_cancelled()

            if not self.select_domain(domain):
                self.log("Failed to select domain", "ERROR")
                return False

            if not self.navigate_to_user_list():
                self.log("Failed to navigate to User List", "ERROR")
                return False

            if not self.search_pending_users():
                self.log(f"No pending users found in {domain}", "WARNING")

                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        self.log(f"Trying counterpart domain: {counterpart}")

                        if not self.select_domain(counterpart):
                            return False

                        time.sleep(3)

                        if not self.navigate_to_user_list():
                            return False

                        if not self.search_pending_users():
                            self.log(f"No pending users in {counterpart} either", "WARNING")
                            return True

                        domain = counterpart
                        process_counterpart = False
                    else:
                        return False
                else:
                    return False

            # Select users
            if specific_users:
                suffix = "_Sign" if "Sign" in domain else "_Auth"
                usernames_to_approve = [f"{user}{suffix}" for user in specific_users]
                self.log(f"Mode: Specific users - {len(usernames_to_approve)} target(s)")
                selected, matched = self.select_specific_users(usernames_to_approve)
            else:
                self.log("Mode: All pending users")
                selected = self.select_all_pending_users()

            if selected > 0:
                self.log(f"{selected} user(s) ready for approval", "SUCCESS")

                if self.approve_users(comment):
                    self.log(f"Successfully approved {selected} users in {domain}!", "SUCCESS")

                    # Process counterpart
                    if process_counterpart:
                        counterpart = self.get_counterpart_domain(domain)
                        if counterpart:
                            self.log("=" * 50)
                            self.log(f"Processing counterpart domain: {counterpart}")
                            self.log("=" * 50)

                            if self.select_domain(counterpart):
                                time.sleep(3)
                                if self.navigate_to_user_list() and self.search_pending_users():
                                    if specific_users:
                                        suffix = "_Sign" if "Sign" in counterpart else "_Auth"
                                        usernames = [f"{user}{suffix}" for user in specific_users]
                                        sel, _ = self.select_specific_users(usernames)
                                    else:
                                        sel = self.select_all_pending_users()

                                    if sel > 0:
                                        self.approve_users(comment)

                    return True
                else:
                    self.log("Approval failed", "ERROR")
                    return False
            else:
                self.log(f"No users selected in {domain}", "WARNING")

                # Try counterpart domain if enabled
                if process_counterpart:
                    counterpart = self.get_counterpart_domain(domain)
                    if counterpart:
                        self.log("=" * 50)
                        self.log(f"Trying counterpart domain: {counterpart}")
                        self.log("=" * 50)

                        if self.select_domain(counterpart):
                            time.sleep(3)
                            if self.navigate_to_user_list() and self.search_pending_users():
                                if specific_users:
                                    suffix = "_Sign" if "Sign" in counterpart else "_Auth"
                                    usernames = [f"{user}{suffix}" for user in specific_users]
                                    sel, _ = self.select_specific_users(usernames)
                                else:
                                    sel = self.select_all_pending_users()

                                if sel > 0:
                                    if self.approve_users(comment):
                                        self.log(f"Successfully approved {sel} users in {counterpart}!", "SUCCESS")
                                        return True

                return False

        except OperationCancelledException:
            self.log("Cancelled by user", "WARNING")
            return False
        except Exception as e:
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

            self.setup_browser()

            if not self.navigate_to_govca():
                return False

            # Process primary domain
            primary_count = self._process_revoke_for_domain(domain, comment)

            # Process counterpart domain if enabled
            if process_counterpart:
                counterpart = self.get_counterpart_domain(domain)
                if counterpart:
                    self.log("=" * 50)
                    self.log(f"Processing counterpart domain: {counterpart}")
                    self.log("=" * 50)
                    counterpart_count = self._process_revoke_for_domain(counterpart, comment)
                    self.log(f"Total approved: {primary_count + counterpart_count} revoke request(s)!", "SUCCESS")
                else:
                    self.log(f"Successfully approved {primary_count} revoke request(s)!", "SUCCESS")
            else:
                self.log(f"Successfully approved {primary_count} revoke request(s)!", "SUCCESS")

            return True

        except OperationCancelledException:
            self.log("Cancelled by user", "WARNING")
            return False
        except Exception as e:
            self.log(f"Unexpected error: {e}", "ERROR")
            return False

    def _process_revoke_for_domain(self, domain, comment):
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

            time.sleep(1)

            # Click search
            search_button = self.driver.find_element(By.ID, "btnSearch")
            search_button.click()
            time.sleep(5)

        except Exception as e:
            self.log(f"Error searching: {e}", "ERROR")
            return 0

        # Process requests one by one
        approved_count = 0
        request_number = 1

        while True:
            self.check_cancelled()
            self.log(f"Processing Request #{request_number}...")
            self.report_progress(approved_count, -1, f"Processing request #{request_number}")

            time.sleep(2)

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
            time.sleep(5)

            try:
                comment_field = WebDriverWait(self.driver, 15).until(
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
                time.sleep(3)

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

                time.sleep(1)
                search_button = self.driver.find_element(By.ID, "btnSearch")
                search_button.click()
                time.sleep(5)
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

                if not WAKEPY_AVAILABLE:
                    self.log("wakepy not installed - computer may sleep during long operations", "WARNING")

                self.setup_browser()

                if not self.navigate_to_govca():
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
                    self.report_progress(i, len(groups), f"Group: {group['name']}")

                    assigned = self.assign_users_to_group(group['value'], group['name'])
                    total_assigned += assigned

                self.log("=" * 50)
                self.log(f"Completed! Total assigned: {total_assigned}", "SUCCESS")
                self.log("=" * 50)
                self.report_progress(len(groups), len(groups), "Completed")

                return True

            except OperationCancelledException:
                self.log("Cancelled by user", "WARNING")
                return False
            except Exception as e:
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

                if not WAKEPY_AVAILABLE:
                    self.log("wakepy not installed - computer may sleep during long operations", "WARNING")
                    self.log("Install with: pip install wakepy", "INFO")

                self.setup_browser()

                if not self.navigate_to_govca():
                    return False

                # Get all domains
                domains = self.get_all_domains()
                if not domains:
                    self.log("No domains found", "ERROR")
                    return False

                self.log(f"Will process {len(domains)} domain(s)")

                total_domains_processed = 0
                total_groups_processed = 0
                skipped_domains = []

                for d_idx, domain in enumerate(domains):
                    self.check_cancelled()
                    self.log("=" * 50)
                    self.log(f"Domain {d_idx+1}/{len(domains)}: {domain}")
                    self.log("=" * 50)
                    self.report_progress(d_idx, len(domains), f"Domain: {domain}")

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
                self.log(f"Domains processed: {total_domains_processed}/{len(domains)}")
                self.log(f"Total groups processed: {total_groups_processed}")
                if skipped_domains:
                    self.log(f"Skipped domains: {len(skipped_domains)}", "WARNING")
                    for d, reason in skipped_domains:
                        self.log(f"  - {d}: {reason}", "WARNING")
                self.log("=" * 50)
                self.report_progress(len(domains), len(domains), "Completed")

                return True

            except OperationCancelledException:
                self.log("Cancelled by user", "WARNING")
                return False
            except Exception as e:
                self.log(f"Unexpected error: {e}", "ERROR")
                return False
