import os

endpoint= os.getenv('SLP_BASE_URL', 'https://api.smartloop.ai/v1')
auth_server = os.getenv('SLP_AUTH_SERVER', 'https://app.smartloop.ai')
homedir = os.getenv('SLP_HOME', os.path.expanduser('~/.slp'))
