import pytest
import tempfile
import json
from pathlib import Path
from auto_ci import AutoCI

class TestAutoCIIntegration:
    def setup_method(self):
        self.auto_ci = AutoCI()
    
    def test_end_to_end_python_project(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "requirements.txt").write_text("flask==2.3.2\npytest==7.4.0")
            (temp_path / "app.py").write_text("""
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, World!"
""")
            (temp_path / "test_app.py").write_text("""
import pytest
from app import app

def test_hello():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
""")
            (temp_path / "Dockerfile").write_text("""
FROM python:3.11
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python", "app.py"]
""")
            analysis = self.auto_ci.scan(str(temp_path))
            assert analysis.primary_language == "python"
            pipeline_content, _ = self.auto_ci.generate_pipeline(str(temp_path), "github")
            assert "name: CI" in pipeline_content
            assert "setup-python" in pipeline_content
            assert "pytest" in pipeline_content
            audit_report = self.auto_ci.audit_repository(str(temp_path))
            assert audit_report["primary_language"] == "python"
            assert len(audit_report["detected_technologies"]["languages"]) > 0
    
    def test_pipeline_saving(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            (temp_path / "requirements.txt").write_text("requests==2.31.0")
            pipeline_content, _ = self.auto_ci.generate_pipeline(str(temp_path), "github")
            file_path = self.auto_ci.save_pipeline(pipeline_content, "github", str(temp_path))
            saved_file = Path(file_path)
            assert saved_file.exists()
            assert saved_file.name == "ci.yml"
            assert ".github/workflows" in str(saved_file)
            content = saved_file.read_text()
            assert "name: CI" in content
