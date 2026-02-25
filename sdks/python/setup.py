from setuptools import setup, find_packages

setup(
    name="lap-sdk",
    version="0.1.0",
    description="Lean API Platform SDK -- compressed API docs for LLM agents",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=["pyyaml>=6.0"],
    extras_require={"tokens": ["tiktoken>=0.5"], "langchain": ["langchain>=0.1"]},
)
