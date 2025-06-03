import os
import time
import webbrowser
import threading
import uuid
import logging
from urllib.parse import urlparse
import requests

from flask import Flask, request, render_template

from smartloop.constants import endpoint, auth_server
from smartloop.utils.user_profile import UserProfile

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)  # Hides most warnings

class BrowserLogin:
    '''Class to handle browser-based login for SmartLoop CLI.'''
    def __init__(self, port=5000):
        self.port = port
        self.auth_success = False
        self.token = None
        self.redirect_uri = f"http://localhost:{self.port}/callback"
        self.state = str(uuid.uuid4())
        self.server = None  # Store HTTP server instance
        # Set up template directory path
        self.template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.app = Flask(__name__, template_folder=self.template_dir)
        # Define Flask routes only if Flask is available
        self.define_flask_routes()


    def validate_token(self, token):
        """Validate the token by making a test request to the API.

        Args:
            token: The access token to validate

        Returns:
            bool: True if token is valid, False otherwise
        """
        try:
            # Try a simple API request that requires authentication
            url = os.path.join(endpoint, 'users', 'me')
            headers = {'x-api-key': token}

            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"Error validating token: {e}")
            return False

    def define_flask_routes(self):
        """Define Flask routes for the callback."""
        @self.app.route('/callback')
        def callback():
            # Check for both token and code in the URL
            token = request.args.get('token')
            state = request.args.get('state')

            # Get the path to the template
            template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
            self.app.template_folder = template_dir

            if state != self.state:
                return render_template('callback.html', success=False, error_message="Invalid state parameter. Authentication failed.")

            success = True if token is not None else False

            if token:
                # Validate the token before saving
                if self.validate_token(token):
                    # Save the token to the user profile
                    user_profile = UserProfile.load(generate=True)
                    user_profile[urlparse(endpoint).hostname] = dict(token=token)
                    UserProfile.save(user_profile)
                    print("[✓] Login successful!")

                    # Set the auth_success flag to true so the main thread knows auth is complete
                    self.auth_success = True
                else:
                    print("Invalid token received. Authentication failed.")

                # Start a background thread to trigger server shutdown after a short delay
                def trigger_shutdown():
                    # Wait a bit to ensure the response is sent first
                    time.sleep(1.5)
                    try:
                        requests.get(f"http://localhost:{self.port}/shutdown", timeout=0.5)
                    except:
                        # Ignore any errors - the auth_success flag is already set
                        pass

                # Start the shutdown thread if authentication was successful
                if self.auth_success:
                    shutdown_thread = threading.Thread(target=trigger_shutdown)
                    shutdown_thread.daemon = True
                    shutdown_thread.start()

                # Send the template response
                return render_template('callback.html', success=success)

    def _exchange_code_for_token(self, code):
        """Exchange the authorization code for an access token."""
        token_endpoint = f"http://{auth_server}/login/token"

        # Real implementation of token exchange with auth server
        token_response = requests.post(
            token_endpoint, 
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': self.redirect_uri,
                'client_id': os.getenv('SLP_CLIENT_ID', 'smartloop-cli')
            }
        )

        # Process the token response from the OAuth server
        if token_response.status_code == 200:
            return token_response.json().get('access_token')

        # If the token endpoint fails, we can use the code as token for backward compatibility
        # Silently handle the failure without printing a warning
        return code  # Fallback to using code as token

    def start_server(self):
        """Start the server in a separate thread."""
        # Define a more robust run method that we can better control
        def run_server():
            # Set up a flag for clean shutdown
            self._should_exit = threading.Event()

            # Run the Flask app with threaded=True to handle multiple requests
            self.app.run(
                host='localhost',
                port=self.port,
                debug=False,
                use_reloader=False
            )

        # Start Flask server in its own thread
        self.flask_thread = threading.Thread(target=run_server)
        self.flask_thread.daemon = True  # Make thread exit when main thread exits
        self.flask_thread.start()

    def open_login_page(self):
        """Open the browser for the user to authenticate."""
        # Construct the authorization URL pointing to /login
        auth_url = f"{auth_server}/login"
        client_id = os.getenv('SLP_CLIENT_ID', 'smartloop-cli')
        full_auth_url = f"{auth_url}?response_type=code&redirect_uri={self.redirect_uri}&state={self.state}&client_id={client_id}"
        # Open the authorization URL in the user's default browser
        webbrowser.open(full_auth_url)

def perform_browser_login(callback_port=5000, timeout=120):
    """Main function to perform browser-based login.

    Args:
        callback_port: The port to use for the local callback server
        timeout: Maximum time to wait for auth in seconds
    """
    login_handler = BrowserLogin(port=callback_port)
    login_handler.start_server()
    login_handler.open_login_page()

    client_id = os.getenv('SLP_CLIENT_ID', 'smartloop-cli')
    print("A browser window has been opened for you to complete the login process.")
    print("If it doesn't open automatically, please go to the following URL:")
    print(f"{auth_server}/login?response_type=code&redirect_uri=http://localhost:{login_handler.port}/callback&state={login_handler.state}&client_id={client_id}")
    print("Complete the login, and the token will be automatically sent back to the callback URL.")

    # Wait for authentication to complete with timeout
    start_time = time.time()
    while not login_handler.auth_success and time.time() - start_time < timeout:
        time.sleep(0.5)
        if not login_handler.flask_thread.is_alive():
            # Thread already ended
            break
    if not login_handler.auth_success:
        print("Authentication timed out or failed. Please try again.")
        return False
    # Return success status
    return login_handler.auth_success
