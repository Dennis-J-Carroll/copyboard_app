"""Compatibility packaging shim for older setuptools installations."""

from setuptools import find_packages, setup


setup(
    name="copyboard-extension",
    version="0.2.0",
    description="A ten-chamber clipboard revolver for desktop workflows",
    packages=find_packages(include=("copyboard_extension", "copyboard_extension.*")),
    include_package_data=True,
    package_data={
        "copyboard_extension": [
            "snippets/*.json",
            "browser_extension/*.html",
            "browser_extension/*.js",
            "browser_extension/*.json",
            "browser_extension/icons/*.png",
        ]
    },
    install_requires=["pyperclip>=1.8.0"],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "copyboard=copyboard_extension.cli:main",
            "copyboard-gui=copyboard_extension.copyboard_gui:main",
            (
                "copyboard-install-integration="
                "copyboard_extension.system_integration:"
                "install_context_menu_integration"
            ),
        ]
    },
)
