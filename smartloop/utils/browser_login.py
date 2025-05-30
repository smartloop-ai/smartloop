import os
import sys
import time
import webbrowser
import threading
import uuid
import json
import logging
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

from smartloop.constants import endpoint, homedir
from smartloop.utils.user_profile import UserProfile
from pathlib import Path

# Try to import Flask, but provide a fallback if not available
try:
    from flask import Flask, request, render_template, render_template_string
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("Flask is not installed. Using simple HTTP server for authentication.")
    Flask = None

class BrowserLogin:
    def __init__(self, port=5000):
        self.port = port
        self.auth_success = False
        self.token = None
        self.redirect_uri = f"http://localhost:{self.port}/callback"
        self.state = str(uuid.uuid4())
        self.server = None  # Store HTTP server instance
        if FLASK_AVAILABLE:
            self.app = Flask(__name__)
            # Define Flask routes only if Flask is available
            self.define_flask_routes()
        else:
            # Use a simple HTTP server if Flask is not available
            print("Flask is not available, using simple HTTP server.")
            self.app = None
    
    def define_flask_routes(self):
        """Define Flask routes for the callback."""
        # Add shutdown route for clean shutdown
        @self.app.route('/success')
        def success():
            """Handle silent server shutdown after successful authentication."""
            # Get the werkzeug shutdown function
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                # Alternative method for newer versions of Werkzeug
                try:
                    # Only import if needed to avoid import errors
                    import importlib
                    if importlib.util.find_spec('werkzeug.serving'):
                        import werkzeug.serving
                        # Get the base server from werkzeug
                        werkzeug.serving.is_running_from_reloader = lambda: False
                except Exception:
                    pass
            else:
                func()  # Call the shutdown function
                
            return "Authentication successful! You can keep this window open if you prefer."
            
        @self.app.route('/callback')
        def callback():
            # Check for both token and code in the URL
            token = request.args.get('token')
            code = request.args.get('code')  # Get the code parameter even if we prioritize token
            state = request.args.get('state')
            
            # Get the path to the template
            template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
            self.app.template_folder = template_dir
            
            # Check if template exists, fallback to inline if not
            template_path = os.path.join(template_dir, 'callback.html')
            template_exists = os.path.isfile(template_path)
            
            if state != self.state:
                if template_exists:
                    return render_template('callback.html', 
                                           success=False, 
                                           error_message="Invalid state parameter. Authentication failed.")
                else:
                    return render_template_string("""
                    <html>
                    <head>
                        <title>Authentication Error</title>
                        <link rel="preconnect" href="https://fonts.googleapis.com">
                        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600<title>Authentication Error</title>display=swap" rel="stylesheet">
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            body, html {
                                font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                                background-color: #1b1b1b;
                                color: #f0f0f0;
                                line-height: 1;
                                height: 100%;
                                width: 100%;
                                margin: 0;
                                padding: 0;
                                text-align: center;
                                -webkit-font-smoothing: antialiased;
                                -moz-osx-font-smoothing: grayscale;
                            }
                            .container {
                                background-color: #252525;
                                border-radius: 8px;
                                padding: 30px;
                                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                                margin: 60px auto;
                                max-width: 500px;
                            }
                            h1 {
                                font-size: 1.8rem;
                                margin-bottom: 20px;
                                color: #ffffff;
                            }
                            p {
                                margin: 12px 0;
                                font-size: 1rem;
                                line-height: 1.5;
                            }
                            .error {
                                color: #ff3b30;
                            }
                            .logo {
                                width: 180px;
                                height: auto;
                                margin-bottom: 24px;
                                filter: brightness(0) invert(1);
                            }
                        </style>
                    </head>
                    <body>                                <div class="container">
                                    <img src="https://app.smartloop.ai/img/logo.svg" alt="Smartloop" class="logo">
                                    <h1>Authentication Error</h1>
                                    <div class="code-message">
                                        <div class="code-header">error</div>
                                        <span class="error">> Invalid state parameter.</span><br>
                                        <span style="color: #aaaaaa; font-size: 0.85rem;">> Please try again by running <code>smartloop login</code> in your terminal.</span>
                                    </div>
                        </div>
                    </body>
                    </html>
                    """)

            if token:
                # Prioritize token if present
                self.token = token
                self.auth_success = True
                
                if template_exists:
                    return render_template('callback.html', success=True)
                else:
                    return render_template_string("""
                    <html>
                    <head>
                        <title>Smartloop Authentication Success</title>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <link rel="preconnect" href="https://fonts.googleapis.com">
                        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
                        <style>
                            body, html {
                                font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                                background-color: #1b1b1b;
                                color: #f0f0f0;
                                line-height: 1;
                                height: 100%;
                                width: 100%;
                                margin: 0;
                                padding: 0;
                                text-align: center;
                                -webkit-font-smoothing: antialiased;
                                -moz-osx-font-smoothing: grayscale;
                                min-width: 320px;
                            }
                            .container {
                                background-color: #252525;
                                border-radius: 8px;
                                padding: 30px;
                                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                                margin: 60px auto;
                                max-width: 500px;
                                transition: all 0.3s ease;
                            }
                            .container:hover {
                                box-shadow: 0 12px 28px rgba(0,0,0,0.3);
                            }
                            h1 {
                                font-size: 1.8rem;
                                margin-bottom: 20px;
                                color: #ffffff;
                            }
                            p {
                                margin: 12px 0;
                                font-size: 1rem;
                                line-height: 1.5;
                            }                                    .success {
                                        color: #4cd964;
                                    }
                                    .logo {
                                        width: 180px;
                                        height: auto;
                                        margin-bottom: 24px;
                                        filter: brightness(0) invert(1);
                                    }
                                    .code-message {
                                        background-color: #1e1e1e;
                                        border-radius: 6px;
                                        border: 1px solid #444;
                                        font-family: 'Courier New', monospace;
                                        color: #4cd964;
                                        padding: 20px;
                                        text-align: left;
                                        margin: 20px 0;
                                        font-size: 0.95rem;
                                        position: relative;
                                    }
                                    .code-header {
                                        position: absolute;
                                        top: -10px;
                                        left: 15px;
                                        background: #252525;
                                        padding: 0 10px;
                                        font-size: 0.8rem;
                                        color: #999;
                                    }
                                    h1 {
                                        font-size: 1.5rem;
                                        margin-bottom: 25px;
                                        color: #ffffff;
                                        font-weight: 500;
                                    }
                                </style>
                            </head>
                            <body>
                                <div class="container">
                                    <img src="https://app.smartloop.ai/img/logo.svg" alt="Smartloop" class="logo">                                    <h1>Authentication Successful! 🎉</h1>
                                    <div class="code-message">
                                        <div class="code-header">response</div>
                                        <span class="success">> You have successfully authenticated with Smartloop CLI.</span><br>
                                        <span style="color: #aaaaaa; font-size: 0.85rem;">> Your access token has been saved securely.</span><br>
                                        <span style="color: #aaaaaa; font-size: 0.85rem;">> You may close this window and return to your terminal.</span>
                                    </div>
                            <script>
                                // Signal successful authentication to server in the background
                                (async function() {
                                    try {
                                        // Notify the server silently
                                        await fetch('/success', { 
                                            method: 'GET',
                                            // Use a short timeout to avoid waiting too long
                                            signal: AbortSignal.timeout(500)
                                        }).catch(() => {});
                                    } catch (e) {
                                        // Silently handle any errors
                                    }
                                })();
                        </script>
                    </body>
                    </html>
                    """)
            else:
                if template_exists:
                    return render_template('callback.html', 
                                           success=False, 
                                           error_message="No token received.")
                else:
                    return render_template_string("""
                    <html>
                    <head>
                        <title>Authentication Error</title>
                        <link rel="preconnect" href="https://fonts.googleapis.com">
                        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600<title>Authentication Error</title>display=swap" rel="stylesheet">
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <style>
                            body, html {
                                font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                                background-color: #1b1b1b;
                                color: #f0f0f0;
                                line-height: 1;
                                height: 100%;
                                width: 100%;
                                margin: 0;
                                padding: 0;
                                text-align: center;
                                -webkit-font-smoothing: antialiased;
                                -moz-osx-font-smoothing: grayscale;
                            }
                            .container {
                                background-color: #252525;
                                border-radius: 8px;
                                padding: 30px;
                                box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                                margin: 60px auto;
                                max-width: 500px;
                            }
                            h1 {
                                font-size: 1.8rem;
                                margin-bottom: 20px;
                                color: #ffffff;
                            }
                            p {
                                margin: 12px 0;
                                font-size: 1rem;
                                line-height: 1.5;
                            }
                            .error {
                                color: #ff3b30;
                            }
                            code {
                                background-color: #333;
                                padding: 3px 6px;
                                border-radius: 4px;
                                font-family: monospace;
                                font-size: 0.9rem;
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <h1>Authentication Error</h1>
                            <p class="error">❌ No token received.</p>
                            <p>Please try again by running <code>smartloop login</code> in your terminal.</p>
                        </div>
                    </body>
                    </html>
                    """)
    
    def _exchange_code_for_token(self, code):
        """Exchange the authorization code for an access token."""
        token_endpoint = "http://localhost:3000/login/token"
        
        # Real implementation of token exchange with localhost:3000
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
        if FLASK_AVAILABLE and self.app is not None:
            # Start Flask server if available
            self.flask_thread = threading.Thread(target=lambda: self.app.run(
                host='localhost', 
                port=self.port, 
                debug=False,
                use_reloader=False
            ))
            self.flask_thread.daemon = True
            self.flask_thread.start()
        else:
            # Use a simple HTTP server if Flask is not available
            from http.server import HTTPServer, SimpleHTTPRequestHandler
            
            # Create a simple request handler that captures the code
            class CallbackHandler(SimpleHTTPRequestHandler):
                browser_login = self  # Reference to the outer class
                
                def do_GET(self):
                    """Handle GET request to capture OAuth callback."""
                    if self.path.startswith('/callback'):
                        # Parse query parameters
                        from urllib.parse import urlparse, parse_qs
                        query = parse_qs(urlparse(self.path).query)
                        
                        token = query.get('token', [''])[0]
                        code = query.get('code', [''])[0]
                        state = query.get('state', [''])[0]
                        
                        if state == self.browser_login.state:
                            if token:
                                # We got a valid token, store it directly
                                self.browser_login.token = token
                                self.browser_login.auth_success = True
                                # Silently store the token without printing status
                            elif code:
                                # We got a code, exchange it for a token silently
                                self.browser_login.token = self.browser_login._exchange_code_for_token(code)
                                self.browser_login.auth_success = True
                            
                            # Send success response
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            success_html = """
                            <html>
                            <head>
                                <title>Smartloop Authentication Success</title>
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <style>
                                    body, html {
                                        font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                                        background-color: #1b1b1b;
                                        color: #f0f0f0;
                                        line-height: 1;
                                        height: 100%;
                                        width: 100%;
                                        margin: 0;
                                        padding: 0;
                                        text-align: center;
                                        -webkit-font-smoothing: antialiased;
                                        -moz-osx-font-smoothing: grayscale;
                                    }
                                    .container {
                                        background-color: #252525;
                                        border-radius: 8px;
                                        padding: 30px;
                                        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                                        margin: 60px auto;
                                        max-width: 500px;
                                    }
                                    h1 {
                                        font-size: 1.8rem;
                                        margin-bottom: 20px;
                                        color: #ffffff;
                                    }
                                    p {
                                        margin: 12px 0;
                                        font-size: 1rem;
                                        line-height: 1.5;
                                    }
                                    .success {
                                        color: #4cd964;
                                    }
                                </style>
                            </head>
                            <body>
                                <div class="container">
                                    <img src="https://app.smartloop.ai/img/logo.svg" alt="Smartloop" class="logo">
                                    <h1>Authentication Successful! 🎉</h1>
                                    <div class="code-message">
                                        <div class="code-header">response</div>
                                        <span class="success">> You have successfully authenticated with Smartloop CLI.</span><br>
                                        <span style="color: #aaaaaa; font-size: 0.85rem;">> Your access token has been saved securely.</span><br>
                                        <span style="color: #aaaaaa; font-size: 0.85rem;">> You may close this window and return to your terminal.</span>
                                    </div>
                                    <p>Your access token has been saved securely.</p>
                                    <p>You may close this window and return to your terminal.</p>
                                </div>
                            </body>
                            </html>
                            """
                            self.wfile.write(success_html.encode())
                        else:
                            # Send error response
                            self.send_response(400)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            error_html = """
                            <html>
                            <head>
                                <title>Authentication Error</title>
                        <link rel="preconnect" href="https://fonts.googleapis.com">
                        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
                        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600<title>Authentication Error</title>display=swap" rel="stylesheet">
                                <meta charset="UTF-8">
                                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                                <style>
                                    body, html {
                                        font-family: 'Poppins', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
                                        background-color: #1b1b1b;
                                        color: #f0f0f0;
                                        line-height: 1;
                                        height: 100%;
                                        width: 100%;
                                        margin: 0;
                                        padding: 0;
                                        text-align: center;
                                        -webkit-font-smoothing: antialiased;
                                        -moz-osx-font-smoothing: grayscale;
                                    }
                                    .container {
                                        background-color: #252525;
                                        border-radius: 8px;
                                        padding: 30px;
                                        box-shadow: 0 8px 24px rgba(0,0,0,0.2);
                                        margin: 60px auto;
                                        max-width: 500px;
                                    }
                                    h1 {
                                        font-size: 1.8rem;
                                        margin-bottom: 20px;
                                        color: #ffffff;
                                    }
                                    p {
                                        margin: 12px 0;
                                        font-size: 1rem;
                                        line-height: 1.5;
                                    }
                                    .error {
                                        color: #ff3b30;
                                    }
                                    code {
                                        background-color: #333;
                                        padding: 3px 6px;
                                        border-radius: 4px;
                                        font-family: monospace;
                                        font-size: 0.9rem;
                                    }
                                    .logo {
                                        width: 180px;
                                        height: auto;
                                        margin-bottom: 24px;
                                        filter: brightness(0) invert(1);
                                    }
                                </style>
                            </head>
                            <body>
                                <div class="container">
                                    <img src="https://app.smartloop.ai/img/logo.svg" alt="Smartloop" class="logo">
                                    <h1>Authentication Error</h1>
                                    <div class="code-message">
                                        <div class="code-header">error</div>
                                        <span class="error">> Invalid state parameter or missing code.</span><br>
                                        <span style="color: #aaaaaa; font-size: 0.85rem;">> Please try again by running <code>smartloop login</code> in your terminal.</span>
                                    </div>
                                </div>
                            </body>
                            </html>
                            """
                            self.wfile.write(error_html.encode())
                    else:
                        super().do_GET()
                
                def log_message(self, format, *args):
                    """Silence log messages."""
                    return
            
            # Start the HTTP server in a separate thread
            self.server = HTTPServer(('localhost', self.port), CallbackHandler)
            self.server_thread = threading.Thread(target=self.server.serve_forever)
            self.server_thread.daemon = True
            self.server_thread.start()
    
    def stop_server(self):
        """Stop the running server cleanly."""
        if FLASK_AVAILABLE and self.app is not None:
            # For Flask, we need to request shutdown via success endpoint
            try:
                import requests
                requests.get(f'http://localhost:{self.port}/success', timeout=0.1)
                # Give Flask a moment to process the shutdown request
                time.sleep(0.2)
            except Exception:
                pass  # Ignore connection errors when shutting down
                
            # If the server is still running, force quit it by closing the socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                sock.connect(('localhost', self.port))
                sock.close()
            except Exception:
                pass  # Port is likely already closed, which is good
        elif self.server is not None:
            # For HTTP server, shut it down in a separate thread to avoid blocking
            shutdown_thread = threading.Thread(target=self._shutdown_http_server)
            shutdown_thread.daemon = True
            shutdown_thread.start()
            shutdown_thread.join(timeout=1.0)  # Wait up to 1 second for clean shutdown
    
    def _shutdown_http_server(self):
        """Helper method to shutdown HTTP server without blocking."""
        try:
            if hasattr(self.server, 'shutdown'):
                self.server.shutdown()
            self.server.server_close()
        except Exception:
            pass  # Ignore errors during server shutdown
            
    def open_login_page(self):
        """Open the browser for the user to authenticate."""
        # Construct the authorization URL pointing to localhost:3000/login
        auth_url = "http://localhost:3000/login"
        client_id = os.getenv('SLP_CLIENT_ID', 'smartloop-cli')
        full_auth_url = f"{auth_url}?response_type=code&redirect_uri={self.redirect_uri}&state={self.state}&client_id={client_id}"
        
        # Open the authorization URL in the user's default browser
        webbrowser.open(full_auth_url)
    
    def wait_for_auth(self, timeout=120):
        """Wait for the authentication to complete with a timeout.
        
        Args:
            timeout: Maximum time to wait for auth in seconds
            
        Returns:
            Tuple of (success, token)
        """
        start_time = time.time()
        while not self.auth_success and time.time() - start_time < timeout:
            time.sleep(1)
        
        if not self.auth_success:
            print("Authentication timed out. Please try again.")
            
        return self.auth_success, self.token

def perform_browser_login(callback_port=5000):
    """Main function to perform browser-based login.
    
    Args:
        callback_port: The port to use for the local callback server
    """
    login_handler = BrowserLogin(port=callback_port)
    login_handler.start_server()
    login_handler.open_login_page()
    
    client_id = os.getenv('SLP_CLIENT_ID', 'smartloop-cli')
    print("A browser window has been opened for you to complete the login process.")
    print("If it doesn't open automatically, please go to the following URL:")
    print(f"http://localhost:3000/login?response_type=code&redirect_uri=http://localhost:{login_handler.port}/callback&state={login_handler.state}&client_id={client_id}")
    print("Complete the login, and the token will be automatically sent back to the callback URL.")
    
    try:
        auth_success, token = login_handler.wait_for_auth()
        
        if auth_success and token:
            # Validate the token before saving
            if validate_token(token):
                # Save the token to the user profile
                user_profile = UserProfile.load(generate=True)
                user_profile[urlparse(endpoint).hostname] = dict(token=token)
                UserProfile.save(user_profile)
                print("\n[✓] Token successfully saved in user profile")
                print("[✓] Login successful!")
                return True
            else:
                print("Invalid token received. Authentication failed.")
                return False
        else:
            print("Authentication failed or timed out.")
            return False
    finally:
        # Always stop the server silently, even if an exception occurs
        login_handler.stop_server()
        time.sleep(0.5)  # Give the server a moment to shut down cleanly
        
def validate_token(token):
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
        return resp.status_code == 200
    except Exception as e:
        print(f"Error validating token: {e}")
        return False
