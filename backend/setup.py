from setuptools import setup, find_packages

setup(
    name="anonidata-backend",
    version="1.0.0",
    description="Backend para anonimización de PDFs",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "PyMuPDF>=1.23.8",
        "pikepdf>=8.10.1",
        "spacy>=3.7.2",
        "opencv-python>=4.8.1",
        "pydantic>=2.5.3",
        "loguru>=0.7.2",
    ],
    entry_points={
        "console_scripts": [
            "anonidata-backend=main:main",
        ],
    },
)
