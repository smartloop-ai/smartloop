import posixpath
import requests
import os

from smartloop.constants import endpoint

class Projects:
    def __init__(self, profile: dict):
        self.profile = profile

    def get_all(self):
        url = os.path.join(endpoint, 'users', 'me')

        resp = requests.get(url, headers={'x-api-key': self.profile.get('token')})
        resp.raise_for_status()
        result = resp.json()

        projects = result['projects']

        return projects

    def set_config(self, config:dict):
        project_id = self.profile.get('project')['id']

        url = posixpath.join(endpoint, 'projects', project_id, 'config')
        resp = requests.post(url, headers={'x-api-key': self.profile.get('token')}, json=config)
        resp.raise_for_status()

    def delete(self):
        project_id = self.profile.get('project')['id']

        url = posixpath.join(endpoint, 'projects', project_id)
        resp = requests.delete(url, headers={'x-api-key': self.profile.get('token')})
        resp.raise_for_status()
