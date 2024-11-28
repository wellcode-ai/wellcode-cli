from setuptools import find_packages, setup
from wellcode_cli import __version__

setup(
    name="wellcode-cli",
    version=__version__,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "PyGithub",
        "slackclient",
        "python-dotenv",
        "pandas",
        "anthropic",
        "slack_sdk",
        "splitio_client",
        "setuptools",
        "colorama",
        "rich-click>=1.6.1",
        "rich>=13.3.5",
        "plotly",
        "markdown",
    ],
    entry_points={
        "console_scripts": [
            "wellcode-cli=wellcode_cli.main:main",
        ],
    },
    author="Wellcode.ai",
    author_email="yan@wellcode.ai",
    description="Engineering Team Metrics Script",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/wellcode-ai/wellcode-cli",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
