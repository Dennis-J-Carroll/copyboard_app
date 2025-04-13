from setuptools import setup, find_packages
import os
from pathlib import Path

# Find all data files for installation
data_files = [
    ('share/copyboard_extension', ['config/nautilus-copyboard.py',
                                   'config/copyboard-kde-service.desktop',
                                   'scripts/install-nautilus-extension.sh',
                                   'scripts/install-kde-service.sh']),
    ('share/doc/copyboard_extension', ['README.md', 'docs/CONTEXT_MENU_INTEGRATION.md'])
]

setup(
    name="copyboard-extension",
    version="0.1.0",
    description="A multi-clipboard utility for copying and pasting multiple items",
    author="Copyboard Developer",
    author_email="example@example.com",
    packages=[
        'copyboard_extension',
        'copyboard_extension.browser_extension',
    ],
    package_dir={
        'copyboard_extension': 'copyboard_extension',
    },
    package_data={
        'copyboard_extension.browser_extension': ['icons/*.png', 'manifest.json'],
    },
    install_requires=[
        "pyperclip>=1.8.0",
        "pillow>=8.0.0",  # For icon generation
    ],
    scripts=[
        "bin/copyboard",
        "bin/copyboard-gui",
        "bin/copyboard-install-integration",
    ],
    entry_points={
        "console_scripts": [
            "copyboard=copyboard_extension.cli:main",
            "copyboard-install-integration=copyboard_extension.system_integration:install_context_menu_integration",
        ],
        "gui_scripts": [
            "copyboard-gui=copyboard_extension.gui:run_gui",
        ],
    },
    data_files=data_files,
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Topic :: Utilities",
    ],
    include_package_data=True,
)
