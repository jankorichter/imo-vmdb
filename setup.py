from setuptools import setup, find_packages
from sphinx.setup_command import BuildDoc
from imo_vmdb import __version__


cmdclass = {
    'build_sphinx': BuildDoc
}

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setup(
    name='imo-vmdb',
    version=__version__,
    author='Janko Richter',
    author_email='janko@richtej.de',
    description='Imports VMDB CSV files from IMO into a SQL database.',
    keywords=['IMO', 'VMDB', 'SQL'],
    license='MIT',
    license_files=['LICENSE.txt'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/jankorichter/imo-vmdb',
    project_urls={
        'Bug Tracker': 'https://github.com/jankorichter/imo-vmdb/issues',
        'Source': 'https://github.com/jankorichter/imo-vmdb',
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    packages=find_packages(where='./'),
    python_requires='>=3.7',
    install_requires=[
        'astropy',
        'numpy'
    ],
    include_package_data=True,
    package_data={
        'imo_vmdb': [
            'data/*.csv'
        ],
    },
    cmdclass=cmdclass,
    command_options={
        'build_sphinx': {
            'source_dir': ('setup.py', 'docs')
        }
    },
)
