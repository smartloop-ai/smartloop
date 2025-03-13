from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text()

from smartloop import __version__

install_requires = [
    'PyYAML==6.0.1',
    'requests==2.32.3',
    'typer==0.12.3',
    'art==6.2',
    'inquirer==3.3.0',
    'tabulate==0.9.0'
]

setup(
    name='smartloop',
    description='Smartloop Command Line interface to process documents using LLM',
    version=__version__,
    author_email='mehfuz@smartloop.ai',
    author='Smartloop Inc.',
    url='https://github.com/LexicHQ/smartloop',
    keywords=['LLM', 'framework', 'llama3', 'phi3', 'platform', 'document', 'gemma'],
    packages=find_packages(exclude=['tests*']),
    py_modules=['main', 'constants'],
    license='LICENSE.txt',
    install_requires=install_requires,
    long_description=long_description,
    long_description_content_type='text/markdown',
    classifiers=[
        'Development Status :: 4 - Beta',
        # Chose either "3 - Alpha", "4 - Beta" or "5 - Production/Stable" as the current state of your package
        'Intended Audience :: Developers',  # Define that your audience are developers
        "Topic :: Software Development :: Libraries",
        'License :: OSI Approved :: MIT License',  # Again, pick a license
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11'
    ],
    entry_points='''
        [console_scripts]
        smartloop=main:bootstrap
    '''
)