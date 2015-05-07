import os
import sys
import setuptools
from setuptools import setup

classifiers = [
    'Development Status :: 3 - Alpha ',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: MacOS :: MacOS X',
    'Topic :: Software Development :: Testing',
    'Topic :: Software Development :: Libraries',
    'Topic :: Utilities'] + [
    ('Programming Language :: Python :: %s' % x) for x in
    '2 2.6 2.7 3 3.3 3.4'.split()]

with open('README.rst') as fd:
    long_description = fd.read()


def get_version():
    p = os.path.join(os.path.dirname(
                     os.path.abspath(__file__)), "pluggy.py")
    with open(p) as f:
        for line in f.readlines():
            if "__version__" in line:
                return line.strip().split("=")[-1].strip(" '")
    raise ValueError("could not read version")


def main():
    setup(
        name='pluggy',
        description='plugin and hook calling mechanisms for python',
        long_description=long_description,
        version=get_version(),
        license='MIT license',
        platforms=['unix', 'linux', 'osx', 'win32'],
        author='Holger Krekel',
        author_email='holger at merlinux.eu',
        classifiers=classifiers,
        py_modules=['pluggy'],
    )

if __name__ == '__main__':
    main()
