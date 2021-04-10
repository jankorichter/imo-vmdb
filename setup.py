import setuptools

with open('README.md', 'r', encoding='utf-8') as fh:
    long_description = fh.read()

setuptools.setup(
    name='imo-vmdb',
    version='1.0.0',
    author='Janko Richter',
    author_email='janko@richtej.de',
    description='Imports VMDB CSV files from IMO into a SQL database.',
    keywords=['IMO', 'VMDB', 'SQL'],
    license='MIT',
    license_files=['LICENSE.txt'],
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/jankorichter/imo-vmdb2sql/',
    project_urls={
        'Bug Tracker': 'https://github.com/jankorichter/imo-vmdb2sql/issues',
        'Source': 'https://github.com/jankorichter/imo-vmdb2sql/',
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    packages=setuptools.find_packages(where='./'),
    python_requires='>=3.7',
    install_requires=[
        'astropy',
        'numpy'
    ],
    include_package_data=True,
    package_data={
        'vmdb': [
            'data/*.csv'
        ],
    }
)
