from setuptools import setup, find_packages

setup(
    name='wellcode-cli',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'requests',
        'python-dateutil',
        'splitio_client',
        'openai',
        # Add any other dependencies
    ],
    entry_points={
        'console_scripts': [
            'wellcode-cli=wellcode-cli.main:main',
        ],
    },
)