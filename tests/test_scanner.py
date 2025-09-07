import pytest
import tempfile
import json
from pathlib import Path
from auto_ci import RepoScanner, DetectedTechnology, RepoAnalysis

class TestRepoScanner:
    def setup_method(self):
        self.scanner = RepoScanner()
    
    def test_python_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "requirements.txt").write_text("flask==2.3.2\npytest==7.4.0")
            (temp_path / "app.py").write_text("from flask import Flask\napp = Flask(__name__)")
            (temp_path / "test_app.py").write_text("import pytest\ndef test_hello(): pass")
            analysis = self.scanner.scan_repository(str(temp_path))
            assert analysis.primary_language == "python"
            assert any(tech.name == "python" for tech in analysis.languages)
            assert any(tech.name == "flask" for tech in analysis.frameworks)
            assert any(tech.name == "pytest" for tech in analysis.test_tools)
    
    def test_javascript_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            package_json = {
                "name": "test-app",
                "dependencies": {"express": "^4.18.0"},
                "devDependencies": {"jest": "^29.0.0"}
            }
            (temp_path / "package.json").write_text(json.dumps(package_json))
            (temp_path / "index.js").write_text("const express = require('express');")
            analysis = self.scanner.scan_repository(str(temp_path))
            assert analysis.primary_language == "javascript"
            assert any(tech.name == "javascript" for tech in analysis.languages)
            assert any(tech.name == "express" for tech in analysis.frameworks)
    
    def test_go_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "go.mod").write_text("module example.com/hello\ngo 1.21")
            (temp_path / "main.go").write_text("package main\nfunc main() {}")
            (temp_path / "main_test.go").write_text("package main\nimport \"testing\"")
            analysis = self.scanner.scan_repository(str(temp_path))
            assert analysis.primary_language == "go"
            assert any(tech.name == "go" for tech in analysis.languages)
            assert any(tech.name == "go test" for tech in analysis.test_tools)
    
    def test_docker_detection(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "Dockerfile").write_text("FROM python:3.11\nCOPY . /app")
            (temp_path / "docker-compose.yml").write_text("version: '3'\nservices:\n  app:\n    build: .")
            analysis = self.scanner.scan_repository(str(temp_path))
            assert any(tech.name == "docker" for tech in analysis.containers)
    
    def test_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            analysis = self.scanner.scan_repository(temp_dir)
            assert len(analysis.languages) == 0
            assert analysis.primary_language is None
    
    def test_confidence_scoring(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "requirements.txt").write_text("flask==2.3.2")
            (temp_path / "setup.py").write_text("from setuptools import setup")
            (temp_path / "app.py").write_text("print('hello')")
            analysis = self.scanner.scan_repository(str(temp_path))
            python_tech = next(tech for tech in analysis.languages if tech.name == "python")
            assert python_tech.confidence > 0.5
