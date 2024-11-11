import typer
import requests
import posixpath
import mimetypes
import os
import re
import http
import time

from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

from tabulate import tabulate

import inquirer
from inquirer.themes import GreenPassion

from smartloop.services import Projects
from smartloop.constants import endpoint
from smartloop.utils import UserProfile

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn

console = Console()

class Project:
    app = typer.Typer()

    @app.command(short_help="Select a project")
    def select() -> dict:
        profile = UserProfile.current_profile()
        projects = Projects(profile).get_all()
        
        _projects = [f"{proj['title']}({proj['name']})" for proj in projects]
        
        try:
            projects_list = [
                inquirer.List(
                    "project",
                    message="Select a project from the options below",
                    choices=_projects,
                ),
            ]

            answer = inquirer.prompt(projects_list, theme=GreenPassion())
            current_selection =  answer.get('project') if answer is not None else None

            if current_selection is not None:
                name = re.findall('\(([^)]+)\)', current_selection)[0]

                selected = [project for project in projects if project.get('name') == name][0]
                
                profile['project'] = selected
               
                user_profile = UserProfile.load()
                user_profile[urlparse(endpoint).hostname] = profile
                
                UserProfile.save(user_profile)

                console.print(f"Default project set to: [underline]{selected['name']}[/underline]")
                
                return selected
        except Exception as ex:
            console.print(ex)

     
    @app.command(short_help="List all projects")
    def list():
        profile = UserProfile.current_profile()
        project = profile.get('project', None)
        
        print_project = lambda x :tabulate(x, headers=['current', 'id', 'title'])
        
        projects = Projects(profile).get_all()

        console.print(print_project([
            ['[*]' if project is not None and proj['id'] == project['id']else '[ ]', 
             proj['id'],
             proj['title']
            ]
            for proj in projects
        ]))


    @app.command(short_help="Create a new project")
    def create(name: Annotated[str, typer.Option(help="The name of the project")]):
        url = posixpath.join(endpoint, 'projects')
        profile = UserProfile.current_profile()
        try:
            resp = requests.put(url, headers={'x-api-key': profile['token']}, json=dict(title=name))
            resp.raise_for_status()

            print("Project created successfully")
        except Exception as ex:
            print(ex)


    @app.command(short_help="get project")
    def get(id: Annotated[str, typer.Option(help="id of the project")]):
       
        try:
            profile = UserProfile.current_profile()
            projects = [
                project for project in Projects(profile).get_all() 
                if project.get('id') == id
            ]

            if len(projects) > 0:
                project_properties = []
                expected_keys = ['id', 'title', 'name', 'config', 'created_at']
                for key, value in projects[0].items():
                    if key in expected_keys:
                        if key == 'config':
                            for key, value in value.items():
                                project_properties.append([key, value])
                        else:    
                            project_properties.append([key, value])

                console.print(tabulate(project_properties, headers=['Name', 'Value']))
            else:
                console.print("[red]No project found[/red]")
        except Exception as ex:
            print(ex)

    @app.command(short_help="Set project properties")
    def set(id: Annotated[str, typer.Option(help="project Id to use")], temp: Annotated[float, typer.Option(help="Set a temperature between 0.0 and 1.0")] = 0.3):
        profile = UserProfile.current_profile()
        projects = [
            project for project in Projects(profile).get_all() 
            if project.get('id') == id
        ]
        # check for length
        if len(projects) > 0:
            profile['project'] = projects[0]
            Projects(profile).set_config(dict(temperature=temp))
        else:
            console.print("No project found")

    @app.command(short_help="Delete a project")
    def delete(id: Annotated[str, typer.Option(help="project Id to use")]):
        profile = UserProfile.current_profile()
        projects = [
            project for project in Projects(profile).get_all() 
            if project.get('id') == id
        ]
        # check for length
        if len(projects) > 0:
            profile['project'] = projects[0]
            Projects(profile).delete()
            console.print("Project deleted successfully")
        else:
            console.print("No project found")

    @app.command(short_help="Upload documents for a slected project")
    def upload(id: Annotated[str, typer.Option(help="project Id to use")], 
               path: Annotated[str, typer.Option(help="folder or file path")]):
        profile = UserProfile.current_profile()
        projects = [
            project for project in Projects(profile).get_all() 
            if project.get('id') == id
        ]

        if len(projects) == 0:
            raise 'No project found'
        
        project = projects[0]

        path = os.path.expanduser(path)
        
        console.print(f"[green]Upload to project: [underline]{project.get('title')}({project.get('name')})[/green][/underline]")

        url = posixpath.join(endpoint, f"{project['id']}/documents")

        files = []

        if os.path.isdir(path):
            files = glob.glob(os.path.join(path, '*.pdf'))
            # extend file types
            files.extend(glob.glob(os.path.join(path, '*.docx')))
            files.extend(glob.glob(os.path.join(path, '*.txt')))
        else:
            files.append(path)

        for file in files:
            console.print(f"Uploading {file}")
            with Progress(SpinnerColumn()) as progress:
                task = progress.add_task("uploading...")
                progress.start()
                try:
                    with open(file, 'rb') as infile:
                        mimetype = mimetypes.guess_type(file)
                        resp = requests.put(url, headers={
                            'x-api-key': profile['token']
                        }, 
                        files={
                            'file': (Path(infile.name).name, infile.read(), mimetype[0])
                        })
                        
                        # handled error
                        if resp.status_code not in [http.HTTPStatus.CREATED, http.HTTPStatus.OK]:
                            progress.stop()
                            console.print(f"[red]{resp.json()['detail']}[/red]")
                            return

                        resp.raise_for_status()

                        data = resp.json()
                        progress.console.print("Uploaded.")
                        progress.console.print("Processing document...")
                        while True:
                            if 'id' in data:
                                # wait for document to be processed
                                url = posixpath.join(endpoint, project.get('id'), 'documents', data['id'])
                                resp =requests.get(url, headers={
                                    'x-api-key': profile['token']
                                })
                                resp.raise_for_status()
                                _data = resp.json()
                                document = _data.get('data', None)
                                # check if not pending 
                                if document is None or not document.get('pending', False):
                                    break
                            else:
                                break
                            time.sleep(1)
                        progress.stop()
                        console.print("Completed.")
                except Exception as ex:
                    console.print(f"[red]{ex}[/red]")

