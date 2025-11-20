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
import tempfile
import subprocess

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys

from rich.progress import Progress, SpinnerColumn, TimeElapsedColumn
from rich.console import Console
from signal import signal, SIGINT
import pyfiglet
from urllib.parse import urlparse

from smartloop.constants import endpoint, homedir, auth_server
from smartloop.cmd.projects import Projects
from smartloop.utils import UserProfile
from smartloop import services

from smartloop import __version__

console = Console()

def version_callback(value: bool):
	"""Callback for --version flag"""
	if value:
		console.print(f"Version: {__version__}")
		raise typer.Exit()

app = typer.Typer()

# Add global --version flag
@app.callback()
def main(
	version: Annotated[bool, typer.Option("--version", callback=version_callback, help="Show version and exit")] = False,
):
	"""
	SmartLoop CLI - Upload, manage, and query documents with fine-tuned LLM models.
	"""
	pass

app.add_typer(Projects.app, name='projects' , short_help= "Manage projects(s)")

def load_file_content(filepath: str) -> str:
	"""Load content from a file if it exists."""
	try:
		if os.path.isfile(filepath):
			with open(filepath, 'r') as f:
				return f.read()
	except Exception as e:
		console.print(f"[red]Error reading file: {e}[/red]")
	return ""

def get_editable_input() -> str:
	"""
	Get user input with multiline support using prompt_toolkit.
	Press Alt+Enter to send, Enter for new line.
	Supports loading files and opening external editor.
	"""
	# Instructions for the user
	console.print("\n[cyan]Enter your prompt:[/cyan]")
	instructions = (
		"[dim]  - Press Enter to add a new line\n"
		"  - Press Alt+Enter (or Esc then Enter) to send the prompt\n"
		"  - Type ':load <filepath>' and Alt+Enter to load a file\n"
		"  - Type ':edit' and Alt+Enter to open in external editor\n"
		"  - Press Ctrl+C or Ctrl+D to cancel[/dim]\n"
	)
	console.print(instructions)

	# Create custom key bindings
	kb = KeyBindings()

	@kb.add('escape', 'enter')
	def _(event):
		"""Accept input on Alt+Enter (escape sequence)"""
		event.current_buffer.validate_and_handle()

	@kb.add(Keys.Enter)
	def _(event):
		"""Insert newline on plain Enter"""
		event.current_buffer.insert_text('\n')

	@kb.add('c-c')
	def _(event):
		"""Exit on Ctrl+C"""
		event.app.exit(exception=KeyboardInterrupt)

	@kb.add('c-d')
	def _(event):
		"""Exit on Ctrl+D"""
		event.app.exit(exception=EOFError)

	try:
		# Get multiline input with custom key bindings
		user_input = prompt(
			'> ',
			multiline=True,
			key_bindings=kb,
			prompt_continuation=lambda width, line_number, is_soft_wrap: '  '
		).strip()

		if not user_input:
			console.print("[yellow]Prompt cancelled or empty. Skipping.[/yellow]")
			return ""

		# Check for special commands
		if user_input.startswith(':load'):
			# Load file content
			parts = user_input.split(maxsplit=1)
			if len(parts) > 1:
				filepath = parts[1].strip()
				content = load_file_content(filepath)
				if content:
					console.print(f"[green]Loaded content from {filepath}[/green]")
					return content
				else:
					console.print(f"[red]Failed to load file: {filepath}[/red]")
					return ""
			else:
				console.print("[yellow]Usage: :load <filepath>[/yellow]")
				return ""

		if user_input.strip() == ':edit':
			# Open in editor
			edited_content = open_in_editor("")
			if edited_content:
				console.print("[green]Content loaded from editor[/green]")
				return edited_content
			else:
				console.print("[yellow]No content from editor[/yellow]")
				return ""

		return user_input

	except KeyboardInterrupt:
		raise  # Re-raise to exit the entire chat session
	except EOFError:
		raise  # Re-raise to exit the entire chat session

def open_in_editor(initial_content: str = "") -> str:
	"""
	Open a temporary file in the default editor for advanced editing.
	Returns the content after the user closes the editor, or None if cancelled.
	"""
	# Create a temporary file
	fd, temp_path = tempfile.mkstemp(suffix='.txt', text=True, prefix='smartloop_prompt_')

	try:
		# Write initial content
		with os.fdopen(fd, 'w') as f:
			f.write("# Edit your prompt below\n")
			f.write("# Lines starting with # are ignored and removed\n\n")
			if initial_content:
				f.write(initial_content)

		# Determine which editor to use
		editor = os.environ.get('EDITOR', 'nano')

		# Try to use different editors in order of preference
		editor_found = False
		for editor_name in [editor, 'nano', 'vim', 'vi', 'gedit', 'code']:
			try:
				# Open the file in the editor
				if editor_name in ['gedit', 'code']:
					subprocess.run([editor_name, temp_path], check=True)
				else:
					subprocess.run([editor_name, temp_path], check=True)
				editor_found = True
				break
			except (subprocess.CalledProcessError, FileNotFoundError):
				continue

		if not editor_found:
			console.print("[red]No suitable editor found. Please install nano, vim, or set the EDITOR environment variable.[/red]")
			return None

		# Read the file content
		with open(temp_path, 'r') as f:
			content = f.read()

		# Filter out comment lines and get the actual prompt
		lines = content.split('\n')
		prompt_lines = []
		for line in lines:
			# Skip empty lines and comment lines
			if line.strip() and not line.strip().startswith('#'):
				prompt_lines.append(line)

		result = '\n'.join(prompt_lines)
		return result if result else None

	finally:
		# Clean up the temporary file
		try:
			os.unlink(temp_path)
		except OSError:
			pass

def select_project() -> dict:
	profile = UserProfile.current_profile()
	projects = services.Projects(profile).get_all()
	# must have a project created earlier
	if len(projects) > 0:
		return Projects.select()

	raise Exception("No project has been created")

def get_project_by_id(project_id: str) -> dict:
	"""Get a project by its ID and set it as the current project."""
	profile = UserProfile.current_profile()
	projects = services.Projects(profile).get_all()

	# Find the project with the given ID
	matching_projects = [project for project in projects if project.get('id') == project_id]

	if len(matching_projects) == 0:
		raise Exception(f"No project found with ID: {project_id}")

	selected_project = matching_projects[0]

	# Set this project as the current project in the profile
	profile['project'] = selected_project

	user_profile = UserProfile.load()
	user_profile[urlparse(endpoint).hostname] = profile
	UserProfile.save(user_profile)

	console.print(f"Selected project: [underline]{selected_project['title']}({selected_project['name']})[/underline]")

	return selected_project

@app.command(short_help="Authenticate using your browser or a token")
def login():
	console.print()

	print(pyfiglet.figlet_format("smartloop.", font="doom"))

	console.print(':clipboard: Please copy your access token using the link [blue]https://app.smartloop.ai/developer[/blue]. You will need to complete your authentication process to obtain / generate access token.')

	console.print()

	token = getpass.getpass('Please paste your token (Token will be invisible): ')

	user_profile = UserProfile.load(generate=True)
	user_profile[urlparse(endpoint).hostname] = dict(token=token)

	UserProfile.save(user_profile)

	try:
		current_profile = UserProfile.current_profile()
		services.Projects(current_profile).get_all()
		console.print('[green]Successfully logged in[/green]')
		console.print('Next up, create a [cyan]project[/cyan] then use the [cyan]run[/cyan] command to start prompting')
	except Exception as ex:
		console.print(f'[red]Invalid login: {str(ex)}[/red]')

def chat_with_agent(project_id: str):
	user_input = get_editable_input().strip()

	# Skip empty prompts
	if not user_input:
		return

	url = posixpath.join(endpoint, 'openai/chat/completions')

	profile = UserProfile.current_profile()
	token = profile.get('token')

	# Prepare the OpenAI-compatible request
	payload = {
		"model": "llama-3.2-1b-instruct",
		"messages": [
			{"role": "user", "content": user_input}
		],
		"stream": True,
		"assistant_type": "project_assistant",
		"project_id": project_id
	}

	headers = {
		'x-api-key': token,
		'Content-Type': 'application/json',
		'Accept': 'text/event-stream'
	}

	try:
		# Use the same progress pattern as in projects upload
		received_first_chunk = False
		with Progress(SpinnerColumn()) as progress:
			task = progress.add_task("thinking...")
			progress.start()

			# Make streaming request
			resp = requests.post(url, json=payload, headers=headers, stream=True)
			resp.raise_for_status()

			# Process the streaming response
			for line in resp.iter_lines():
				if line:
					line_text = line.decode('utf-8')

					# Handle Server-Sent Events format
					if line_text.startswith('data: '):
						data_text = line_text[6:]  # Remove 'data: ' prefix

						# Check for end of stream
						if data_text.strip() == '[END]':
							break

						try:
							chunk_data = json.loads(data_text)

							# Extract content from the chunk
							if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
								chunk_content = chunk_data['choices'][0].get('delta', {}).get('content', '')
								if chunk_content:
									if not received_first_chunk:
										progress.stop()
										received_first_chunk = True
									print(f"{chunk_content}", end='', flush=True)
						except json.JSONDecodeError as e:
							print(f"[DEBUG] JSON decode error: {e}")
							# Maybe it's just plain text
							if not received_first_chunk:
								progress.stop()
								received_first_chunk = True
							print(data_text, end='', flush=True)
					else:
						# Not SSE format, might be plain text
						if not received_first_chunk:
							progress.stop()
							received_first_chunk = True
						print(line_text, end='', flush=True)

			# Ensure spinner is stopped if no chunks were received
			if not received_first_chunk:
				progress.stop()

		print('\n')  # Add newline at the end

	except requests.exceptions.HTTPError as http_err:
		# Handle 429 credit limit errors specifically
		if http_err.response.status_code == 429:
			try:
				error_data = http_err.response.json()
				detail = error_data.get('detail', {})

				# Check if detail is a dict (as shown in the API response format)
				if isinstance(detail, dict):
					message = detail.get('detail', 'Credit limit exceeded.')
					subscription_url = detail.get('subscription_url', '')
				else:
					# Fallback if detail is just a string
					message = str(detail)
					subscription_url = ''

				# Print the credit limit message
				console.print(f'\n[yellow]{message}[/yellow]')

				# Display the subscription URL if available
				if subscription_url:
					console.print(f'[cyan]Update your subscription: [link={subscription_url}]{subscription_url}[/link][/cyan]')
			except (json.JSONDecodeError, KeyError, AttributeError):
				# Fallback if response format is unexpected
				console.print(f'[red]Credit limit exceeded. Please check your subscription.[/red]')
		else:
			# Handle other HTTP errors
			console.print(f'[red]HTTP Error: {str(http_err)}[/red]')
	except Exception as ex:
		console.print(f'[red]Error: {str(ex)}[/red]')

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
def run(project_id: Annotated[str, typer.Option("--project-id", help="Project ID to use for the chat session")] = None):
	try:
		profile = UserProfile.current_profile()
		# check if logged in
		if 'token' in profile.keys():
			project = None

			# If project_id is provided, use that project
			if project_id:
				project = get_project_by_id(project_id)
			else:
				# No project selected, prompt user to select one
				project = select_project()

			if project:
				display_name = f"{project.get('title')}({project['name']})"
				dashes = "".join(['-' for i in range(len(display_name))])

				console.print(f"[cyan]{display_name}[/cyan]")
				console.print(dashes)

				# chat till cancelled
				while True:
					try:
						chat_with_agent(project['id'])
						time.sleep(1)
					except (KeyboardInterrupt, EOFError):
						# User pressed Ctrl+C or Ctrl+D to exit
						console.print("\n[cyan]Bye! 👋[/cyan]")
						break
		else:
			login()
	except (KeyboardInterrupt, EOFError):
		# Handle exit during project selection
		console.print("\n[cyan]Bye! 👋[/cyan]")
	except Exception as ex:
		console.print(f"[red]{ex}[/red]")

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
		console.print(f"{resp.get('name')}[green] ({resp.get('email')}[/green])")
	except Exception as ex:
		console.print(f"[red]{ex}[/red]")

def bootstrap():
	if not os.path.isdir(homedir):
		os.makedirs(homedir)


	app()