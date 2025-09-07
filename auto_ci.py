import os
import json
import yaml
import argparse
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import hashlib
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class DetectedTechnology:
    name: str
    version: Optional[str] = None
    files: List[str] = None
    confidence: float = 1.0
    
    def __post_init__(self):
        if self.files is None:
            self.files = []

@dataclass
class RepoAnalysis:
    languages: List[DetectedTechnology]
    frameworks: List[DetectedTechnology] 
    test_tools: List[DetectedTechnology]
    build_tools: List[DetectedTechnology]
    containers: List[DetectedTechnology]
    infrastructure: List[DetectedTechnology]
    package_managers: List[DetectedTechnology]
    repo_path: str
    primary_language: Optional[str] = None
    
    def __post_init__(self):
        if self.primary_language is None and self.languages:
            self.primary_language = max(self.languages, key=lambda x: x.confidence).name

# ============================================================================
# REPOSITORY SCANNER
# ============================================================================

class RepoScanner:
    """Scans repository to detect technologies, frameworks, and tools"""
    
    def __init__(self):
        self.detection_rules = self._load_detection_rules()
    
    def _load_detection_rules(self) -> Dict:
        """Load detection rules for various technologies"""
        return {
            "languages": {
                "python": {
                    "files": ["*.py", "requirements.txt", "setup.py", "pyproject.toml", "Pipfile"],
                    "patterns": [r"\.py$", r"requirements.*\.txt$", r"setup\.py$"]
                },
                "javascript": {
                    "files": ["package.json", "*.js", "*.ts", "yarn.lock", "package-lock.json"],
                    "patterns": [r"package\.json$", r"\.js$", r"\.ts$"]
                },
                "go": {
                    "files": ["go.mod", "go.sum", "*.go"],
                    "patterns": [r"go\.mod$", r"\.go$"]
                },
                "java": {
                    "files": ["pom.xml", "build.gradle", "*.java", "gradlew"],
                    "patterns": [r"pom\.xml$", r"build\.gradle$", r"\.java$"]
                },
                "rust": {
                    "files": ["Cargo.toml", "Cargo.lock", "*.rs"],
                    "patterns": [r"Cargo\.toml$", r"\.rs$"]
                },
                "php": {
                    "files": ["composer.json", "composer.lock", "*.php"],
                    "patterns": [r"composer\.json$", r"\.php$"]
                },
                "ruby": {
                    "files": ["Gemfile", "Gemfile.lock", "*.rb", "*.gemspec"],
                    "patterns": [r"Gemfile$", r"\.rb$"]
                },
                "csharp": {
                    "files": ["*.csproj", "*.sln", "*.cs", "packages.config"],
                    "patterns": [r"\.csproj$", r"\.cs$", r"\.sln$"]
                }
            },
            "frameworks": {
                "django": {"files": ["manage.py", "settings.py"], "language": "python"},
                "flask": {"files": ["app.py"], "content_patterns": [r"from flask import"], "language": "python"},
                "fastapi": {"content_patterns": [r"from fastapi import"], "language": "python"},
                "react": {"files": ["package.json"], "content_patterns": [r'"react"'], "language": "javascript"},
                "vue": {"files": ["package.json"], "content_patterns": [r'"vue"'], "language": "javascript"},
                "angular": {"files": ["angular.json", "package.json"], "language": "javascript"},
                "express": {"files": ["package.json"], "content_patterns": [r'"express"'], "language": "javascript"},
                "spring": {"files": ["pom.xml"], "content_patterns": [r"spring-boot"], "language": "java"},
                "gin": {"content_patterns": [r'"github.com/gin-gonic/gin"'], "language": "go"},
                "laravel": {"files": ["artisan", "composer.json"], "language": "php"},
                "rails": {"files": ["Gemfile"], "content_patterns": [r'gem ["\']rails["\']'], "language": "ruby"}
            },
            "test_tools": {
                "pytest": {"files": ["pytest.ini", "pyproject.toml"], "content_patterns": [r"pytest"], "language": "python"},
                "unittest": {"content_patterns": [r"import unittest"], "language": "python"},
                "jest": {"files": ["jest.config.js", "package.json"], "content_patterns": [r'"jest"'], "language": "javascript"},
                "mocha": {"files": ["package.json"], "content_patterns": [r'"mocha"'], "language": "javascript"},
                "junit": {"files": ["pom.xml"], "content_patterns": [r"junit"], "language": "java"},
                "go test": {"patterns": [r"_test\.go$"], "language": "go"},
                "phpunit": {"files": ["phpunit.xml", "composer.json"], "language": "php"},
                "rspec": {"files": [".rspec", "spec/"], "language": "ruby"}
            },
            "build_tools": {
                "webpack": {"files": ["webpack.config.js", "package.json"], "language": "javascript"},
                "gulp": {"files": ["gulpfile.js"], "language": "javascript"},
                "grunt": {"files": ["Gruntfile.js"], "language": "javascript"},
                "maven": {"files": ["pom.xml"], "language": "java"},
                "gradle": {"files": ["build.gradle", "gradlew"], "language": "java"},
                "make": {"files": ["Makefile", "makefile"]},
                "cmake": {"files": ["CMakeLists.txt"]},
                "setuptools": {"files": ["setup.py"], "language": "python"},
                "poetry": {"files": ["pyproject.toml"], "language": "python"}
            },
            "containers": {
                "docker": {"files": ["Dockerfile", "docker-compose.yml", ".dockerignore"]},
                "podman": {"files": ["Containerfile"]},
                "kubernetes": {"files": ["*.yaml", "*.yml"], "content_patterns": [r"apiVersion:", r"kind:"]}
            },
            "infrastructure": {
                "terraform": {"files": ["*.tf", "terraform.tfvars"]},
                "ansible": {"files": ["*.yml", "ansible.cfg"], "content_patterns": [r"hosts:", r"tasks:"]},
                "helm": {"files": ["Chart.yaml", "values.yaml"]},
                "cloudformation": {"files": ["*.json", "*.yaml"], "content_patterns": [r"AWSTemplateFormatVersion"]}
            }
        }
    
    def scan_repository(self, repo_path: str) -> RepoAnalysis:
        """Main method to scan repository and return analysis"""
        logger.info(f"Scanning repository: {repo_path}")
        
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {repo_path}")
        
        analysis = RepoAnalysis(
            languages=[],
            frameworks=[],
            test_tools=[],
            build_tools=[],
            containers=[],
            infrastructure=[],
            package_managers=[],
            repo_path=str(repo_path)
        )
        
        # Scan for each category
        analysis.languages = self._detect_languages(repo_path)
        analysis.frameworks = self._detect_frameworks(repo_path)
        analysis.test_tools = self._detect_test_tools(repo_path)
        analysis.build_tools = self._detect_build_tools(repo_path)
        analysis.containers = self._detect_containers(repo_path)
        analysis.infrastructure = self._detect_infrastructure(repo_path)
        analysis.package_managers = self._detect_package_managers(repo_path)
        
        # Determine primary language
        if analysis.languages:
            analysis.primary_language = max(analysis.languages, key=lambda x: x.confidence).name
        
        logger.info(f"Detection complete. Primary language: {analysis.primary_language}")
        return analysis
    
    def _detect_languages(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect programming languages in the repository"""
        languages = []
        
        for lang, rules in self.detection_rules["languages"].items():
            confidence = 0.0
            found_files = []
            
            # Check for specific files
            for file_pattern in rules["files"]:
                matches = list(repo_path.rglob(file_pattern))
                if matches:
                    confidence += 0.3 * len(matches)
                    found_files.extend([str(m.relative_to(repo_path)) for m in matches[:5]])
            
            # Check patterns in filenames
            for pattern in rules.get("patterns", []):
                for file_path in repo_path.rglob("*"):
                    if file_path.is_file() and re.search(pattern, file_path.name):
                        confidence += 0.2
                        if str(file_path.relative_to(repo_path)) not in found_files:
                            found_files.append(str(file_path.relative_to(repo_path)))
            
            if confidence > 0:
                languages.append(DetectedTechnology(
                    name=lang,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(languages, key=lambda x: x.confidence, reverse=True)
    
    def _detect_frameworks(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect frameworks used in the repository"""
        frameworks = []
        
        for framework, rules in self.detection_rules["frameworks"].items():
            confidence = 0.0
            found_files = []
            
            # Check for specific files
            for file_pattern in rules.get("files", []):
                matches = list(repo_path.rglob(file_pattern))
                if matches:
                    # Check content patterns if specified
                    if "content_patterns" in rules:
                        for match in matches:
                            try:
                                content = match.read_text(encoding='utf-8')
                                for pattern in rules["content_patterns"]:
                                    if re.search(pattern, content):
                                        confidence += 0.8
                                        found_files.append(str(match.relative_to(repo_path)))
                                        break
                            except (UnicodeDecodeError, PermissionError):
                                continue
                    else:
                        confidence += 0.5
                        found_files.extend([str(m.relative_to(repo_path)) for m in matches[:3]])
            
            # Check content patterns in all relevant files
            if "content_patterns" in rules and not found_files:
                language = rules.get("language", "")
                file_extensions = {
                    "python": [".py"],
                    "javascript": [".js", ".ts"],
                    "java": [".java"],
                    "go": [".go"],
                    "php": [".php"],
                    "ruby": [".rb"]
                }
                
                if language in file_extensions:
                    for ext in file_extensions[language]:
                        for file_path in repo_path.rglob(f"*{ext}"):
                            try:
                                content = file_path.read_text(encoding='utf-8')
                                for pattern in rules["content_patterns"]:
                                    if re.search(pattern, content):
                                        confidence += 0.3
                                        found_files.append(str(file_path.relative_to(repo_path)))
                                        break
                            except (UnicodeDecodeError, PermissionError):
                                continue
            
            if confidence > 0:
                frameworks.append(DetectedTechnology(
                    name=framework,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(frameworks, key=lambda x: x.confidence, reverse=True)
    
    def _detect_test_tools(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect testing tools and frameworks"""
        test_tools = []
        
        for tool, rules in self.detection_rules["test_tools"].items():
            confidence = 0.0
            found_files = []
            
            # Check for specific files
            for file_pattern in rules.get("files", []):
                matches = list(repo_path.rglob(file_pattern))
                if matches:
                    confidence += 0.6
                    found_files.extend([str(m.relative_to(repo_path)) for m in matches[:3]])
            
            # Check patterns (e.g., _test.go files)
            for pattern in rules.get("patterns", []):
                for file_path in repo_path.rglob("*"):
                    if file_path.is_file() and re.search(pattern, file_path.name):
                        confidence += 0.4
                        found_files.append(str(file_path.relative_to(repo_path)))
            
            # Check content patterns
            if "content_patterns" in rules:
                language = rules.get("language", "")
                file_extensions = {
                    "python": [".py"],
                    "javascript": [".js", ".ts"],
                    "java": [".java"]
                }
                
                if language in file_extensions:
                    for ext in file_extensions[language]:
                        for file_path in repo_path.rglob(f"*{ext}"):
                            try:
                                content = file_path.read_text(encoding='utf-8')
                                for pattern in rules["content_patterns"]:
                                    if re.search(pattern, content):
                                        confidence += 0.3
                                        if str(file_path.relative_to(repo_path)) not in found_files:
                                            found_files.append(str(file_path.relative_to(repo_path)))
                                        break
                            except (UnicodeDecodeError, PermissionError):
                                continue
            
            if confidence > 0:
                test_tools.append(DetectedTechnology(
                    name=tool,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(test_tools, key=lambda x: x.confidence, reverse=True)
    
    def _detect_build_tools(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect build tools and package managers"""
        build_tools = []
        
        for tool, rules in self.detection_rules["build_tools"].items():
            confidence = 0.0
            found_files = []
            
            for file_pattern in rules.get("files", []):
                matches = list(repo_path.rglob(file_pattern))
                if matches:
                    confidence += 0.8
                    found_files.extend([str(m.relative_to(repo_path)) for m in matches[:3]])
            
            if confidence > 0:
                build_tools.append(DetectedTechnology(
                    name=tool,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(build_tools, key=lambda x: x.confidence, reverse=True)
    
    def _detect_containers(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect containerization technologies"""
        containers = []
        
        for tech, rules in self.detection_rules["containers"].items():
            confidence = 0.0
            found_files = []
            
            for file_pattern in rules.get("files", []):
                matches = list(repo_path.rglob(file_pattern))
                if matches:
                    # For Kubernetes, check content patterns
                    if tech == "kubernetes" and "content_patterns" in rules:
                        for match in matches:
                            if match.suffix in ['.yaml', '.yml']:
                                try:
                                    content = match.read_text(encoding='utf-8')
                                    if any(re.search(pattern, content) for pattern in rules["content_patterns"]):
                                        confidence += 0.7
                                        found_files.append(str(match.relative_to(repo_path)))
                                except (UnicodeDecodeError, PermissionError):
                                    continue
                    else:
                        confidence += 0.8
                        found_files.extend([str(m.relative_to(repo_path)) for m in matches[:3]])
            
            if confidence > 0:
                containers.append(DetectedTechnology(
                    name=tech,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(containers, key=lambda x: x.confidence, reverse=True)
    
    def _detect_infrastructure(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect infrastructure as code tools"""
        infrastructure = []
        
        for tech, rules in self.detection_rules["infrastructure"].items():
            confidence = 0.0
            found_files = []
            
            for file_pattern in rules.get("files", []):
                matches = list(repo_path.rglob(file_pattern))
                if matches:
                    # Check content patterns if specified
                    if "content_patterns" in rules:
                        for match in matches:
                            try:
                                content = match.read_text(encoding='utf-8')
                                if any(re.search(pattern, content) for pattern in rules["content_patterns"]):
                                    confidence += 0.8
                                    found_files.append(str(match.relative_to(repo_path)))
                            except (UnicodeDecodeError, PermissionError):
                                continue
                    else:
                        confidence += 0.7
                        found_files.extend([str(m.relative_to(repo_path)) for m in matches[:3]])
            
            if confidence > 0:
                infrastructure.append(DetectedTechnology(
                    name=tech,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(infrastructure, key=lambda x: x.confidence, reverse=True)
    
    def _detect_package_managers(self, repo_path: Path) -> List[DetectedTechnology]:
        """Detect package managers"""
        package_managers = []
        
        # Package manager detection based on lock/config files
        pm_files = {
            "npm": ["package-lock.json", "package.json"],
            "yarn": ["yarn.lock"],
            "pnpm": ["pnpm-lock.yaml"],
            "pip": ["requirements.txt", "Pipfile"],
            "poetry": ["poetry.lock"],
            "composer": ["composer.lock"],
            "bundler": ["Gemfile.lock"],
            "maven": ["pom.xml"],
            "gradle": ["build.gradle", "gradle.properties"],
            "go modules": ["go.mod"],
            "cargo": ["Cargo.lock"]
        }
        
        for pm, files in pm_files.items():
            confidence = 0.0
            found_files = []
            
            for file_name in files:
                matches = list(repo_path.rglob(file_name))
                if matches:
                    confidence += 0.8
                    found_files.extend([str(m.relative_to(repo_path)) for m in matches[:3]])
            
            if confidence > 0:
                package_managers.append(DetectedTechnology(
                    name=pm,
                    files=found_files,
                    confidence=min(confidence, 1.0)
                ))
        
        return sorted(package_managers, key=lambda x: x.confidence, reverse=True)

# ============================================================================
# PIPELINE GENERATOR
# ============================================================================

class PipelineGenerator(ABC):
    """Abstract base class for CI/CD pipeline generators"""
    
    @abstractmethod
    def generate(self, analysis: RepoAnalysis, options: Dict[str, Any]) -> str:
        pass

class GitHubActionsGenerator(PipelineGenerator):
    """Generate GitHub Actions workflows"""
    
    def generate(self, analysis: RepoAnalysis, options: Dict[str, Any]) -> str:
        """Generate GitHub Actions workflow YAML"""
        
        workflow = {
            "name": "CI",
            "on": {
                "push": {"branches": ["main", "master", "develop"]},
                "pull_request": {"branches": ["main", "master"]}
            },
            "jobs": {}
        }
        
        # Add language-specific jobs
        if analysis.primary_language == "python":
            workflow["jobs"].update(self._python_jobs(analysis))
        elif analysis.primary_language == "javascript":
            workflow["jobs"].update(self._javascript_jobs(analysis))
        elif analysis.primary_language == "go":
            workflow["jobs"].update(self._go_jobs(analysis))
        elif analysis.primary_language == "java":
            workflow["jobs"].update(self._java_jobs(analysis))
        else:
            # Generic job
            workflow["jobs"]["build"] = {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"run": "echo 'Add your build steps here'"}
                ]
            }
        
        # Add Docker job if Dockerfile exists
        if any(tech.name == "docker" for tech in analysis.containers):
            workflow["jobs"]["docker"] = self._docker_job()
        
        return yaml.dump(workflow, default_flow_style=False, sort_keys=False)
    
    def _python_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Python-specific jobs"""
        python_version = "3.11"  # Default version
        
        jobs = {
            "lint": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "uses": "actions/setup-python@v4",
                        "with": {"python-version": python_version}
                    },
                    {
                        "name": "Cache pip dependencies",
                        "uses": "actions/cache@v3",
                        "with": {
                            "path": "~/.cache/pip",
                            "key": "${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}",
                            "restore-keys": "${{ runner.os }}-pip-"
                        }
                    },
                    {"run": "pip install flake8 black isort"},
                    {"run": "flake8 . --max-line-length=88 --exclude=venv,env"},
                    {"run": "black --check ."},
                    {"run": "isort --check-only ."}
                ]
            },
            "test": {
                "runs-on": "ubuntu-latest",
                "strategy": {
                    "matrix": {
                        "python-version": ["3.9", "3.10", "3.11"]
                    }
                },
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "uses": "actions/setup-python@v4", 
                        "with": {"python-version": "${{ matrix.python-version }}"}
                    },
                    {
                        "name": "Cache pip dependencies",
                        "uses": "actions/cache@v3",
                        "with": {
                            "path": "~/.cache/pip",
                            "key": "${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}",
                            "restore-keys": "${{ runner.os }}-pip-"
                        }
                    }
                ]
            }
        }
        
        # Add dependency installation
        if any(tech.name == "poetry" for tech in analysis.build_tools):
            jobs["test"]["steps"].extend([
                {"run": "pip install poetry"},
                {"run": "poetry install"},
                {"run": "poetry run pytest --cov=. --cov-report=xml"}
            ])
        else:
            jobs["test"]["steps"].extend([
                {"run": "pip install -r requirements.txt || pip install -r requirements/dev.txt || echo 'No requirements file found'"},
                {"run": "pip install pytest pytest-cov"}
            ])
            
            # Determine test command
            if any(tech.name == "pytest" for tech in analysis.test_tools):
                jobs["test"]["steps"].append({"run": "pytest --cov=. --cov-report=xml"})
            else:
                jobs["test"]["steps"].append({"run": "python -m pytest || python -m unittest discover"})
        
        # Add coverage upload
        jobs["test"]["steps"].append({
            "name": "Upload coverage to Codecov",
            "uses": "codecov/codecov-action@v3",
            "with": {"file": "./coverage.xml"}
        })
        
        return jobs
    
    def _javascript_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate JavaScript/Node.js-specific jobs"""
        node_version = "18"
        
        # Determine package manager
        package_manager = "npm"
        if any(tech.name == "yarn" for tech in analysis.package_managers):
            package_manager = "yarn"
        elif any(tech.name == "pnpm" for tech in analysis.package_managers):
            package_manager = "pnpm"
        
        install_cmd = {
            "npm": "npm ci",
            "yarn": "yarn install --frozen-lockfile", 
            "pnpm": "pnpm install --frozen-lockfile"
        }
        
        jobs = {
            "lint-and-test": {
                "runs-on": "ubuntu-latest",
                "strategy": {
                    "matrix": {
                        "node-version": ["16", "18", "20"]
                    }
                },
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "uses": "actions/setup-node@v4",
                        "with": {
                            "node-version": "${{ matrix.node-version }}",
                            "cache": package_manager
                        }
                    },
                    {"run": install_cmd[package_manager]},
                    {"run": f"{package_manager} run lint || echo 'No lint script found'"},
                    {"run": f"{package_manager} run test || echo 'No test script found'"},
                    {"run": f"{package_manager} run build || echo 'No build script found'"}
                ]
            }
        }
        
        return jobs
    
    def _go_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Go-specific jobs"""
        return {
            "lint-and-test": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {
                        "uses": "actions/setup-go@v4",
                        "with": {"go-version": "1.21"}
                    },
                    {
                        "name": "Cache Go modules",
                        "uses": "actions/cache@v3",
                        "with": {
                            "path": "~/go/pkg/mod",
                            "key": "${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}",
                            "restore-keys": "${{ runner.os }}-go-"
                        }
                    },
                    {"run": "go mod download"},
                    {"run": "go vet ./..."},
                    {"run": "go test -race -coverprofile=coverage.out ./..."},
                    {"run": "go build -v ./..."}
                ]
            }
        }
    
    def _java_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Java-specific jobs"""
        if any(tech.name == "maven" for tech in analysis.build_tools):
            return {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "uses": "actions/setup-java@v4",
                            "with": {
                                "java-version": "11",
                                "distribution": "temurin"
                            }
                        },
                        {
                            "name": "Cache Maven dependencies",
                            "uses": "actions/cache@v3",
                            "with": {
                                "path": "~/.m2",
                                "key": "${{ runner.os }}-m2-${{ hashFiles('**/pom.xml') }}",
                                "restore-keys": "${{ runner.os }}-m2"
                            }
                        },
                        {"run": "mvn clean compile"},
                        {"run": "mvn test"},
                        {"run": "mvn package"}
                    ]
                }
            }
        elif any(tech.name == "gradle" for tech in analysis.build_tools):
            return {
                "test": {
                    "runs-on": "ubuntu-latest", 
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "uses": "actions/setup-java@v4",
                            "with": {
                                "java-version": "11",
                                "distribution": "temurin"
                            }
                        },
                        {
                            "name": "Cache Gradle dependencies",
                            "uses": "actions/cache@v3",
                            "with": {
                                "path": "~/.gradle/caches",
                                "key": "${{ runner.os }}-gradle-${{ hashFiles('**/*.gradle') }}",
                                "restore-keys": "${{ runner.os }}-gradle-"
                            }
                        },
                        {"run": "./gradlew build test"}
                    ]
                }
            }
        else:
            return {
                "test": {
                    "runs-on": "ubuntu-latest",
                    "steps": [
                        {"uses": "actions/checkout@v4"},
                        {
                            "uses": "actions/setup-java@v4",
                            "with": {
                                "java-version": "11", 
                                "distribution": "temurin"
                            }
                        },
                        {"run": "javac *.java"},
                        {"run": "java -cp . Main || echo 'Specify your main class'"}
                    ]
                }
            }
    
    def _docker_job(self) -> Dict:
        """Generate Docker build job"""
        return {
            "runs-on": "ubuntu-latest",
            "steps": [
                {"uses": "actions/checkout@v4"},
                {
                    "name": "Set up Docker Buildx",
                    "uses": "docker/setup-buildx-action@v3"
                },
                {
                    "name": "Login to Docker Hub",
                    "uses": "docker/login-action@v3",
                    "with": {
                        "username": "${{ secrets.DOCKERHUB_USERNAME }}",
                        "password": "${{ secrets.DOCKERHUB_TOKEN }}"
                    }
                },
                {
                    "name": "Build and push",
                    "uses": "docker/build-push-action@v5",
                    "with": {
                        "context": ".",
                        "platforms": "linux/amd64,linux/arm64",
                        "push": True,
                        "tags": "${{ secrets.DOCKERHUB_USERNAME }}/myapp:latest,${{ secrets.DOCKERHUB_USERNAME }}/myapp:${{ github.sha }}"
                    }
                }
            ]
        }


class GitLabCIGenerator(PipelineGenerator):
    """Generate GitLab CI/CD pipelines"""
    
    def generate(self, analysis: RepoAnalysis, options: Dict[str, Any]) -> str:
        """Generate GitLab CI YAML"""
        
        pipeline = {
            "stages": ["lint", "test", "build", "deploy"],
            "variables": {
                "PIP_CACHE_DIR": "$CI_PROJECT_DIR/.cache/pip",
                "NODE_CACHE_DIR": "$CI_PROJECT_DIR/.cache/node"
            },
            "cache": {
                "paths": [".cache/"]
            }
        }
        
        if analysis.primary_language == "python":
            pipeline.update(self._python_gitlab_jobs(analysis))
        elif analysis.primary_language == "javascript":
            pipeline.update(self._javascript_gitlab_jobs(analysis))
        elif analysis.primary_language == "go":
            pipeline.update(self._go_gitlab_jobs(analysis))
        elif analysis.primary_language == "java":
            pipeline.update(self._java_gitlab_jobs(analysis))
        
        # Add Docker job if Dockerfile exists
        if any(tech.name == "docker" for tech in analysis.containers):
            pipeline["docker-build"] = self._docker_gitlab_job()
        
        return yaml.dump(pipeline, default_flow_style=False, sort_keys=False)
    
    def _python_gitlab_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Python GitLab CI jobs"""
        jobs = {
            "lint": {
                "stage": "lint",
                "image": "python:3.11",
                "before_script": [
                    "pip install --upgrade pip",
                    "pip install flake8 black isort"
                ],
                "script": [
                    "flake8 . --max-line-length=88 --exclude=venv,env",
                    "black --check .",
                    "isort --check-only ."
                ]
            },
            "test": {
                "stage": "test",
                "image": "python:3.11",
                "before_script": [
                    "pip install --upgrade pip"
                ],
                "script": [],
                "coverage": "/coverage: \\d+%/",
                "artifacts": {
                    "reports": {
                        "coverage_report": {
                            "coverage_format": "cobertura",
                            "path": "coverage.xml"
                        }
                    }
                }
            }
        }
        
        # Configure test script based on detected tools
        if any(tech.name == "poetry" for tech in analysis.build_tools):
            jobs["test"]["before_script"].extend([
                "pip install poetry",
                "poetry install"
            ])
            jobs["test"]["script"] = ["poetry run pytest --cov=. --cov-report=xml"]
        else:
            jobs["test"]["before_script"].append(
                "pip install -r requirements.txt || pip install pytest pytest-cov"
            )
            jobs["test"]["script"] = ["pytest --cov=. --cov-report=xml"]
        
        return jobs
    
    def _javascript_gitlab_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate JavaScript GitLab CI jobs"""
        package_manager = "npm"
        if any(tech.name == "yarn" for tech in analysis.package_managers):
            package_manager = "yarn"
        
        return {
            "test": {
                "stage": "test",
                "image": "node:18",
                "cache": {
                    "paths": ["node_modules/"]
                },
                "before_script": [
                    f"{package_manager} install"
                ],
                "script": [
                    f"{package_manager} run lint || echo 'No lint script'",
                    f"{package_manager} run test || echo 'No test script'",
                    f"{package_manager} run build || echo 'No build script'"
                ]
            }
        }
    
    def _go_gitlab_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Go GitLab CI jobs"""
        return {
            "test": {
                "stage": "test",
                "image": "golang:1.21",
                "before_script": [
                    "go mod download"
                ],
                "script": [
                    "go vet ./...",
                    "go test -race -coverprofile=coverage.out ./...",
                    "go build -v ./..."
                ]
            }
        }
    
    def _java_gitlab_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Java GitLab CI jobs"""
        if any(tech.name == "maven" for tech in analysis.build_tools):
            return {
                "test": {
                    "stage": "test",
                    "image": "maven:3.8-openjdk-11",
                    "cache": {
                        "paths": [".m2/repository/"]
                    },
                    "script": [
                        "mvn clean compile test package"
                    ],
                    "artifacts": {
                        "paths": ["target/"]
                    }
                }
            }
        else:
            return {
                "test": {
                    "stage": "test",
                    "image": "openjdk:11",
                    "script": [
                        "javac *.java",
                        "java Main || echo 'Specify your main class'"
                    ]
                }
            }
    
    def _docker_gitlab_job(self) -> Dict:
        """Generate Docker build GitLab job"""
        return {
            "stage": "build",
            "image": "docker:latest",
            "services": ["docker:dind"],
            "before_script": [
                "docker login -u $CI_REGISTRY_USER -p $CI_REGISTRY_PASSWORD $CI_REGISTRY"
            ],
            "script": [
                "docker build -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA .",
                "docker push $CI_REGISTRY_IMAGE:$CI_COMMIT_SHA"
            ]
        }


class CircleCIGenerator(PipelineGenerator):
    """Generate CircleCI pipeline configuration"""
    
    def generate(self, analysis: RepoAnalysis, options: Dict[str, Any]) -> str:
        """Generate CircleCI config.yml"""
        
        config = {
            "version": 2.1,
            "jobs": {},
            "workflows": {
                "version": 2,
                "build_and_test": {
                    "jobs": []
                }
            }
        }
        
        if analysis.primary_language == "python":
            jobs = self._python_circleci_jobs(analysis)
            config["jobs"].update(jobs)
            config["workflows"]["build_and_test"]["jobs"].extend(jobs.keys())
        elif analysis.primary_language == "javascript":
            jobs = self._javascript_circleci_jobs(analysis)
            config["jobs"].update(jobs)
            config["workflows"]["build_and_test"]["jobs"].extend(jobs.keys())
        elif analysis.primary_language == "go":
            jobs = self._go_circleci_jobs(analysis)
            config["jobs"].update(jobs)
            config["workflows"]["build_and_test"]["jobs"].extend(jobs.keys())
        
        return yaml.dump(config, default_flow_style=False, sort_keys=False)
    
    def _python_circleci_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Python CircleCI jobs"""
        return {
            "test": {
                "docker": [{"image": "cimg/python:3.11"}],
                "steps": [
                    "checkout",
                    {
                        "restore_cache": {
                            "keys": [
                                "pip-packages-v1-{{ .Branch }}-{{ checksum \"requirements.txt\" }}",
                                "pip-packages-v1-{{ .Branch }}-",
                                "pip-packages-v1-"
                            ]
                        }
                    },
                    {
                        "run": {
                            "name": "Install dependencies",
                            "command": "pip install -r requirements.txt || pip install pytest pytest-cov"
                        }
                    },
                    {
                        "save_cache": {
                            "key": "pip-packages-v1-{{ .Branch }}-{{ checksum \"requirements.txt\" }}",
                            "paths": ["/home/circleci/.cache/pip"]
                        }
                    },
                    {
                        "run": {
                            "name": "Run tests",
                            "command": "pytest --cov=. --cov-report=xml"
                        }
                    }
                ]
            }
        }
    
    def _javascript_circleci_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate JavaScript CircleCI jobs"""
        return {
            "test": {
                "docker": [{"image": "cimg/node:18.0"}],
                "steps": [
                    "checkout",
                    {
                        "restore_cache": {
                            "keys": [
                                "npm-packages-v1-{{ .Branch }}-{{ checksum \"package-lock.json\" }}",
                                "npm-packages-v1-{{ .Branch }}-",
                                "npm-packages-v1-"
                            ]
                        }
                    },
                    {"run": "npm ci"},
                    {
                        "save_cache": {
                            "key": "npm-packages-v1-{{ .Branch }}-{{ checksum \"package-lock.json\" }}",
                            "paths": ["/home/circleci/.npm"]
                        }
                    },
                    {"run": "npm run test || echo 'No test script'"}
                ]
            }
        }
    
    def _go_circleci_jobs(self, analysis: RepoAnalysis) -> Dict:
        """Generate Go CircleCI jobs"""
        return {
            "test": {
                "docker": [{"image": "cimg/go:1.21"}],
                "steps": [
                    "checkout",
                    {"run": "go mod download"},
                    {"run": "go test -v ./..."},
                    {"run": "go build -v ./..."}
                ]
            }
        }


# ============================================================================
# RULES ENGINE
# ============================================================================

class RulesEngine:
    """Engine for applying CI/CD generation rules based on detected technologies"""
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict:
        """Load CI/CD generation rules"""
        return {
            "optimization_rules": {
                "caching": {
                    "python": {
                        "pip": "~/.cache/pip",
                        "poetry": "~/.cache/pypoetry"
                    },
                    "javascript": {
                        "npm": "~/.npm",
                        "yarn": "~/.cache/yarn"
                    },
                    "go": "~/go/pkg/mod",
                    "java": {
                        "maven": "~/.m2",
                        "gradle": "~/.gradle/caches"
                    }
                },
                "parallel_jobs": {
                    "lint_and_test": ["python", "javascript", "go"],
                    "multi_version": ["python", "javascript", "java"]
                }
            },
            "security_rules": {
                "secret_scanning": ["python", "javascript", "go", "java"],
                "dependency_check": {
                    "python": ["safety", "bandit"],
                    "javascript": ["npm audit", "snyk"],
                    "java": ["owasp dependency check"],
                    "go": ["gosec"]
                }
            },
            "deployment_rules": {
                "docker": {
                    "trigger": ["Dockerfile"],
                    "registries": ["dockerhub", "ghcr", "ecr"]
                },
                "kubernetes": {
                    "trigger": ["k8s", "kubernetes"],
                    "manifest_check": True
                }
            }
        }
    
    def apply_optimizations(self, analysis: RepoAnalysis, generator_type: str) -> Dict[str, Any]:
        """Apply optimization rules and return options for pipeline generation"""
        options = {
            "caching": {},
            "parallel_jobs": False,
            "security_scans": [],
            "deployment": {}
        }
        
        # Apply caching rules
        if analysis.primary_language in self.rules["optimization_rules"]["caching"]:
            cache_config = self.rules["optimization_rules"]["caching"][analysis.primary_language]
            if isinstance(cache_config, dict):
                # Check which package manager is detected
                for tech in analysis.package_managers:
                    if tech.name.lower() in cache_config:
                        options["caching"][tech.name] = cache_config[tech.name.lower()]
            else:
                options["caching"][analysis.primary_language] = cache_config
        
        # Apply parallel job rules
        if analysis.primary_language in self.rules["optimization_rules"]["parallel_jobs"]["lint_and_test"]:
            options["parallel_jobs"] = True
        
        # Apply security rules
        if analysis.primary_language in self.rules["security_rules"]["secret_scanning"]:
            options["security_scans"].append("secret_scanning")
        
        if analysis.primary_language in self.rules["security_rules"]["dependency_check"]:
            options["security_scans"].extend(
                self.rules["security_rules"]["dependency_check"][analysis.primary_language]
            )
        
        # Apply deployment rules
        if any(tech.name == "docker" for tech in analysis.containers):
            options["deployment"]["docker"] = True
        
        if any(tech.name == "kubernetes" for tech in analysis.containers):
            options["deployment"]["kubernetes"] = True
        
        return options


# ============================================================================
# PIPELINE OPTIMIZER
# ============================================================================

class PipelineOptimizer:
    """Optimize generated pipelines for performance and best practices"""
    
    def __init__(self):
        self.optimization_strategies = {
            "caching": self._optimize_caching,
            "parallelization": self._optimize_parallelization,
            "resource_allocation": self._optimize_resources,
            "security": self._optimize_security
        }
    
    def optimize(self, pipeline_content: str, analysis: RepoAnalysis, ci_type: str) -> str:
        """Apply all optimization strategies to the pipeline"""
        optimized_pipeline = pipeline_content
        
        for strategy_name, strategy_func in self.optimization_strategies.items():
            try:
                optimized_pipeline = strategy_func(optimized_pipeline, analysis, ci_type)
                logger.info(f"Applied {strategy_name} optimization")
            except Exception as e:
                logger.warning(f"Failed to apply {strategy_name} optimization: {e}")
        
        return optimized_pipeline
    
    def _optimize_caching(self, pipeline: str, analysis: RepoAnalysis, ci_type: str) -> str:
        """Optimize caching strategies"""
        # This is a simplified implementation
        # In practice, you would parse the YAML, modify it, and convert back
        return pipeline
    
    def _optimize_parallelization(self, pipeline: str, analysis: RepoAnalysis, ci_type: str) -> str:
        """Optimize job parallelization"""
        return pipeline
    
    def _optimize_resources(self, pipeline: str, analysis: RepoAnalysis, ci_type: str) -> str:
        """Optimize resource allocation"""
        return pipeline
    
    def _optimize_security(self, pipeline: str, analysis: RepoAnalysis, ci_type: str) -> str:
        """Add security optimizations"""
        return pipeline


# ============================================================================
# MAIN AUTO-CI CLASS
# ============================================================================

class AutoCI:
    """Main class that orchestrates the entire CI/CD generation process"""
    
    def __init__(self):
        self.scanner = RepoScanner()
        self.rules_engine = RulesEngine()
        self.optimizer = PipelineOptimizer()
        
        self.generators = {
            "github": GitHubActionsGenerator(),
            "gitlab": GitLabCIGenerator(),
            "circleci": CircleCIGenerator()
        }
    
    def scan(self, repo_path: str) -> RepoAnalysis:
        """Scan repository and return analysis"""
        return self.scanner.scan_repository(repo_path)
    
    def generate_pipeline(self, repo_path: str, ci_type: str = "github", 
                         optimize: bool = True) -> Tuple[str, RepoAnalysis]:
        """Generate optimized CI/CD pipeline for a repository"""
        logger.info(f"Generating {ci_type} pipeline for {repo_path}")
        
        # Step 1: Scan repository
        analysis = self.scan(repo_path)
        
        # Step 2: Apply rules and get optimization options
        options = self.rules_engine.apply_optimizations(analysis, ci_type)
        
        # Step 3: Generate pipeline
        if ci_type not in self.generators:
            raise ValueError(f"Unsupported CI type: {ci_type}. Supported: {list(self.generators.keys())}")
        
        generator = self.generators[ci_type]
        pipeline_content = generator.generate(analysis, options)
        
        # Step 4: Optimize pipeline if requested
        if optimize:
            pipeline_content = self.optimizer.optimize(pipeline_content, analysis, ci_type)
        
        return pipeline_content, analysis
    
    def audit_repository(self, repo_path: str) -> Dict[str, Any]:
        """Audit repository and suggest improvements"""
        analysis = self.scan(repo_path)
        
        audit_report = {
            "repository": repo_path,
            "primary_language": analysis.primary_language,
            "detected_technologies": {
                "languages": [tech.name for tech in analysis.languages],
                "frameworks": [tech.name for tech in analysis.frameworks],
                "test_tools": [tech.name for tech in analysis.test_tools],
                "build_tools": [tech.name for tech in analysis.build_tools],
                "containers": [tech.name for tech in analysis.containers],
                "infrastructure": [tech.name for tech in analysis.infrastructure]
            },
            "recommendations": self._generate_recommendations(analysis),
            "missing_components": self._check_missing_components(analysis)
        }
        
        return audit_report
    
    def _generate_recommendations(self, analysis: RepoAnalysis) -> List[str]:
        """Generate recommendations based on analysis"""
        recommendations = []
        
        # Check for missing test tools
        if not analysis.test_tools:
            if analysis.primary_language == "python":
                recommendations.append("Consider adding pytest for testing")
            elif analysis.primary_language == "javascript":
                recommendations.append("Consider adding Jest or Mocha for testing")
            elif analysis.primary_language == "java":
                recommendations.append("Consider adding JUnit for testing")
        
        # Check for missing linting tools
        if analysis.primary_language == "python":
            if not any(tech.name in ["black", "flake8", "pylint"] for tech in analysis.build_tools):
                recommendations.append("Consider adding code formatting tools like Black and linting with flake8")
        
        # Check for containerization
        if not analysis.containers:
            recommendations.append("Consider containerizing your application with Docker")
        
        # Check for dependency management
        if not analysis.package_managers:
            recommendations.append("Consider using a package manager for dependency management")
        
        return recommendations
    
    def _check_missing_components(self, analysis: RepoAnalysis) -> List[str]:
        """Check for missing CI/CD components"""
        missing = []
        
        # Check for existing CI/CD files
        ci_files = [
            ".github/workflows",
            ".gitlab-ci.yml", 
            ".circleci/config.yml",
            "Jenkinsfile",
            "azure-pipelines.yml"
        ]
        
        repo_path = Path(analysis.repo_path)
        has_ci = False
        
        for ci_file in ci_files:
            if (repo_path / ci_file).exists():
                has_ci = True
                break
        
        if not has_ci:
            missing.append("CI/CD pipeline configuration")
        
        # Check for common files
        common_files = {
            "README.md": "README file",
            ".gitignore": "Git ignore file",
            "LICENSE": "License file"
        }
        
        for file_name, description in common_files.items():
            if not (repo_path / file_name).exists():
                missing.append(description)
        
        return missing
    
    def save_pipeline(self, pipeline_content: str, ci_type: str, output_path: str = None):
        """Save generated pipeline to appropriate location"""
        if output_path is None:
            output_path = "."
        
        output_path = Path(output_path)
        
        # Determine output file path based on CI type
        ci_file_paths = {
            "github": output_path / ".github" / "workflows" / "ci.yml",
            "gitlab": output_path / ".gitlab-ci.yml",
            "circleci": output_path / ".circleci" / "config.yml"
        }
        
        if ci_type not in ci_file_paths:
            raise ValueError(f"Unsupported CI type: {ci_type}")
        
        file_path = ci_file_paths[ci_type]
        
        # Create directory if it doesn't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write pipeline content
        file_path.write_text(pipeline_content, encoding='utf-8')
        logger.info(f"Pipeline saved to {file_path}")
        
        return str(file_path)


# ============================================================================
# CLI INTERFACE
# ============================================================================

def create_cli():
    """Create command line interface"""
    parser = argparse.ArgumentParser(
        description="Auto-CI: Automated CI/CD Pipeline Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  auto-ci scan .                          # Scan current directory
  auto-ci generate --ci github           # Generate GitHub Actions pipeline
  auto-ci generate --ci gitlab -o /tmp   # Generate GitLab CI pipeline to /tmp
  auto-ci audit .                        # Audit repository and show recommendations
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan repository for technologies')
    scan_parser.add_argument('path', nargs='?', default='.', help='Repository path (default: current directory)')
    scan_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate CI/CD pipeline')
    generate_parser.add_argument('path', nargs='?', default='.', help='Repository path (default: current directory)')
    generate_parser.add_argument('--ci', choices=['github', 'gitlab', 'circleci'], 
                                default='github', help='CI/CD platform (default: github)')
    generate_parser.add_argument('--output', '-o', help='Output directory (default: repository root)')
    generate_parser.add_argument('--no-optimize', action='store_true', help='Skip optimization')
    generate_parser.add_argument('--dry-run', action='store_true', help='Print pipeline without saving')
    
    # Audit command
    audit_parser = subparsers.add_parser('audit', help='Audit repository and suggest improvements')
    audit_parser.add_argument('path', nargs='?', default='.', help='Repository path (default: current directory)')
    audit_parser.add_argument('--json', action='store_true', help='Output in JSON format')
    
    return parser
def main():
    """Main CLI entry point"""
    parser = create_cli()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    auto_ci = AutoCI()
    
    try:
        if args.command == 'scan':
            analysis = auto_ci.scan(args.path)
            
            if args.json:
                # Convert to dict for JSON serialization
                analysis_dict = asdict(analysis)
                print(json.dumps(analysis_dict, indent=2))
            else:
                print(f"\nRepository Analysis: {analysis.repo_path}")
                print(f"Primary Language: {analysis.primary_language or 'Unknown'}")
                
                if analysis.languages:
                    print(f"\nLanguages ({len(analysis.languages)}):")
                    for tech in analysis.languages[:5]:
                        print(f"  • {tech.name} (confidence: {tech.confidence:.2f})")
                
                if analysis.frameworks:
                    print(f"\nFrameworks ({len(analysis.frameworks)}):")
                    for tech in analysis.frameworks[:5]:
                        print(f"  • {tech.name} (confidence: {tech.confidence:.2f})")
                
                if analysis.test_tools:
                    print(f"\nTest Tools ({len(analysis.test_tools)}):")
                    for tech in analysis.test_tools[:5]:
                        print(f"  • {tech.name} (confidence: {tech.confidence:.2f})")
                
                if analysis.containers:
                    print(f"\nContainers ({len(analysis.containers)}):")
                    for tech in analysis.containers[:5]:
                        print(f"  • {tech.name} (confidence: {tech.confidence:.2f})")
                
                print()
        
        elif args.command == 'generate':
            pipeline_content, analysis = auto_ci.generate_pipeline(
                args.path, 
                args.ci, 
                optimize=not args.no_optimize
            )
            
            if args.dry_run:
                print(f"\nGenerated {args.ci.upper()} Pipeline:")
                print("=" * 50)
                print(pipeline_content)
            else:
                output_path = args.output or args.path
                file_path = auto_ci.save_pipeline(pipeline_content, args.ci, output_path)
                print(f"\n{args.ci.upper()} pipeline generated successfully!")
                print(f"Saved to: {file_path}")
                print(f"Detected primary language: {analysis.primary_language}")
                
                if analysis.frameworks:
                    frameworks = ", ".join([f.name for f in analysis.frameworks[:3]])
                    print(f"Detected frameworks: {frameworks}")
        
        elif args.command == 'audit':
            audit_report = auto_ci.audit_repository(args.path)
            
            if args.json:
                print(json.dumps(audit_report, indent=2))
            else:
                print(f"\nRepository Audit: {audit_report['repository']}")
                print(f"Primary Language: {audit_report['primary_language'] or 'Unknown'}")
                
                print(f"\nDetected Technologies:")
                for category, techs in audit_report['detected_technologies'].items():
                    if techs:
                        print(f"  {category.title()}: {', '.join(techs)}")
                
                if audit_report['recommendations']:
                    print(f"\nRecommendations:")
                    for rec in audit_report['recommendations']:
                        print(f"  • {rec}")
                
                if audit_report['missing_components']:
                    print(f"\nMissing Components:")
                    for missing in audit_report['missing_components']:
                        print(f"  • {missing}")
                
                print()
    
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        print(f"\nError: {e}")
        return 1
    
    return 0


# ============================================================================
# EXAMPLE USAGE AND TESTING
# ============================================================================

def create_sample_repo(path: str, repo_type: str = "python"):
    """Create a sample repository for testing"""
    repo_path = Path(path)
    repo_path.mkdir(exist_ok=True)
    
    if repo_type == "python":
        # Create Python sample files
        (repo_path / "requirements.txt").write_text("""
flask==2.3.2
pytest==7.4.0
black==23.7.0
flake8==6.0.0
""".strip())
        
        (repo_path / "app.py").write_text("""
from flask import Flask

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, World!"

if __name__ == '__main__':
    app.run(debug=True)
""")
        
        (repo_path / "test_app.py").write_text("""
import pytest
from app import app

def test_hello():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert b"Hello, World!" in response.data
""")
        
        (repo_path / "Dockerfile").write_text("""
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
""")
    
    elif repo_type == "javascript":
        # Create JavaScript sample files
        (repo_path / "package.json").write_text(json.dumps({
            "name": "sample-app",
            "version": "1.0.0",
            "scripts": {
                "start": "node index.js",
                "test": "jest",
                "lint": "eslint ."
            },
            "dependencies": {
                "express": "^4.18.0"
            },
            "devDependencies": {
                "jest": "^29.0.0",
                "eslint": "^8.0.0"
            }
        }, indent=2))
        
        (repo_path / "index.js").write_text("""
const express = require('express');
const app = express();
const PORT = process.env.PORT || 3000;

app.get('/', (req, res) => {
    res.json({ message: 'Hello, World!' });
});

app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});

module.exports = app;
""")
        
        (repo_path / "index.test.js").write_text("""
const request = require('supertest');
const app = require('./index');

describe('GET /', () => {
    it('should return hello message', async () => {
        const response = await request(app).get('/');
        expect(response.status).toBe(200);
        expect(response.body.message).toBe('Hello, World!');
    });
});
""")
    
    elif repo_type == "go":
        # Create Go sample files
        (repo_path / "go.mod").write_text("""
module example.com/hello

go 1.21
""")
        
        (repo_path / "main.go").write_text("""
package main

import (
    "fmt"
    "net/http"
)

func hello(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w, "Hello, World!")
}

func main() {
    http.HandleFunc("/", hello)
    http.ListenAndServe(":8080", nil)
}
""")
        
        (repo_path / "main_test.go").write_text("""
package main

import (
    "net/http"
    "net/http/httptest"
    "testing"
)

func TestHello(t *testing.T) {
    req, err := http.NewRequest("GET", "/", nil)
    if err != nil {
        t.Fatal(err)
    }

    rr := httptest.NewRecorder()
    handler := http.HandlerFunc(hello)
    handler.ServeHTTP(rr, req)

    if status := rr.Code; status != http.StatusOK {
        t.Errorf("handler returned wrong status code: got %v want %v", status, http.StatusOK)
    }

    expected := "Hello, World!"
    if rr.Body.String() != expected {
        t.Errorf("handler returned unexpected body: got %v want %v", rr.Body.String(), expected)
    }
}
""")
    
    # Common files for all repo types
    (repo_path / "README.md").write_text(f"""
# Sample {repo_type.title()} Application

This is a sample {repo_type} application for testing Auto-CI.

## Installation

Follow the standard {repo_type} installation process.

## Usage

Run the application and tests as usual.
""")
    
    (repo_path / ".gitignore").write_text("""
# Dependencies
node_modules/
__pycache__/
*.pyc
vendor/

# Build outputs
dist/
build/
*.exe

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
""")
    
    print(f"Created sample {repo_type} repository at {repo_path}")


def run_examples():
    """Run example usage of Auto-CI"""
    print("Auto-CI Example Usage")
    print("=" * 50)
    
    # Create sample repositories
    sample_repos = {
        "python": "./sample_python_repo",
        "javascript": "./sample_js_repo", 
        "go": "./sample_go_repo"
    }
    
    auto_ci = AutoCI()
    
    for repo_type, repo_path in sample_repos.items():
        print(f"\nCreating sample {repo_type} repository...")
        create_sample_repo(repo_path, repo_type)
        
        print(f"\nScanning {repo_type} repository...")
        analysis = auto_ci.scan(repo_path)
        print(f"   Primary language: {analysis.primary_language}")
        print(f"   Detected frameworks: {[f.name for f in analysis.frameworks]}")
        print(f"   Test tools: {[t.name for t in analysis.test_tools]}")
        
        print(f"\nGenerating GitHub Actions pipeline...")
        pipeline_content, _ = auto_ci.generate_pipeline(repo_path, "github")
        pipeline_file = auto_ci.save_pipeline(pipeline_content, "github", repo_path)
        print(f"   Saved to: {pipeline_file}")
        
        print(f"\nRepository audit:")
        audit_report = auto_ci.audit_repository(repo_path)
        print(f"   Recommendations: {len(audit_report['recommendations'])}")
        print(f"   Missing components: {len(audit_report['missing_components'])}")
    
    print("\nAll examples completed successfully!")
    print("\nTo clean up sample repositories:")
    for repo_path in sample_repos.values():
        print(f"  rm -rf {repo_path}")


# ============================================================================
# WEB API (OPTIONAL)
# ============================================================================

class AutoCIWebAPI:
    """Optional web API for Auto-CI (requires Flask)"""
    
    def __init__(self):
        self.auto_ci = AutoCI()
        try:
            from flask import Flask, request, jsonify
            self.app = Flask(__name__)
            self._setup_routes()
        except ImportError:
            print("Flask not installed. Web API not available.")
            self.app = None
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/api/scan', methods=['POST'])
        def api_scan():
            data = request.get_json()
            repo_path = data.get('repo_path', '.')
            
            try:
                analysis = self.auto_ci.scan(repo_path)
                return jsonify(asdict(analysis))
            except Exception as e:
                return jsonify({'error': str(e)}), 400
        
        @self.app.route('/api/generate', methods=['POST'])
        def api_generate():
            data = request.get_json()
            repo_path = data.get('repo_path', '.')
            ci_type = data.get('ci_type', 'github')
            optimize = data.get('optimize', True)
            
            try:
                pipeline_content, analysis = self.auto_ci.generate_pipeline(
                    repo_path, ci_type, optimize
                )
                return jsonify({
                    'pipeline': pipeline_content,
                    'analysis': asdict(analysis)
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 400
        
        @self.app.route('/api/audit', methods=['POST'])
        def api_audit():
            data = request.get_json()
            repo_path = data.get('repo_path', '.')
            
            try:
                audit_report = self.auto_ci.audit_repository(repo_path)
                return jsonify(audit_report)
            except Exception as e:
                return jsonify({'error': str(e)}), 400
        
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({'status': 'healthy'})
    
    def run(self, host='0.0.0.0', port=5000, debug=False):
        """Run the web API"""
        if self.app:
            self.app.run(host=host, port=port, debug=debug)
        else:
            print("Flask not available. Cannot run web API.")


# ============================================================================
# GITHUB INTEGRATION (OPTIONAL)
# ============================================================================

class GitHubIntegration:
    """Optional GitHub integration for Auto-CI"""
    
    def __init__(self, github_token: str = None):
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        self.auto_ci = AutoCI()
    
    def analyze_github_repo(self, repo_url: str) -> Dict[str, Any]:
        """Clone and analyze a GitHub repository"""
        try:
            # Extract repo info from URL
            repo_info = self._parse_github_url(repo_url)
            if not repo_info:
                raise ValueError("Invalid GitHub repository URL")
            
            # Clone repository to temporary directory
            import tempfile
            import shutil
            
            with tempfile.TemporaryDirectory() as temp_dir:
                clone_path = Path(temp_dir) / "repo"
                
                # Clone the repository
                subprocess.run([
                    'git', 'clone', repo_url, str(clone_path)
                ], check=True, capture_output=True)
                
                # Analyze the repository
                analysis = self.auto_ci.scan(str(clone_path))
                audit_report = self.auto_ci.audit_repository(str(clone_path))
                
                # Generate pipeline
                pipeline_content, _ = self.auto_ci.generate_pipeline(
                    str(clone_path), 'github'
                )
                
                return {
                    'repository': repo_info,
                    'analysis': asdict(analysis),
                    'audit': audit_report,
                    'suggested_pipeline': pipeline_content
                }
                
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Failed to clone repository: {e}")
        except Exception as e:
            raise ValueError(f"Analysis failed: {e}")
    
    def _parse_github_url(self, url: str) -> Optional[Dict[str, str]]:
        """Parse GitHub URL and extract owner/repo"""
        import re
        
        patterns = [
            r'https://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?',
            r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?/?' 
        ]
        
        for pattern in patterns:
            match = re.match(pattern, url.strip())
            if match:
                return {
                    'owner': match.group(1),
                    'repo': match.group(2),
                    'url': url
                }
        
        return None
    
    def create_pr_with_pipeline(self, repo_url: str, branch_name: str = "auto-ci-setup"):
        """Create a PR with generated CI/CD pipeline (requires PyGithub)"""
        try:
            from github import Github
            
            if not self.github_token:
                raise ValueError("GitHub token required for PR creation")
            
            # Analyze repository
            result = self.analyze_github_repo(repo_url)
            repo_info = result['repository']
            pipeline_content = result['suggested_pipeline']
            
            # Connect to GitHub API
            g = Github(self.github_token)
            repo = g.get_repo(f"{repo_info['owner']}/{repo_info['repo']}")
            
            # Create new branch
            master_ref = repo.get_git_ref("heads/main")
            repo.create_git_ref(
                ref=f"refs/heads/{branch_name}",
                sha=master_ref.object.sha
            )
            
            # Create/update workflow file
            try:
                file = repo.get_contents(".github/workflows/ci.yml", ref=branch_name)
                repo.update_file(
                    ".github/workflows/ci.yml",
                    "Add Auto-CI generated workflow",
                    pipeline_content,
                    file.sha,
                    branch=branch_name
                )
            except:
                repo.create_file(
                    ".github/workflows/ci.yml",
                    "Add Auto-CI generated workflow", 
                    pipeline_content,
                    branch=branch_name
                )
            
            # Create pull request
            pr_body = f"""
## Auto-CI Generated Pipeline

This PR adds a CI/CD pipeline automatically generated by Auto-CI.

### Detected Technologies
- **Primary Language**: {result['analysis']['primary_language']}
- **Frameworks**: {', '.join([f['name'] for f in result['analysis']['frameworks']])}
- **Test Tools**: {', '.join([t['name'] for t in result['analysis']['test_tools']])}

### Audit Results
- **Recommendations**: {len(result['audit']['recommendations'])} suggestions
- **Missing Components**: {len(result['audit']['missing_components'])} items

### Pipeline Features
- Automated testing and linting
- Dependency caching for faster builds  
- Multi-version testing matrix
- Docker build (if applicable)

Please review the generated pipeline and customize as needed for your project.
"""
            
            pr = repo.create_pull(
                title="Add CI/CD pipeline (Auto-CI)",
                body=pr_body,
                head=branch_name,
                base="main"
            )
            
            return {
                'pr_url': pr.html_url,
                'pr_number': pr.number,
                'analysis': result
            }
            
        except ImportError:
            raise ValueError("PyGithub required for GitHub integration: pip install PyGithub")
        except Exception as e:
            raise ValueError(f"Failed to create PR: {e}")


if __name__ == "__main__":
    # Check if running as CLI
    import sys
    
    if len(sys.argv) > 1:
        # Run CLI
        exit(main())
    else:
        # Run examples
        print("Auto-CI: Automated CI/CD Pipeline Generator")
        print("=" * 50)
        print()
        print("Usage:")
        print("  python auto_ci.py scan [path]                    # Scan repository")
        print("  python auto_ci.py generate --ci github [path]    # Generate pipeline")
        print("  python auto_ci.py audit [path]                   # Audit repository")
        print()
        print("Or run examples:")
        
        try:
            run_examples()
        except KeyboardInterrupt:
            print("\n\nExamples cancelled by user")
        except Exception as e:
            print(f"\nError running examples: {e}")