from setuptools import setup, find_packages

requires = [
    'requests',
]

setup(
    name='dyn-gandi',
    version='1.0',
    long_description=__doc__,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=requires,
    entry_points={
        'console_scripts': [
            'dyn_gandi = dyn_gandi:cli'
        ]
    },
    dependency_links=[]
)
