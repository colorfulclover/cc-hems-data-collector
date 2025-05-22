# setup.py
from setuptools import setup, find_packages

setup(
    name="hems-client",
    version="0.1.0",
    packages=find_packages(),
    package_dir={"": "src"},
    install_requires=[
        "pyserial>=3.5",
        "pyyaml>=6.0",
    ],
    extras_require={
        "cloud": ["google-cloud-pubsub>=2.13.0"],
    },
    entry_points={
        "console_scripts": [
            "hems-client=main:main",
        ],
    },
)