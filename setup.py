from setuptools import setup

classifiers = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'License :: OSI Approved :: MIT License',
    'Operating System :: POSIX',
    'Operating System :: Microsoft :: Windows',
    'Operating System :: MacOS :: MacOS X',
    'Topic :: Software Development :: Testing',
    'Topic :: Software Development :: Libraries',
    'Topic :: Utilities',
    'Programming Language :: Python :: Implementation :: CPython',
    'Programming Language :: Python :: Implementation :: PyPy'] + [
    ('Programming Language :: Python :: %s' % x) for x in
    '2 2.7 3 3.4 3.5 3.6'.split()]

with open('README.rst') as fd:
    long_description = fd.read()


def main():
    setup(
        name='pluggy',
        description='plugin and hook calling mechanisms for python',
        long_description=long_description,
        use_scm_version={
            'write_to': 'pluggy/_version.py',
        },
        setup_requires=['setuptools-scm'],
        license='MIT license',
        platforms=['unix', 'linux', 'osx', 'win32'],
        author='Holger Krekel',
        author_email='holger@merlinux.eu',
        url='https://github.com/pytest-dev/pluggy',
        python_requires='>=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*',
        classifiers=classifiers,
        packages=['pluggy'],
    )


if __name__ == '__main__':
    main()
