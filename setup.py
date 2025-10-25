from setuptools import setup, find_packages

setup(
    name="mr_eleven_stream",
    version="1.0.0",
    description="ElevenLabs streaming TTS plugin for MindRoot",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "elevenlabs>=1.0.0",
        "dotenv"
    ],
    extras_require={
        "playback": [
            "pygame>=2.0.0",
            "pydub>=0.25.0",
            "simpleaudio>=1.0.0",
        ],
        "dev": [
            "pytest",
            "pytest-asyncio",
        ],
    },
    python_requires=">=3.8",
    author="MindRoot",
    author_email="admin@mindroot.ai",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
