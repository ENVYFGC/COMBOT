"""
Setup script for Combot - Universal Fighting Game Combo Bot
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read requirements
requirements = []
requirements_path = this_directory / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path, 'r', encoding='utf-8') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="combot",
    version="2.0.0",
    author="ENVYFGC", 
    author_email="contact@envyfgc.com",
    description="Universal Fighting Game Combo Bot for Discord",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ENVYFGC/combot",
    
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9", 
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Communications :: Chat",
        "Topic :: Games/Entertainment",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
    ],
    
    python_requires=">=3.8",
    install_requires=requirements,
    
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0", 
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "logging": [
            "structlog>=23.0.0",
            "colorlog>=6.7.0",
        ]
    },
    
    entry_points={
        "console_scripts": [
            "combot=combot:run",
            "combot-run=combot.bot:run",
        ],
    },
    
    include_package_data=True,
    package_data={
        "combot": ["*.md", "*.txt", "*.env.example"],
    },
    
    project_urls={
        "Bug Reports": "https://github.com/ENVYFGC/combot/issues",
        "Source": "https://github.com/ENVYFGC/combot",
        "Documentation": "https://github.com/ENVYFGC/combot/wiki",
        "Community": "https://discord.gg/fgc",
    },
    
    keywords=[
        "discord", 
        "bot", 
        "fighting-games", 
        "combos", 
        "fgc", 
        "youtube",
        "gaming",
        "community"
    ],
)
