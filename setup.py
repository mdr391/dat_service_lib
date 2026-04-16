from setuptools import setup, find_packages

setup(
    name="dat-service-lib",
    version="1.0.0",
    description="Production-grade shared service library using Hexagonal Architecture (Ports & Adapters)",
    author="Zahidur Rahman",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "structlog>=21.0.0",
        "pydantic>=1.10.0,<2.0.0",
        "prometheus-client>=0.14.0",
        "pyjwt>=2.4.0",
    ],
    extras_require={
        "postgres": ["psycopg2-binary>=2.9.0"],
        "data": ["pandas>=1.3.0", "numpy>=1.21.0", "matplotlib>=3.4.0"],
        "dev": ["pytest>=7.0.0", "pytest-cov>=4.0.0"],
    },
)
