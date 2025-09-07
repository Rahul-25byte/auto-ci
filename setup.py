from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="auto-ci",
    version="1.0.0",
    author="Auto-CI Team",
    author_email="team@auto-ci.com",
    description="Automated CI/CD Pipeline Generator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/souvik03-136/auto-ci.git",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "web": ["flask>=2.0.0"],
        "github": ["PyGithub>=1.55.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "isort>=5.0.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "auto-ci=auto_ci:main",
        ],
    },
    include_package_data=True,
    package_data={
        "auto_ci": ["templates/*.yml", "templates/*.yaml"],
    },
)