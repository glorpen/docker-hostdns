import os

from setuptools import setup, find_packages
import re

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.rst')) as f:
    README = f.read()
with open(os.path.join(here, 'CHANGES.rst')) as f:
    CHANGES = f.read()

name = "docker_hostdns"
name_human = "docker-hostdns"

with open("%s/src/%s/__init__.py" % (here, name), "rt") as f:
    data = f.read()
    version = re.search(r'^__version__\s*=\s*"([^"]+)', data, re.MULTILINE).group(1)
    description = re.search(r'^__description__\s*=\s*"([^"]+)', data, re.MULTILINE).group(1)

requires = [
    'docker>=2.0.0',
    'dnspython>=1.13.0'
]

suggested_require = [
    "python-daemon"
]
dev_require = []
tests_require = ['unittest']

setup(name=name_human,
      version = version,
      description=description,
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
          "Programming Language :: Python",
          "Development Status :: 5 - Production/Stable",
          "Intended Audience :: Developers",
          "Intended Audience :: System Administrators",
          "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
          "Programming Language :: Python :: 3 :: Only",
          "Topic :: Software Development",
          "Topic :: Utilities",
      ],
      author='Arkadiusz Dzięgiel',
      author_email='arkadiusz.dziegiel@glorpen.pl',
      url="https://github.com/glorpen/%s" % name_human,
      keywords='docker dns bind named',
      packages=find_packages("src"),
      package_dir = {'': 'src'},
      include_package_data=True,
      zip_safe=True,
      extras_require={
          'testing': tests_require + suggested_require,
          'development': dev_require + tests_require + suggested_require,
          'suggested': suggested_require
      },
      install_requires=requires,
      entry_points = {
        "console_scripts": [
            "docker-hostdns = docker_hostdns.console:execute",
        ]
      },
      test_suite="docker_hostdns.tests",
)
