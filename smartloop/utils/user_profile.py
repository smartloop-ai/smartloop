import os
import yaml
from urllib.parse import urlparse

from smartloop.constants import homedir
from smartloop.constants import endpoint

class UserProfile:
    @staticmethod
    def load(generate=False) -> dict:
        if not generate:
            path = os.path.join(homedir, 'user.yaml')
            try:
                if os.path.exists(path):
                    with open(path, 'r') as infile:
                        _yaml = yaml.safe_load(infile)
                        return _yaml
            except Exception as ex:
                print(ex)
        return dict()
    
    @staticmethod
    def current_profile() -> dict:
        return UserProfile.load().get(urlparse(endpoint).hostname, dict())
    
    @staticmethod
    def save(profile:dict):
        with open(os.path.join(homedir, 'user.yaml'), 'w+') as outfile:
            yaml.dump(dict(profile), outfile, default_flow_style=False)