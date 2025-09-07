import pytest
import yaml
from auto_ci import (
    GitHubActionsGenerator, GitLabCIGenerator, CircleCIGenerator,
    RepoAnalysis, DetectedTechnology
)

class TestPipelineGenerators:
    def create_python_analysis(self):
        return RepoAnalysis(
            languages=[DetectedTechnology("python", confidence=1.0)],
            frameworks=[DetectedTechnology("flask", confidence=0.8)],
            test_tools=[DetectedTechnology("pytest", confidence=0.6)],
            build_tools=[DetectedTechnology("setuptools", confidence=0.5)],
            containers=[DetectedTechnology("docker", confidence=0.8)],
            infrastructure=[],
            package_managers=[DetectedTechnology("pip", confidence=1.0)],
            repo_path="/test/repo"
        )
    
    def test_github_actions_python_generation(self):
        generator = GitHubActionsGenerator()
        analysis = self.create_python_analysis()
        pipeline = generator.generate(analysis, {})
        pipeline_dict = yaml.safe_load(pipeline)
        assert pipeline_dict["name"] == "CI"
        assert "on" in pipeline_dict
        assert "jobs" in pipeline_dict
        assert "lint" in pipeline_dict["jobs"]
        assert "test" in pipeline_dict["jobs"]
        assert "docker" in pipeline_dict["jobs"]
        test_job = pipeline_dict["jobs"]["test"]
        assert any("setup-python" in str(step) for step in test_job["steps"])
    
    def test_gitlab_ci_python_generation(self):
        generator = GitLabCIGenerator()
        analysis = self.create_python_analysis()
        pipeline = generator.generate(analysis, {})
        pipeline_dict = yaml.safe_load(pipeline)
        assert "stages" in pipeline_dict
        assert "lint" in pipeline_dict["stages"]
        assert "test" in pipeline_dict["stages"]
        assert pipeline_dict["lint"]["image"] == "python:3.11"
    
    def test_circleci_python_generation(self):
        generator = CircleCIGenerator()
        analysis = self.create_python_analysis()
        pipeline = generator.generate(analysis, {})
        pipeline_dict = yaml.safe_load(pipeline)
        assert pipeline_dict["version"] == 2.1
        assert "jobs" in pipeline_dict
        assert "workflows" in pipeline_dict
    
    def test_javascript_generation(self):
        analysis = RepoAnalysis(
            languages=[DetectedTechnology("javascript", confidence=1.0)],
            frameworks=[DetectedTechnology("react", confidence=0.8)],
            test_tools=[DetectedTechnology("jest", confidence=0.6)],
            build_tools=[DetectedTechnology("webpack", confidence=0.7)],
            containers=[],
            infrastructure=[],
            package_managers=[DetectedTechnology("npm", confidence=1.0)],
            repo_path="/test/repo"
        )
        generator = GitHubActionsGenerator()
        pipeline = generator.generate(analysis, {})
        pipeline_dict = yaml.safe_load(pipeline)
        assert "lint-and-test" in pipeline_dict["jobs"]
        job = pipeline_dict["jobs"]["lint-and-test"]
        assert any("setup-node" in str(step) for step in job["steps"])
