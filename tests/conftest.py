import pytest
import tempfile
from pathlib import Path
import json

@pytest.fixture
def temp_repo():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)

@pytest.fixture
def python_repo(temp_repo):
    (temp_repo / "requirements.txt").write_text("flask==2.3.2\npytest==7.4.0")
    (temp_repo / "app.py").write_text("from flask import Flask\napp = Flask(__name__)")
    return temp_repo

@pytest.fixture
def javascript_repo(temp_repo):
    package_json = {
        "name": "test-app",
        "dependencies": {"express": "^4.18.0"},
        "devDependencies": {"jest": "^29.0.0"}
    }
    (temp_repo / "package.json").write_text(json.dumps(package_json))
    (temp_repo / "index.js").write_text("const express = require('express');")
    return temp_repo
