import sys
from typing import Annotated
import requests
import json
import os
import typer
import uuid
import getpass
import time
import posixpath

from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.console import Console
from signal import signal, SIGINT
from art import text2art
from urllib.parse import urlparse

from smartloop.constants import endpoint, homedir

from smartloop.cmd.projects import Projects
from smartloop.utils import UserProfile
from smartloop import services

from smartloop import __version__

console = Console()
app = typer.Typer()

app.add_typer(Projects.app, name='projects' , short_help= "Manage projects(s)")

def select_project() -> dict:
	profile = UserProfile.current_profile()
	projects = services.Projects(profile).get_all()
	# must have a project created earlier
	if len(projects) > 0:
		return services.Projects.select()

	raise "No project has been created"

@app.command(short_help="Authenticate using a token from https://api.smartloop.ai/v1/redoc")
def login():
	Art = text2art('smartloop.')

	console.print(Art)
	console.print('Please copy your access token using the link https://dashboard.smartloop.ai/developer')
	console.print('You will need to complete your authentication process to obtain / generate access token')

	token  = getpass.getpass('Paste your token (Token will be invisible): ')

	user_profile = UserProfile.load(generate=True)
	user_profile[urlparse(endpoint).hostname] = dict(token=token)

	UserProfile.save(user_profile)

	try:
		current_profile = UserProfile.current_profile()
		services.Projects(current_profile).get_all()
		console.print('[green]Successfully logged in[/green]')
		console.print('Next up, create and [cyan]project[/cyan] then use the [cyan]run[/cyan] command to start prompting')
	except:
		console.print('[red]Invalid login[/red]')

def chat_with_agent(project_id: str):
	user_input = input('Enter prompt (Ctrl-C to exit):\n')
	url = posixpath.join(endpoint, 'projects', project_id, 'messages')

	profile =  UserProfile.current_profile()
	token = profile.get('token')

	uid = str(uuid.uuid4())

	resp = requests.post(url,
					  json=dict(
           				uid=uid,
						text=user_input,
						type='text'
					),headers={
						'x-api-key': token
					})
	resp.raise_for_status()
	result = resp.json()

	# Lookup the UID from the IN message so we can poll for the OUT message response
	uid = result.get('uid')

	timeout = 5 * 60 + time.time()

	with Progress(SpinnerColumn()) as progress:
		progress.add_task("thinking...")
		progress.start()
		# observe for responses
		while True:
			try:
				url = posixpath.join(endpoint, 'projects', project_id, 'messages', uid, 'out')

				resp = requests.get(url, headers={'x-api-key': token})
				resp.raise_for_status()
				result = resp.json()

				found = False

				for i in range(len(result)):
					msg = result[i]

					direction = msg['direction']
					_uid = msg['uid']

					if direction == 'out' and _uid == uid:
						progress.stop()

						for char in msg['text']:
							print(char, end='')
							sys.stdout.flush()
							time.sleep(.01)

						typer.echo('\n')
						found = True

				if found or time.time() > timeout:
					break

				time.sleep(1)
			except Exception as ex:
				typer.echo(ex)

def _current_project() -> dict:
	try:
		profile = UserProfile.current_profile()
		# if logged in
		if 'token' in profile.keys():
			project =  profile['project']
			return project
	except Exception as ex:
		console.print(ex)

	return dict()

@app.command(short_help="Starts a chat session with a selected project")
def run():
	try:
		profile = UserProfile.current_profile()
		# check if logged in
		if 'token' in profile.keys():
			if 'project' in profile.keys():
				project =  profile['project']

				display_name = f"{project.get('title')}({project['name']})"
				dashes = "".join([ '-' for i in range(len(display_name))])

				console.print(f"[cyan]{display_name}[/cyan]")
				console.print(dashes)

				# chat till the cancelled
				while True:
					chat_with_agent(project['id'])
					time.sleep(1)
			else:
				select_project()
				run()
		else:
			login()
	except Exception as ex:
		console.print(ex)

@app.command(short_help="Upload document for the selected project")
def upload(path: Annotated[str, typer.Option(help="folder or file path")]):
	project = _current_project()
	# check for project id
	if 'id' in project:
		Projects.upload(project.get('id'), path)

@app.command(short_help="Find out which account you are logged in")
def whoami():

	try:
		profile = UserProfile.current_profile()
		token = profile.get('token')

		url = posixpath.join(endpoint, 'users', 'me')

		resp = requests.get(url, headers={
			'x-api-key': token
		})
		resp.raise_for_status()
		resp = resp.json()
		console.print(f"{resp.get('name')}")
	except Exception as ex:
		console.print(f"[red]{ex}[/red]")

@app.command(short_help="Version of the cli")
def version():
	console.print(f"Version: {__version__}")

def bootstrap():
	if not os.path.isdir(homedir):
		os.makedirs(homedir)

	app()
