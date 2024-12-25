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

from smartloop.cmd import Project
from smartloop.utils import UserProfile
from smartloop.services import Projects

from smartloop import __version__

console = Console()
app = typer.Typer()

app.add_typer(Project.app, name='project' , short_help= "Manage projects")

def select_project() -> dict:
	profile = UserProfile.current_profile()
	projects = Projects(profile).get_all()
	# must have a project created earlier
	if len(projects) > 0:
		return Project.select()
	
	raise "No project has been created"

@app.command(short_help="Authenticate using a token from https://api.smartloop.ai/v1/redoc")
def login():
	Art = text2art('smartloop.', font='small')
	
	console.print(Art)
	console.print('Copy your token from the https://app.smartloop.ai/developer')
	console.print('You will need to complete your authentication process to obtain / generate access token')

	token  = getpass.getpass('Paste your token (Token will be invisible): ')

	user_profile = UserProfile.load()
	user_profile[urlparse(endpoint).hostname] = dict(token=token)

	UserProfile.save(user_profile)

	try:
		current_profile = UserProfile.current_profile()
		Projects(current_profile).get_all()
		console.print('[green]Successfully logged in[/green]')
		console.print('Next up explore [cyan]project[/cyan] or use [cyan]run[/cyan] to chat with a document')
	except:
		console.print('[red]Invalid login[/red]')

def chat_to_project(project_id: str):
	user_input = input('Enter message (Ctrl-C to exit): ')
	url = posixpath.join(endpoint, project_id, 'messages')

	profile =  UserProfile.current_profile()
	token = profile.get('token')

	uid = str(uuid.uuid4())
	
	resp = requests.post(url, 
					  json=dict(uid=uid,
						text=user_input,
						type='text'
					),headers={
						'x-api-key': token
					})
	resp.raise_for_status()

	result = resp.json()
	data = result.get('data', {})
	uid = data.get('uid')
	
	timeout = 5*60 + time.time()

	with Progress(SpinnerColumn()) as progress:
		progress.add_task("thinking...")
		progress.start()
		# observe for responses
		while True:
			try:
				url = posixpath.join(endpoint, project_id, 'messages', 'recent')
				
				resp = requests.get(url,headers={'x-api-key': token})
				resp.raise_for_status()
				result = resp.json()

				data = result.get('data', [])

				found = False

				for i in range(len(data)):
					msg = data[i]
					direction = msg['direction']
					payload = msg['payload']
					_uid = payload['uid']
				
					if direction == 'out' and _uid == uid:
						progress.stop()
						for char in payload['text']:
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


@app.command(short_help="Starts a chat session with a selected project")
def run():
	try:
		profile = UserProfile.current_profile()
		# check if logged in
		if 'token' in profile.keys():
			if 'project' in profile.keys():
				project =  profile['project']

				console.print(f"[green]Current project: [underline]{project.get('title')}({project['name']})[/green][/underline]")
				# chat till the cancelled
				while True:
					chat_to_project(project['id'])
					time.sleep(1)
			else:
				select_project()
				run()
		else:
			login()
	except Exception as ex:
		console.print(ex)

@app.command(short_help="Find out which account you are logged in")
def whoami():
	try:
		profile = UserProfile.current_profile()
		token = profile.get('token')

		url = posixpath.join(endpoint, 'users')
		
		resp = requests.get(url, headers={
			'x-api-key': token
		})
		resp.raise_for_status()
		resp = resp.json()
		# check for data
		if 'data' in resp:
			data = resp['data']
			console.print(f"{data.get('name')}")
	except Exception as ex:
		console.print(f"[red]{ex}[/red]")

@app.command(short_help="Version of the cli")
def version():
	console.print(f"Version: {__version__}")

def bootstrap():
	if not os.path.isdir(homedir):
		os.makedirs(homedir)
	
	app()
