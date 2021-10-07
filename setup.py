import setuptools


setuptools.setup(
    name="BehaviorBuilder - OpheliaComplex",
    version="0.0.1",
    author="OpheliaComplex",
    description="A xml behavior file builder for skyrims havok system",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU GPL 3.0",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "BehaviorBuilder"},
    packages=setuptools.find_packages(include=["BehaviorBuilder.*"]),
    python_requires=">=3.6",
)