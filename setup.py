#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="agente_calendario",
    version="2.1.0",
    author="Reinel G. Paredes",
    author_email="reinelgparedes@gmail.com",
    description="Agente conversacional para gestionar eventos del calendario usando LLM local. Ejecuta la operacion correspondiente en el archivo .ics del calendario / Conversational agent for managing calendar events using local LLM. Executes the corresponding operation on the calendar ICS file.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/rgparedess/agente_calendario",
    py_modules=["agente_calendario"],
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "requests>=2.25.0",
        "calendario_ics>=2.1.0",   # dependencia
    ],
    entry_points={
        "console_scripts": [
            "calendario-agent = agente_calendario:main",
        ],
    },
)