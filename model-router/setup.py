from setuptools import setup

setup(
    name="model-router",
    version="0.1.0",
    py_modules=["router", "router_config"],
    install_requires=["anthropic>=0.45.0", "openai>=1.14.0", "python-dotenv>=1.0.0"],
)
